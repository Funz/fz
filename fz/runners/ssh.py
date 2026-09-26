"""SSH calculator: host key policy, URI parsing, remote execution and SFTP transfers."""

import os
import time
import hashlib
import base64
import uuid
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from .base import Calculator
from ..logging import log_warning, log_info
from ..config import get_config
from .manager import resolve_timeout, get_environment_info
from .errors import classify_error

try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy, RejectPolicy

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    SSHClient = None
    AutoAddPolicy = None
    RejectPolicy = None


class InteractiveHostKeyPolicy(
    paramiko.MissingHostKeyPolicy if PARAMIKO_AVAILABLE else object
):
    """
    Custom host key policy that validates fingerprints interactively or stores them
    """

    def __init__(self, auto_accept: bool = False):
        self.auto_accept = auto_accept
        self.known_hosts_file = Path.home() / ".ssh" / "known_hosts"

    def missing_host_key(self, client, hostname, key):
        """
        Handle missing host key by validating fingerprint
        """
        # Get key fingerprint
        fingerprint = self._get_key_fingerprint(key)
        key_type = key.get_name()

        log_warning(f"Host key for '{hostname}' is not known.")
        log_info(f"Key type: {key_type}")
        log_info(f"Fingerprint: {fingerprint}")

        if self.auto_accept:
            log_info("Auto-accepting host key (auto_accept=True)")
            self._add_host_key(client, hostname, key)
            return

        # Interactive prompt
        while True:
            response = (
                input("Accept this host key? [y/N/fingerprint]: ").strip().lower()
            )

            if response == "y" or response == "yes":
                self._add_host_key(client, hostname, key)
                return
            elif response == "n" or response == "no" or response == "":
                raise paramiko.SSHException(f"Host key for {hostname} was rejected")
            elif response == "fingerprint":
                log_info(f"Full fingerprint: {fingerprint}")
                continue
            else:
                log_info("Please answer 'y' (yes), 'n' (no), or 'fingerprint'")

    def _get_key_fingerprint(self, key):
        """
        Get SHA256 fingerprint of the key
        """
        key_bytes = key.asbytes()
        digest = hashlib.sha256(key_bytes).digest()
        fingerprint = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"SHA256:{fingerprint}"

    def _add_host_key(self, client, hostname, key):
        """
        Add host key to client and optionally to known_hosts file
        """
        client.get_host_keys().add(hostname, key.get_name(), key)
        log_info(f"Host key for {hostname} added to session.")

        # Try to add to known_hosts file
        try:
            # Ensure .ssh directory exists
            self.known_hosts_file.parent.mkdir(exist_ok=True, mode=0o700)

            # Format: hostname keytype base64key
            key_line = f"{hostname} {key.get_name()} {key.get_base64()}\n"

            # Check if already in known_hosts
            if self.known_hosts_file.exists():
                existing_content = self.known_hosts_file.read_text()
                if key_line.strip() in existing_content:
                    return

            # Append to known_hosts
            with open(self.known_hosts_file, "a") as f:
                f.write(key_line)

            log_info(f"Host key added to {self.known_hosts_file}")

        except Exception as e:
            log_warning(f"Could not save host key to known_hosts: {e}")


def get_host_key_policy(password_provided: bool = False, auto_accept: bool = False):
    """
    Get appropriate host key policy based on authentication method

    Args:
        password_provided: Whether password was provided in URI
        auto_accept: Whether to auto-accept unknown host keys

    Returns:
        Appropriate paramiko host key policy
    """
    if not PARAMIKO_AVAILABLE:
        return None

    if auto_accept:
        return InteractiveHostKeyPolicy(auto_accept=True)

    # For password auth, be more interactive about host keys
    if password_provided:
        return InteractiveHostKeyPolicy(auto_accept=False)

    # For key-based auth, use standard paramiko behavior
    return paramiko.AutoAddPolicy()


def validate_ssh_connection_security(
    host: str, username: str, password: Optional[str]
) -> Dict[str, Any]:
    """
    Validate SSH connection security parameters

    Args:
        host: SSH host
        username: SSH username
        password: SSH password (if provided)

    Returns:
        Dict with security recommendations and settings
    """
    security_info = {
        "password_provided": password is not None,
        "recommendations": [],
        "warnings": [],
    }

    if password:
        security_info["warnings"].append(
            "Password provided in URI. Consider using key-based authentication for better security."
        )
        security_info["recommendations"].append(
            "Use 'ssh-keygen' to generate keys and 'ssh-copy-id' to set up key-based auth."
        )

    if not username:
        security_info["warnings"].append(
            "No username provided, will use current user or SSH_USER environment variable."
        )

    return security_info


