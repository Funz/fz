"""
Calculation runners for fz package: calculator resolution and execution
"""

import os
import subprocess
import time
import re
import tarfile
import tempfile
import hashlib
import base64
import threading
import queue
import socket
import platform
import shutil

from .logging import log_error, log_warning, log_info, log_debug
from .config import get_config
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Any, Optional, Tuple
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy, RejectPolicy

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    SSHClient = None
    AutoAddPolicy = None
    RejectPolicy = None

from .io import load_aliases


def get_environment_info() -> Dict[str, str]:
    """
    Get environment information for logging

    Returns:
        Dict with environment variables and system info
    """
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"

    try:
        username = getpass.getuser()
    except:
        username = os.getenv("USER", os.getenv("USERNAME", "unknown"))

    return {
        "user": username,
        "hostname": hostname,
        "operating_system": platform.system(),
        "platform": platform.platform(),
        "working_dir": os.getcwd(),
        "python_version": platform.python_version(),
    }


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


def resolve_calculators(
    calculators: Union[str, List[str], List[Dict]], model_id: str = None
) -> List[str]:
    """
    Resolve calculator aliases to URI strings

    Args:
        calculators: Calculator specifications (string, list of strings, or list of dicts)
        model_id: Optional model ID for model-specific calculator commands

    Returns:
        List of calculator URI strings
    """
    if isinstance(calculators, str):
        if calculators == "*":
            # Find all calculator files
            calc_files = []
            search_dirs = [Path.cwd() / ".fz", Path.home() / ".fz"]
            for base_dir in search_dirs:
                calc_dir = base_dir / "calculators"
                if calc_dir.exists():
                    calc_files.extend([f.stem for f in calc_dir.glob("*.json")])

            # Implicitly include cache calculator as first option when using "*"
            # This ensures cache is checked before running new calculations
            calculators = ["cache://results"] + calc_files
        else:
            calculators = [calculators]

    result = []
    for calc in calculators:
        if isinstance(calc, dict):
            # Direct calculator dict
            uri = calc.get("uri", "sh://")
            # Handle models field if present and model_id provided
            if model_id and "models" in calc and model_id in calc["models"]:
                command = calc["models"][model_id]
                result.append(f"{uri}{command}")
            else:
                result.append(uri)
        elif isinstance(calc, str):
            if "://" in calc:
                # Direct URI
                result.append(calc)
            else:
                # Alias - load from file
                calc_data = load_aliases(calc, "calculators")
                if calc_data:
                    uri = calc_data.get("uri", "sh://")
                    # Handle models field if present and model_id provided
                    if (
                        model_id
                        and "models" in calc_data
                        and model_id in calc_data["models"]
                    ):
                        command = calc_data["models"][model_id]
                        result.append(f"{uri}{command}")
                    else:
                        result.append(uri)
                else:
                    result.append(calc)
    return result