def parse_ssh_uri(ssh_uri: str) -> Tuple[str, int, str, Optional[str], str]:
    """
    Parse SSH URI into components

    Args:
        ssh_uri: SSH URI in format ssh://[user[:password]@]host[:port]/command

    Returns:
        Tuple of (host, port, username, password, command)
    """
    # Remove ssh:// prefix
    if ssh_uri.startswith("ssh://"):
        uri_part = ssh_uri[6:]
    else:
        uri_part = ssh_uri

    # Split command part (everything after first /)
    if "/" in uri_part:
        connection_part, command = uri_part.split("/", 1)
    else:
        connection_part = uri_part
        command = ""

    # Parse connection part: [user[:password]@]host[:port]
    username = None
    password = None
    host = connection_part
    port = 22

    # Check for user info
    if "@" in connection_part:
        user_info, host_port = connection_part.split("@", 1)
        host = host_port

        # Check for password in user info
        if ":" in user_info:
            username, password = user_info.split(":", 1)
        else:
            username = user_info

    # Check for port in host
    if ":" in host:
        host, port_str = host.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"Invalid port number: {port_str}")

    return host, port, username, password, command


def run_ssh_calculation(
    working_dir: Path,
    ssh_uri: str,
    model: Dict,
    timeout: int = None,
    input_files_list: List[str] = None,
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run calculation via SSH

    Args:
        working_dir: Directory containing input files
        ssh_uri: SSH URI (e.g., "ssh://user:password@host:port/command")
        model: Model definition dict
        timeout: Timeout in seconds (None resolves via model["timeout"], then FZ_RUN_TIMEOUT config default, 3600)
        input_files_list: List of input file names in order (from .fz_hash)
        static_entries: Pre-resolved input_static entries, explicitly
            transferred (relative ones only - see transfer_static_files_to_remote_sftp)

    Returns:
        Dict containing calculation results and status
    """
    # Resolve effective timeout: explicit arg > model's "timeout" entry > config default
    timeout = resolve_timeout(model, timeout)

    # Import here to avoid circular imports
    from ..core import is_interrupted

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": ssh_uri,
        }

    if not PARAMIKO_AVAILABLE:
        return {
            "status": "error",
            "error": "paramiko library not available. Install with: pip install paramiko",
        }

    start_time = datetime.now()
    env_info = get_environment_info()

    try:
        # Parse SSH URI
        host, port, username, password, command = parse_ssh_uri(ssh_uri)

        if not host:
            return {"status": "error", "error": "No host specified in SSH URI"}

        if not username:
            # Try to get username from environment or use current user
            username = os.getenv("SSH_USER") or getpass.getuser()

        # Validate connection security
        security_info = validate_ssh_connection_security(host, username, password)
        for warning in security_info["warnings"]:
            log_warning(f"Security Warning: {warning}")

        log_info(f"Connecting to SSH: {username}@{host}:{port}")
        if security_info["password_provided"]:
            log_info("Using password authentication (keyring disabled)")
        else:
            log_info("Using key-based authentication")

        # Create SSH client
        ssh_client = paramiko.SSHClient()

        # Set appropriate host key policy based on authentication method
        config = get_config()
        host_key_policy = get_host_key_policy(
            password_provided=security_info["password_provided"],
            auto_accept=config.ssh_auto_accept_hostkeys,
        )
        ssh_client.set_missing_host_key_policy(host_key_policy)

        # Load known host keys
        try:
            ssh_client.load_system_host_keys()
            ssh_client.load_host_keys(os.path.expanduser("~/.ssh/known_hosts"))
        except Exception as e:
            log_warning(f"Could not load host keys: {e}")

        # Prepare connection arguments
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 30 if timeout is None else min(timeout, 30),  # Connection timeout
        }

        if password:
            # Password provided: use only password auth, disable key lookup
            connect_kwargs["password"] = password
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False
            log_info("Disabled SSH agent and key lookup (password provided)")
        else:
            # No password: use key-based authentication
            connect_kwargs["look_for_keys"] = True
            connect_kwargs["allow_agent"] = True

        ssh_client.connect(**connect_kwargs)

        # Set keepalive for long-running connections
        transport = ssh_client.get_transport()
        if transport:
            transport.set_keepalive(config.ssh_keepalive)

        # Create SFTP client for file transfer
        sftp = ssh_client.open_sftp()

        # Create remote temporary directory in ./.fz/tmp (get absolute path)
        # Get SSH remote root dir (absolute)
        remote_root_dir = "~"  # Default to home directory
        try:
            stdin, stdout, stderr = ssh_client.exec_command("pwd", timeout=10)
            remote_root_dir = stdout.read().decode("utf-8").strip()
        except Exception as e:
            log_warning(
                f"Could not determine remote root directory, defaulting to ~/: {e}"
            )

        # Create unique remote directory using case-specific identifier
        # Extract unique identifier from local working_dir to ensure each case gets its own remote dir
        # working_dir typically looks like: /path/to/.fz/tmp/fz_temp_abc123.../case_name
        # We use the last component of the path as a unique identifier for this calculation
        local_dir_identifier = working_dir.name  # e.g., "x=1,y=2" or "single_case"

        # Also include a UUID to handle edge cases where dir names might collide
        # (e.g., same variable values running on different hosts or at different times)
        unique_id = uuid.uuid4().hex[:8]  # Short UUID for additional uniqueness

        # Build remote directory name with both case identifier and UUID
        # This ensures parallel calculations to the same SSH host use distinct directories
        remote_temp_dir = (
            f"{remote_root_dir}/.fz/tmp/fz_calc_{local_dir_identifier}_{unique_id}"
        )
        ssh_client.exec_command(f"mkdir -p {remote_temp_dir}")

        log_info(f"Created remote directory: {remote_temp_dir}")
        log_info(f"🌐 SSH calculation using remote directory: {username}@{host}:{remote_temp_dir}")

        try:
            # Transfer input files to remote
            _transfer_files_to_remote(sftp, working_dir, remote_temp_dir)
            transfer_static_files_to_remote_sftp(sftp, static_entries, remote_temp_dir)

            # Execute command on remote
            result = _execute_remote_command(
                ssh_client,
                command,
                remote_temp_dir,
                working_dir,
                timeout,
                start_time,
                env_info,
                input_files_list,
            )

            # Transfer results back
            _transfer_results_from_remote(sftp, remote_temp_dir, working_dir)

            # Parse output using fzo
            from ..core import fzo

            if result["status"] == "done":
                try:
                    output_results = fzo(working_dir, model)
                    # Convert DataFrame to dict if needed (fzo returns DataFrame when pandas available)
                    if hasattr(output_results, "to_dict"):
                        # DataFrame - convert to dict (first row as we only have one case)
                        output_dict = output_results.iloc[0].to_dict()
                    else:
                        # Already a dict
                        output_dict = output_results

                    # Propagate _output_error from fzo if present
                    output_error = output_dict.pop("_output_error", None)
                    result.update(output_dict)
                    result["calculator"] = f"ssh://{host}"
                    result["command"] = command
                    if output_error:
                        result["error"] = f"Missing output on remote server: {output_error}"
                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    result["error"] = f"Output parsing failed after successful remote execution: {e}"

            # Add command to result even if not done
            if "command" not in result:
                result["command"] = command

            return result

        finally:
            # Cleanup remote directory
            try:
                ssh_client.exec_command(f"rm -rf {remote_temp_dir}")
                log_info(f"Cleaned up remote directory: {remote_temp_dir}")
            except Exception as e:
                log_warning(f"Could not cleanup remote directory: {e}")

            sftp.close()

    except Exception as e:
        # Classify SSH-level errors for better diagnostics
        error_str = str(e)
        error_msg = classify_error(
            stderr=error_str,
            exit_code=None,
            command=ssh_uri,
            protocol="ssh",
        )
        return {"status": "error", "error": f"SSH calculation failed: {error_msg}", "command": ssh_uri}
    finally:
        try:
            ssh_client.close()
        except:
            pass


def _transfer_files_to_remote(sftp, local_dir: Path, remote_dir: str) -> None:
    """
    Transfer files from local directory to remote directory via SFTP
    """
    for item in local_dir.iterdir():
        if item.is_file():
            local_path = str(item)
            remote_path = f"{remote_dir}/{item.name}"
            log_info(
                f"Transferring {item.name} from local ({local_path}) to remote ({remote_path})"
            )
            sftp.put(local_path, remote_path)


def _sftp_mkdir_p(sftp, remote_dir: str) -> None:
    """Create a remote directory (and parents) via SFTP, ignoring "already exists"."""
    parts = remote_dir.strip("/").split("/")
    path = ""
    for part in parts:
        path = f"{path}/{part}" if path else f"/{part}"
        try:
            sftp.mkdir(path)
        except IOError:
            pass  # Already exists


def transfer_static_files_to_remote_sftp(sftp, static_entries: Optional[List[Dict[str, Any]]], remote_dir: str) -> None:
    """
    Explicitly transfer a model's relative static_files entries to a remote
    directory via SFTP.

    Relative static_files (see helpers.resolve_static_files) live outside
    input_path/working_dir - only a local symlink is placed there for local
    execution - so the generic per-case file transfer (_transfer_files_to_remote,
    which only sees what's physically in working_dir) never finds them. This
    uploads them explicitly from their real source path instead. Absolute entries
    are skipped: they're assumed already present at that same path on the
    calculator side.
    """
    if not static_entries:
        return
    for entry in static_entries:
        if entry["is_absolute"]:
            continue
        remote_path = f"{remote_dir}/{entry['name']}"
        if "/" in entry["name"]:
            _sftp_mkdir_p(sftp, str(Path(remote_path).parent).replace("\\", "/"))
        log_info(f"Transferring static file {entry['name']} from {entry['source']} to remote ({remote_path})")
        sftp.put(str(entry["source"]), remote_path)


def _execute_remote_command(
    ssh_client,
    command: str,
    remote_dir: str,
    local_dir: Path,
    timeout: int,
    start_time: datetime = None,
    env_info: Dict = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Execute command on remote server with interrupt handling

    Args:
        ssh_client: SSH client connection
        command: Command to execute
        remote_dir: Remote directory path
        local_dir: Local directory path
        timeout: Timeout in seconds
        start_time: Start time of execution
        env_info: Environment information
        input_files_list: List of input file names in order (from .fz_hash)
    """
    # Import here to avoid circular imports
    from ..core import is_interrupted

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": command,
        }

    # Build arguments from input files list
    input_argument = " ".join(input_files_list) if input_files_list else "."

    # Construct full command
    if command:
        full_command = f"cd {remote_dir} && {command} {input_argument}"
    else:
        full_command = f"cd {remote_dir} && ./{input_argument}"

    log_info(f"Executing remote command: {full_command}")

    # Execute command
    command_start_time = datetime.now()
    stdin, stdout, stderr = ssh_client.exec_command(full_command, timeout=timeout)

    # Get the channel for polling
    channel = stdout.channel

    # Poll for completion with interrupt checking
    poll_interval = 0.5  # Poll every 500ms
    elapsed_time = 0.0
    exit_code = None

    try:
        while not channel.exit_status_ready():
            # Check if user requested interrupt
            if is_interrupted():
                log_warning(f"⚠️  Interrupt detected, terminating remote process...")
                # Send SIGTERM to remote process group
                try:
                    # Try to kill the remote process
                    # Use channel.send to send Ctrl+C
                    channel.send('\x03')  # Send Ctrl+C (SIGINT)
                    time.sleep(0.5)  # Give process time to terminate

                    # If still running, force kill
                    if not channel.exit_status_ready():
                        # Try killing the process tree
                        kill_cmd = f"pkill -P $(pgrep -f '{command[:50]}')"  # Kill process tree
                        try:
                            ssh_client.exec_command(kill_cmd, timeout=2)
                        except:
                            pass
                except Exception as e:
                    log_warning(f"⚠️  Could not terminate remote process: {e}")

                raise KeyboardInterrupt("Remote process interrupted by user")

            # Check for timeout
            if timeout is not None and elapsed_time >= timeout:
                log_warning(f"⚠️  Remote command timeout after {timeout}s")
                try:
                    channel.send('\x03')  # Send Ctrl+C
                    time.sleep(0.5)
                except:
                    pass
                return {
                    "status": "timeout",
                    "error": f"Command timed out after {timeout} seconds",
                    "command": full_command,
                }

            # Sleep briefly before next poll
            time.sleep(poll_interval)
            elapsed_time += poll_interval

        # Get exit status
        exit_code = channel.recv_exit_status()
        command_end_time = datetime.now()

    except KeyboardInterrupt:
        # Handle interrupt - close channel
        try:
            channel.close()
        except:
            pass
        return {
            "status": "interrupted",
            "error": "Remote calculation interrupted by user",
            "command": full_command,
        }

    # Get output
    stdout_data = stdout.read().decode("utf-8")
    stderr_data = stderr.read().decode("utf-8")

    # Calculate timing
    if start_time:
        total_execution_time = (command_end_time - start_time).total_seconds()
        command_execution_time = (command_end_time - command_start_time).total_seconds()
    else:
        total_execution_time = command_execution_time = 0.0

    # Get remote system information
    remote_info_cmd = "hostname; whoami; pwd; uname -s; uname -a"
    try:
        _, remote_stdout, _ = ssh_client.exec_command(remote_info_cmd, timeout=10)
        remote_info_lines = remote_stdout.read().decode("utf-8").strip().split("\n")
        remote_hostname = (
            remote_info_lines[0] if len(remote_info_lines) > 0 else "unknown"
        )
        remote_user = remote_info_lines[1] if len(remote_info_lines) > 1 else "unknown"
        remote_pwd = remote_info_lines[2] if len(remote_info_lines) > 2 else "unknown"
        remote_os = remote_info_lines[3] if len(remote_info_lines) > 3 else "unknown"
        remote_platform = (
            remote_info_lines[4] if len(remote_info_lines) > 4 else "unknown"
        )
    except:
        remote_hostname = remote_user = remote_pwd = remote_os = remote_platform = (
            "unknown"
        )

    # Create enhanced log files remotely
    log_command = f"""cd {remote_dir}

# Create enhanced log.txt
cat > log.txt << 'EOF'
Command: {full_command}
Exit code: {exit_code}
Time start: {start_time.isoformat() if start_time else 'unknown'}
Time end: {command_end_time.isoformat()}
Command execution time: {command_execution_time:.3f} seconds
Total execution time: {total_execution_time:.3f} seconds
Local user: {env_info.get('user', 'unknown') if env_info else 'unknown'}
Local hostname: {env_info.get('hostname', 'unknown') if env_info else 'unknown'}
Local operating system: {env_info.get('operating_system', 'unknown') if env_info else 'unknown'}
Local working directory: {env_info.get('working_dir', 'unknown') if env_info else 'unknown'}
Remote user: {remote_user}
Remote hostname: {remote_hostname}
Remote operating system: {remote_os}
Remote platform: {remote_platform}
Remote working directory: {remote_pwd}
Timestamp: $(date)
EOF

# Create output files
cat > out.txt << 'EOF'
{stdout_data}
EOF

cat > err.txt << 'EOF'
{stderr_data}
EOF
"""
    ssh_client.exec_command(log_command, timeout=30)

    if exit_code != 0:
        # Classify the error to provide a human-readable message
        error_message = classify_error(
            stderr=stderr_data,
            exit_code=exit_code,
            command=command,
            protocol="ssh",
        )
        return {
            "status": "failed",
            "exit_code": exit_code,
            "error": error_message,
            "stderr": stderr_data,
            "command": command,
        }

    return {"status": "done", "stdout": stdout_data, "stderr": stderr_data}


def _transfer_results_from_remote(sftp, remote_dir: str, local_dir: Path) -> None:
    """
    Transfer result files from remote directory back to local directory
    """
    try:
        # List remote files
        remote_files = sftp.listdir(remote_dir)

        for filename in remote_files:
            if filename not in [".", ".."]:
                remote_path = f"{remote_dir}/{filename}"
                local_path = local_dir / filename

                try:
                    log_info(f"Transferring {filename} from remote")
                    sftp.get(remote_path, str(local_path))
                except Exception as e:
                    log_warning(f"Could not transfer {filename}: {e}")

    except Exception as e:
        log_warning(f"Could not list remote files: {e}")


class SshCalculator(Calculator):
    scheme = "ssh"

    def run(self, working_dir, calculator_uri, model, timeout=None,
            original_input_was_dir=False, original_cwd=None,
            input_files_list=None, static_entries=None):
        return run_ssh_calculation(
            working_dir, calculator_uri, model, timeout, input_files_list,
            static_entries=static_entries,
        )