def run_calculation(
    working_dir: Path,
    calculator_uri: str,
    model: Dict,
    timeout: int = 300,
    original_input_was_dir: bool = False,
    original_cwd: str = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run a single calculation on a calculator

    Args:
        working_dir: Directory containing input files
        calculator_uri: Calculator URI (e.g., "sh://command", "ssh://host/command")
        model: Model definition dict
        timeout: Timeout in seconds
        original_input_was_dir: Whether original input was a directory
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    base_uri = calculator_uri

    # Handle different calculator types
    if base_uri.startswith("cache://"):
        # Cache handling is now done at fzr level, this should not be reached
        return {"status": "cache_miss"}

    elif base_uri.startswith("sh://") or base_uri == "sh:":
        # Local shell execution
        command = base_uri[5:] if base_uri.startswith("sh://") else ""
        return run_local_calculation(
            working_dir,
            command,
            model,
            timeout,
            original_input_was_dir,
            original_cwd,
            input_files_list,
        )

    elif base_uri.startswith("ssh://"):
        # Remote SSH execution
        return run_ssh_calculation(
            working_dir, base_uri, model, timeout, input_files_list
        )

    else:
        # Default to local shell
        return run_local_calculation(
            working_dir,
            base_uri,
            model,
            timeout,
            original_input_was_dir,
            original_cwd,
            input_files_list,
        )


def resolve_all_paths_in_command(command: str, original_cwd: str) -> tuple[str, bool]:
    """
    Resolve ALL file paths in a shell command to absolute paths

    This function handles:
    - Script paths and file arguments
    - Input/output redirections (>, >>, <, <<)
    - File operations (cp, mv, tar, etc.)
    - Complex command structures with pipes and &&/||
    - Path arguments with spaces and special characters
    - Multiple file operations in compound commands

    Args:
        command: Original shell command
        original_cwd: Original working directory for resolving relative paths

    Returns:
        Tuple of (resolved_command, was_changed) where:
        - resolved_command: Command with all relative file paths converted to absolute paths
        - was_changed: Boolean indicating if any changes were made
    """
    import shlex
    import re

    try:
        # Enhanced pattern for redirections including complex cases
        redirection_pattern = r"([<>]+)\s*([^\s|&;\'\"]+|\'[^\']*\'|\"[^\"]*\")"

        # Pattern for pipe separators to handle compound commands
        pipe_pattern = r"\s*(\|{1,2}|\&{1,2}|\;)\s*"

        # Split command by pipes/operators while preserving them
        command_segments = re.split(pipe_pattern, command)
        resolved_segments = []

        for segment in command_segments:
            segment = segment.strip()
            if not segment:
                continue

            # Check if this is an operator (|, ||, &&, ;)
            if re.match(r"^(\|{1,2}|\&{1,2}|\;)$", segment):
                resolved_segments.append(segment)
                continue

            # Process this command segment
            resolved_segment, segment_changed = _resolve_paths_in_segment(
                segment, original_cwd
            )
            resolved_segments.append(resolved_segment)

        final_command = " ".join(resolved_segments)

        # Check if there are meaningful path changes (not just quote normalization)
        has_meaningful_changes = False
        if final_command != command:
            # Simple heuristic: if the resolved command contains absolute paths where
            # the original had relative paths, it's a meaningful change
            if "/" in final_command and final_command.count("/") > command.count("/"):
                has_meaningful_changes = True

        return final_command, has_meaningful_changes

    except Exception as e:
        log_warning(f"Path resolution failed, using original command: {e}")
        return command, False


def _resolve_paths_in_segment(segment: str, original_cwd: str) -> tuple[str, bool]:
    """
    Resolve ALL relative paths in a command segment to absolute paths.
    Simple approach: convert any token that looks like a file path to absolute.
    """
    import shlex
    import re
    import os

    # Parse command parts using shlex for proper quote handling
    try:
        command_parts = shlex.split(segment)
    except ValueError:
        # Fallback to simple split if shlex fails
        command_parts = segment.split()

    if not command_parts:
        return segment, False

    resolved_parts = []
    was_changed = False

    for part in command_parts:
        # Skip if already absolute path
        if os.path.isabs(part):
            resolved_parts.append(part)
            continue

        # Skip shell operators and special tokens
        if part in ["|", "||", "&&", ";", ">", ">>", "<", "<<", "&1", "&2"]:
            resolved_parts.append(part)
            continue

        # Skip command flags (start with - and longer than 1 char)
        if part.startswith("-") and len(part) > 1:
            resolved_parts.append(part)
            continue

        # Skip variables and expansions
        if part.startswith("$") or (part.startswith("${") and part.endswith("}")):
            resolved_parts.append(part)
            continue

        # Skip pure numbers
        if re.match(r"^[0-9]+$", part):
            resolved_parts.append(part)
            continue

        # Skip URLs
        if part.startswith(("http://", "https://", "ftp://", "ssh://", "file://")):
            resolved_parts.append(part)
            continue

        # Skip literals and built-in values
        if part in [
            "true",
            "false",
            "null",
            "nil",
            "echo",
            "cat",
            "cp",
            "mv",
            "rm",
            "ls",
            "grep",
            "awk",
            "sed",
            "sort",
            "uniq",
            "wc",
            "head",
            "tail",
            "tee",
            "find",
            "chmod",
            "chown",
            "python",
            "python3",
            "bash",
            "sh",
            "perl",
            "ruby",
            "java",
            "gcc",
            "make",
            "tar",
            "gzip",
            "zip",
        ]:
            resolved_parts.append(part)
            continue

        # Skip device files
        if part.startswith("/dev/"):
            resolved_parts.append(part)
            continue

        # Convert potential file paths to absolute
        # This includes:
        # - Files with extensions (script.sh, data.txt, etc.)
        # - Paths with slashes (./file, ../dir/file, subdir/file)
        # - Current/parent directory references (., ..)
        # - Simple filenames that could be files

        should_resolve = False

        # Contains path separator - definitely a path
        if "/" in part:
            should_resolve = True
        # Has file extension - likely a file
        elif (
            "." in part
            and not part.startswith(".")
            and re.match(r"^[^.]+\.[a-zA-Z0-9]+$", part)
        ):
            should_resolve = True
        # Current/parent directory references
        elif part in [".", ".."] or part.startswith("./") or part.startswith("../"):
            should_resolve = True
        # Simple potential filenames (alphanumeric + underscore, no spaces, not pure command names)
        elif re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$", part) and len(part) > 1:
            # Additional check: if it looks like it could be a filename
            # (contains letters and possibly numbers/dots/underscores)
            should_resolve = True

        if should_resolve:
            # Convert to absolute path
            abs_path = os.path.abspath(os.path.join(original_cwd, part))
            # Preserve quoting if the path contains spaces or special characters
            if " " in abs_path or "'" in abs_path or '"' in abs_path:
                resolved_parts.append(shlex.quote(abs_path))
            else:
                resolved_parts.append(abs_path)
            was_changed = True
        else:
            # Keep as-is
            resolved_parts.append(part)

    # Reconstruct the command
    final_segment = " ".join(resolved_parts)
    return final_segment, was_changed


def run_local_calculation(
    working_dir: Path,
    command: str,
    model: Dict,
    timeout: int = 300,
    original_input_was_dir: bool = False,
    original_cwd: str = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation locally via shell command

    Args:
        working_dir: Directory containing input files
        command: Shell command to execute
        model: Model definition dict
        timeout: Timeout in seconds
        original_input_was_dir: Whether original input was a directory
        original_cwd: Original working directory
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Import here to avoid circular imports
    from .core import fzo, is_interrupted

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": command,
        }

    # Use provided original_cwd or fall back to current directory
    if original_cwd is None:
        original_cwd = os.getcwd()
    start_time = datetime.now()
    env_info = get_environment_info()

    # Initialize variables for command tracking
    command_for_result = command
    process = None

    try:
        os.chdir(working_dir)

        # Build arguments from input files list
        input_argument = " ".join(input_files_list) if input_files_list else "."

        # Construct command - resolve ALL file paths to absolute for reliable parallel execution
        if command:
            resolved_command, was_changed = resolve_all_paths_in_command(
                command, original_cwd
            )
            command_for_result = resolved_command
            full_command = resolved_command + f" {input_argument}"

            # Display warning if command was changed
            if was_changed:
                log_info(f"Info: sh:// command paths resolved to absolute:")
                log_info(f"  Original: {command}")
                log_info(f"  Resolved: {resolved_command}")
        else:
            # Try to infer command from model or use generic approach
            full_command = f"./{input_argument}"
            command_for_result = None

        # Run calculation in the input directory (temp directory), files will be copied to result_dir afterwards
        working_dir = working_dir
        # Use absolute paths for output files to avoid race conditions in parallel execution
        out_file_path = working_dir / "out.txt"
        err_file_path = working_dir / "err.txt"
        log_info(f"Info: Running command: {full_command}")

        # Determine shell executable for Windows
        executable = None
        if platform.system() == "Windows":
            # On Windows, use bash if available (Git Bash, WSL, etc.)
            bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                shutil.which("bash"),
            ]
            for bash_path in bash_paths:
                if bash_path and os.path.exists(bash_path):
                    executable = bash_path
                    log_debug(f"Using bash at: {executable}")
                    break

            if not executable:
                log_warning(
                    "Bash not found on Windows. Commands may fail if they use bash-specific syntax."
                )

        with open(out_file_path, "w") as out_file, open(err_file_path, "w") as err_file:
            # Start process with Popen to allow interrupt handling
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=out_file,
                stderr=err_file,
                cwd=working_dir,
                executable=executable,
            )

            # Poll process and check for interrupts
            try:
                process.wait(timeout=timeout)
                result = process
            except subprocess.TimeoutExpired:
                # Timeout occurred
                if process:
                    process.kill()
                    process.wait()
                raise

        # Small delay to ensure all streams are properly closed and files are fully written
        # This prevents race conditions when moving the case directory
        time.sleep(0.01)  # 10ms delay

        # Create enhanced log file
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        log_file_path = working_dir / "log.txt"
        with open(log_file_path, "w") as log_file:
            # Command and execution info
            log_file.write(f"Command: {full_command}\n")
            log_file.write(f"Exit code: {result.returncode}\n")

            # Timing information
            log_file.write(f"Time start: {start_time.isoformat()}\n")
            log_file.write(f"Time end: {end_time.isoformat()}\n")
            log_file.write(f"Execution time: {execution_time:.3f} seconds\n")

            # Environment information
            log_file.write(f"User: {env_info['user']}\n")
            log_file.write(f"Hostname: {env_info['hostname']}\n")
            log_file.write(f"Operating system: {env_info['operating_system']}\n")
            log_file.write(f"Platform: {env_info['platform']}\n")
            log_file.write(f"Working directory: {working_dir}\n")
            log_file.write(f"Original directory: {original_cwd}\n")

            # Legacy timestamp for compatibility
            log_file.write(f"Timestamp: {time.ctime()}\n")

        if result.returncode != 0:
            # Read stderr for error details
            stderr_content = ""
            try:
                if err_file_path.exists():
                    with open(err_file_path, "r") as f:
                        stderr_content = f.read().strip()
            except Exception:
                pass

            failure_result = {
                "status": "failed",
                "exit_code": result.returncode,
                "error": f"Command failed with exit code {result.returncode}",
                "stderr": stderr_content,
            }

            # Include command information
            failure_result["command"] = command_for_result

            return failure_result

        # Parse output
        output_results = fzo(working_dir, model)

        # Convert DataFrame to dict if needed (fzo returns DataFrame when pandas available)
        if hasattr(output_results, "to_dict"):
            # DataFrame - convert to dict (first row as we only have one case)
            output_dict = output_results.iloc[0].to_dict()
        else:
            # Already a dict
            output_dict = output_results

        output_dict["status"] = "done"
        output_dict["calculator"] = "sh://"

        # Include command information
        output_dict["command"] = command_for_result

        return output_dict

    except subprocess.TimeoutExpired:
        timeout_result = {"status": "timeout"}
        timeout_result["command"] = command_for_result
        return timeout_result
    except KeyboardInterrupt:
        # Handle interrupt - terminate process if running
        if process and process.poll() is None:
            log_warning(f"⚠️  Terminating process due to interrupt...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log_warning(f"⚠️  Process didn't terminate, killing...")
                process.kill()
                process.wait()
        interrupt_result = {
            "status": "interrupted",
            "error": "Calculation interrupted by user",
        }
        interrupt_result["command"] = command_for_result
        return interrupt_result
    except Exception as e:
        error_result = {"status": "error", "error": str(e)}
        error_result["command"] = command_for_result
        return error_result
    finally:
        os.chdir(original_cwd)


def run_ssh_calculation(
    working_dir: Path,
    ssh_uri: str,
    model: Dict,
    timeout: int = 300,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation via SSH

    Args:
        working_dir: Directory containing input files
        ssh_uri: SSH URI (e.g., "ssh://user:password@host:port/command")
        model: Model definition dict
        timeout: Timeout in seconds
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
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
            import getpass

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
            "timeout": min(timeout, 30),  # Connection timeout
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

        remote_temp_dir = (
            f"{remote_root_dir}/.fz/tmp/fz_calc_{int(time.time())}_{os.getpid()}"
        )
        ssh_client.exec_command(f"mkdir -p {remote_temp_dir}")

        log_info(f"Created remote directory: {remote_temp_dir}")

        try:
            # Transfer input files to remote
            _transfer_files_to_remote(sftp, working_dir, remote_temp_dir)

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
            from .core import fzo

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
                    result.update(output_dict)
                    result["calculator"] = f"ssh://{host}"
                    result["command"] = command
                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    result["error"] = str(e)

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
        return {"status": "error", "error": f"SSH calculation failed: {str(e)}"}
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
    Execute command on remote server

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

    # Wait for completion
    exit_code = stdout.channel.recv_exit_status()
    command_end_time = datetime.now()

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
        return {"status": "failed", "exit_code": exit_code, "stderr": stderr_data}

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


def select_calculator_for_case(calculator_uris: List[str], case_index: int) -> str:
    """
    Select a calculator for a specific case using round-robin distribution

    Args:
        calculator_uris: List of available calculator URIs (excluding cache://)
        case_index: Index of the current case

    Returns:
        Selected calculator URI
    """
    if not calculator_uris:
        return "sh://"  # Fallback to default

    # Use round-robin to distribute cases across calculators
    selected_index = case_index % len(calculator_uris)
    return calculator_uris[selected_index]


def run_single_case_calculation(
    working_dir: Path,
    calculator_uri: str,
    model: Dict,
    timeout: int = 300,
    original_input_was_dir: bool = False,
    original_cwd: str = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation for a single case on a specific calculator

    Args:
        working_dir: Directory containing input files
        calculator_uri: Calculator URI to use for this case
        model: Model definition dict
        timeout: Timeout in seconds
        original_input_was_dir: Whether original input was a directory
        original_cwd: Original working directory
        input_files_list: List of input file names in order

    Returns:
        Dict containing calculation results and status
    """
    try:
        result = run_calculation(
            working_dir,
            calculator_uri,
            model,
            timeout,
            original_input_was_dir,
            original_cwd,
            input_files_list,
        )

        # Always add calculator URI to result
        result["calculator_uri"] = calculator_uri

        # If calculation failed, enhance error information
        if result.get("status") not in ["done", "timeout"]:
            # Add more detailed error context
            result["error_details"] = {
                "calculator": calculator_uri,
                "working_dir": str(working_dir),
                "status": result.get("status", "unknown"),
                "exit_code": result.get("exit_code"),
                "error_message": result.get("error", "No error message provided"),
                "stderr": result.get("stderr", "No stderr available"),
            }

        return result

    except Exception as e:
        import traceback

        return {
            "status": "error",
            "calculator_uri": calculator_uri,
            "error": str(e),
            "error_details": {
                "calculator": calculator_uri,
                "working_dir": str(working_dir),
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "traceback": traceback.format_exc(),
            },
        }
