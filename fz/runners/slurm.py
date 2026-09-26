"""SLURM calculator (local srun and remote over SSH)."""

import os
import subprocess
import time
import uuid
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from .base import Calculator
from ..logging import log_warning, log_info
from ..config import get_config
from ..shell import run_command
from .manager import resolve_timeout, get_environment_info
from .errors import classify_error
from .ssh import (
    validate_ssh_connection_security,
    get_host_key_policy,
    _transfer_files_to_remote,
    transfer_static_files_to_remote_sftp,
    _transfer_results_from_remote,
)

try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy, RejectPolicy

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    SSHClient = None
    AutoAddPolicy = None
    RejectPolicy = None


def parse_slurm_uri(slurm_uri: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str], str, str]:
    """
    Parse SLURM URI into components

    Args:
        slurm_uri: SLURM URI in format slurm://[user[:password]@host[:port]]:partition/script

    Returns:
        Tuple of (host, port, username, password, partition, script)
        - host will be None for local SLURM execution
        - port will be None if host is None or not specified
        - username will be None if host is None or not specified
        - password will be None if host is None or not specified
        - partition is the SLURM partition name (required)
        - script is the script path to execute (required)
    """
    # Remove slurm:// prefix
    if slurm_uri.startswith("slurm://"):
        uri_part = slurm_uri[8:]
    else:
        uri_part = slurm_uri

    # Split to find the partition and script (everything after FIRST /)
    # Format: [user[:password]@host[:port]]:partition/script
    if "/" not in uri_part:
        raise ValueError(
            f"Invalid SLURM URI format: '{slurm_uri}'. "
            "Expected format: slurm://[user@host]:partition/script or slurm://:partition/script"
        )

    # Split on FIRST / to separate partition/connection from script
    # This is important because script may contain / characters in the path
    first_slash_idx = uri_part.find("/")
    partition_part = uri_part[:first_slash_idx]
    script = uri_part[first_slash_idx + 1:]

    if not script:
        raise ValueError(
            f"Invalid SLURM URI: script path is required. "
            "Expected format: slurm://[user@host]:partition/script or slurm://:partition/script"
        )

    # Check for completely empty partition_part (e.g., slurm:///script.sh)
    if not partition_part:
        raise ValueError(
            f"Invalid SLURM URI: partition is required. "
            "Expected format: slurm://[user@host]:partition/script or slurm://:partition/script"
        )

    # Now parse partition_part to extract optional host and required partition
    # Format: [user[:password]@host[:port]]:partition
    host = None
    port = None
    username = None
    password = None
    partition = partition_part

    # Check if there's a colon that separates host from partition
    # We need to be careful because:
    # - user:password@host:port:partition has multiple colons
    # - host:port:partition has multiple colons
    # - :partition means local execution (new format)
    # - partition alone is NOT supported (must use :partition for local)

    # Look for @ symbol which indicates user@host format
    if "@" in partition_part:
        # Format is user[:password]@host[:port]:partition
        user_part, rest = partition_part.split("@", 1)

        # Parse user and optional password
        if ":" in user_part:
            username, password = user_part.split(":", 1)
        else:
            username = user_part

        # Parse host[:port]:partition
        # Find the last colon which separates host:port from partition
        if ":" in rest:
            # Could be host:port:partition or host:partition
            # We need to find where partition starts
            # Try to find a pattern: everything before last : is host[:port]
            last_colon_idx = rest.rfind(":")
            host_port_part = rest[:last_colon_idx]
            partition = rest[last_colon_idx + 1:]

            # Parse host[:port]
            if ":" in host_port_part:
                host, port_str = host_port_part.split(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    raise ValueError(f"Invalid port number: {port_str}")
            else:
                host = host_port_part
                port = 22  # Default SSH port
        else:
            # No colon after @, so it's just user@partition
            # This means local execution but with username specified (unusual)
            raise ValueError(
                f"Invalid SLURM URI format: '{slurm_uri}'. "
                "If username is provided, host must also be provided. "
                "Expected format: slurm://user@host:partition/script"
            )
    elif ":" in partition_part:
        # Format might be :partition (local), host:partition, or host:port:partition (no user)
        # Count colons to determine format
        colons = partition_part.count(":")

        if colons == 1:
            # Could be :partition (local) or host:partition (remote)
            parts = partition_part.split(":", 1)

            if parts[0] == "":
                # Format: :partition (local execution)
                host = None
                port = None
                partition = parts[1]
            else:
                # Format: host:partition (remote execution)
                host = parts[0]
                partition = parts[1]
                port = 22  # Default SSH port
        elif colons == 2:
            # host:port:partition
            parts = partition_part.split(":")
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                raise ValueError(f"Invalid port number: {parts[1]}")
            partition = parts[2]
        else:
            # Too many colons, unclear format
            raise ValueError(
                f"Invalid SLURM URI format: '{slurm_uri}'. "
                "Too many colons. Expected format: slurm://[user@host]:partition/script or slurm://:partition/script"
            )
    else:
        # No colon at all - this is no longer supported for local execution
        # User must use :partition format
        raise ValueError(
            f"Invalid SLURM URI format: '{slurm_uri}'. "
            "For local execution, use format: slurm://:partition/script (note the colon before partition)"
        )

    if not partition:
        raise ValueError(
            f"Invalid SLURM URI: partition is required. "
            "Expected format: slurm://[user@host]:partition/script or slurm://:partition/script"
        )

    return host, port, username, password, partition, script


def run_slurm_calculation(
    working_dir: Path,
    slurm_uri: str,
    model: Dict,
    timeout: int = None,
    input_files_list: List[str] = None,
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run calculation via SLURM workload manager

    Args:
        working_dir: Directory containing input files
        slurm_uri: SLURM URI (e.g., "slurm://partition/script" or "slurm://user@host:partition/script")
        model: Model definition dict
        timeout: Timeout in seconds (None resolves via model["timeout"], then FZ_RUN_TIMEOUT config default, 3600)
        input_files_list: List of input file names in order (from .fz_hash)
        static_entries: Pre-resolved input_static entries; only used for
            remote SLURM execution (local execution shares the filesystem, so the
            local symlink already resolves)

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
            "command": slurm_uri,
        }

    start_time = datetime.now()
    env_info = get_environment_info()

    try:
        # Parse SLURM URI
        host, port, username, password, partition, script = parse_slurm_uri(slurm_uri)

        log_info(f"SLURM calculation: partition={partition}, script={script}")

        # Check if this is local or remote SLURM execution
        if host is None:
            # Local SLURM execution
            return _run_local_slurm_calculation(
                working_dir, partition, script, model, timeout, start_time, env_info, input_files_list
            )
        else:
            # Remote SLURM execution via SSH
            if not PARAMIKO_AVAILABLE:
                return {
                    "status": "error",
                    "error": "paramiko library not available for remote SLURM. Install with: pip install paramiko",
                }

            if not username:
                # Try to get username from environment or use current user
                username = os.getenv("SSH_USER") or getpass.getuser()

            log_info(f"Remote SLURM: connecting to {username}@{host}:{port or 22}")

            return _run_remote_slurm_calculation(
                working_dir, host, port or 22, username, password, partition, script,
                model, timeout, start_time, env_info, input_files_list, static_entries=static_entries
            )

    except Exception as e:
        return {"status": "error", "error": f"SLURM calculation failed: {str(e)}"}


def _run_local_slurm_calculation(
    working_dir: Path,
    partition: str,
    script: str,
    model: Dict,
    timeout: Optional[int],
    start_time: datetime,
    env_info: Dict,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run SLURM calculation locally using srun

    Args:
        working_dir: Directory containing input files
        partition: SLURM partition name
        script: Script to execute via srun
        model: Model definition dict
        timeout: Timeout in seconds
        start_time: Calculation start time
        env_info: Environment information
        input_files_list: List of input file names in order

    Returns:
        Dict containing calculation results and status
    """
    from ..core import is_interrupted, fzo

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": f"srun --partition={partition} {script}",
        }

    original_cwd = os.getcwd()
    process = None

    try:
        os.chdir(working_dir)

        # Build arguments from input files list
        input_argument = " ".join(input_files_list) if input_files_list else "."

        # Construct srun command
        # Use --partition for partition and execute the script
        full_command = f"srun --partition={partition} {script} {input_argument}"

        log_info(f"Running SLURM command: {full_command}")

        # Prepare output files
        out_file_path = working_dir / "out.txt"
        err_file_path = working_dir / "err.txt"

        with open(out_file_path, "w") as out_file, open(err_file_path, "w") as err_file:
            # Start process with Popen to allow interrupt handling
            process = run_command(
                full_command,
                shell=True,
                stdout=out_file,
                stderr=err_file,
                cwd=working_dir,
                use_popen=True,
            )

            # Poll process and check for interrupts
            poll_interval = 0.5  # Poll every 500ms
            elapsed_time = 0.0

            while process.poll() is None:
                # Check if user requested interrupt
                if is_interrupted():
                    log_warning(f"⚠️  Interrupt detected, terminating SLURM job...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        log_warning(f"⚠️  Process didn't terminate, killing...")
                        process.kill()
                        process.wait()
                    raise KeyboardInterrupt("SLURM job interrupted by user")

                # Check for timeout
                if timeout is not None and elapsed_time >= timeout:
                    raise subprocess.TimeoutExpired(full_command, timeout)

                # Sleep briefly before next poll
                time.sleep(poll_interval)
                elapsed_time += poll_interval

            result = process

        # Small delay to ensure streams are closed
        time.sleep(0.01)

        # Create enhanced log file
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        log_file_path = working_dir / "log.txt"
        with open(log_file_path, "w") as log_file:
            log_file.write(f"Command: {full_command}\n")
            log_file.write(f"Exit code: {result.returncode}\n")
            log_file.write(f"SLURM partition: {partition}\n")
            log_file.write(f"Time start: {start_time.isoformat()}\n")
            log_file.write(f"Time end: {end_time.isoformat()}\n")
            log_file.write(f"Execution time: {execution_time:.3f} seconds\n")
            log_file.write(f"User: {env_info['user']}\n")
            log_file.write(f"Hostname: {env_info['hostname']}\n")
            log_file.write(f"Operating system: {env_info['operating_system']}\n")
            log_file.write(f"Platform: {env_info['platform']}\n")
            log_file.write(f"Working directory: {working_dir}\n")
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

            # Classify the error to provide a human-readable message
            error_message = classify_error(
                stderr=stderr_content,
                exit_code=result.returncode,
                command=full_command,
                protocol="slurm",
            )

            return {
                "status": "failed",
                "exit_code": result.returncode,
                "error": error_message,
                "stderr": stderr_content,
                "command": full_command,
            }

        # Parse output
        output_results = fzo(working_dir, model)

        # Convert DataFrame to dict if needed
        if hasattr(output_results, "to_dict"):
            output_dict = output_results.iloc[0].to_dict()
        else:
            output_dict = output_results

        # Propagate _output_error from fzo if present
        output_error = output_dict.pop("_output_error", None)

        output_dict["status"] = "done"
        output_dict["calculator"] = f"slurm://{partition}"
        output_dict["command"] = full_command

        # If output parsing had errors, report them
        if output_error:
            output_dict["error"] = f"Missing output: {output_error}"

        return output_dict

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "error": f"SLURM job timed out after {timeout} seconds on partition '{partition}'",
            "command": f"srun --partition={partition} {script}",
        }
    except KeyboardInterrupt:
        if process and process.poll() is None:
            log_warning(f"⚠️  Terminating SLURM job due to interrupt...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log_warning(f"⚠️  Job didn't terminate, killing...")
                process.kill()
                process.wait()
        return {
            "status": "interrupted",
            "error": "SLURM calculation interrupted by user",
            "command": f"srun --partition={partition} {script}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "command": f"srun --partition={partition} {script}",
        }
    finally:
        os.chdir(original_cwd)


def _run_remote_slurm_calculation(
    working_dir: Path,
    host: str,
    port: int,
    username: str,
    password: Optional[str],
    partition: str,
    script: str,
    model: Dict,
    timeout: Optional[int],
    start_time: datetime,
    env_info: Dict,
    input_files_list: List[str] = None,
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run SLURM calculation on remote host via SSH

    Args:
        working_dir: Local directory containing input files
        host: Remote SSH host
        port: SSH port
        username: SSH username
        password: SSH password (optional)
        partition: SLURM partition name
        script: Script to execute via srun
        model: Model definition dict
        timeout: Timeout in seconds
        start_time: Calculation start time
        env_info: Local environment information
        input_files_list: List of input file names in order
        static_entries: Pre-resolved input_static entries, explicitly
            transferred (relative ones only - see transfer_static_files_to_remote_sftp)

    Returns:
        Dict containing calculation results and status
    """
    from ..core import is_interrupted

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": f"srun --partition={partition} {script}",
        }

    # Validate connection security
    security_info = validate_ssh_connection_security(host, username, password)
    for warning in security_info["warnings"]:
        log_warning(f"Security Warning: {warning}")

    log_info(f"Connecting to SSH for SLURM: {username}@{host}:{port}")

    ssh_client = None
    try:
        # Create SSH client
        ssh_client = paramiko.SSHClient()

        # Set appropriate host key policy
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
            "timeout": 30 if timeout is None else min(timeout, 30),
        }

        if password:
            connect_kwargs["password"] = password
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False
        else:
            connect_kwargs["look_for_keys"] = True
            connect_kwargs["allow_agent"] = True

        ssh_client.connect(**connect_kwargs)

        # Set keepalive
        transport = ssh_client.get_transport()
        if transport:
            transport.set_keepalive(config.ssh_keepalive)

        # Create SFTP client
        sftp = ssh_client.open_sftp()

        # Create remote temporary directory
        try:
            stdin, stdout, stderr = ssh_client.exec_command("pwd", timeout=10)
            remote_root_dir = stdout.read().decode("utf-8").strip()
        except Exception as e:
            log_warning(f"Could not determine remote root directory, defaulting to ~/: {e}")
            remote_root_dir = "~"

        # Create unique remote directory
        local_dir_identifier = working_dir.name
        unique_id = uuid.uuid4().hex[:8]
        remote_temp_dir = f"{remote_root_dir}/.fz/tmp/fz_slurm_{local_dir_identifier}_{unique_id}"

        ssh_client.exec_command(f"mkdir -p {remote_temp_dir}")
        log_info(f"Created remote directory: {remote_temp_dir}")
        log_info(f"🖥️  SLURM calculation on remote: {username}@{host}:{remote_temp_dir}")

        try:
            # Transfer input files to remote
            _transfer_files_to_remote(sftp, working_dir, remote_temp_dir)
            transfer_static_files_to_remote_sftp(sftp, static_entries, remote_temp_dir)

            # Execute SLURM command on remote
            result = _execute_remote_slurm_command(
                ssh_client,
                partition,
                script,
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
                    if hasattr(output_results, "to_dict"):
                        output_dict = output_results.iloc[0].to_dict()
                    else:
                        output_dict = output_results

                    # Propagate _output_error from fzo if present
                    output_error = output_dict.pop("_output_error", None)
                    result.update(output_dict)
                    result["calculator"] = f"slurm://{host}:{partition}"
                    result["command"] = f"srun --partition={partition} {script}"
                    if output_error:
                        result["error"] = f"Missing output on remote SLURM node: {output_error}"
                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    result["error"] = f"Output parsing failed after successful remote SLURM execution: {e}"

            if "command" not in result:
                result["command"] = f"srun --partition={partition} {script}"

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
        return {"status": "error", "error": f"Remote SLURM calculation failed: {str(e)}"}
    finally:
        if ssh_client:
            try:
                ssh_client.close()
            except:
                pass


def _execute_remote_slurm_command(
    ssh_client,
    partition: str,
    script: str,
    remote_dir: str,
    local_dir: Path,
    timeout: int,
    start_time: datetime,
    env_info: Dict,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Execute SLURM command on remote server with interrupt handling

    Args:
        ssh_client: SSH client connection
        partition: SLURM partition name
        script: Script to execute
        remote_dir: Remote directory path
        local_dir: Local directory path
        timeout: Timeout in seconds
        start_time: Start time of execution
        env_info: Environment information
        input_files_list: List of input file names in order

    Returns:
        Dict with execution results
    """
    from ..core import is_interrupted

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": f"srun --partition={partition} {script}",
        }

    # Build arguments from input files list
    input_argument = " ".join(input_files_list) if input_files_list else "."

    # Construct full SLURM command
    full_command = f"cd {remote_dir} && srun --partition={partition} {script} {input_argument}"

    log_info(f"Executing remote SLURM command: {full_command}")

    # Execute command
    command_start_time = datetime.now()
    stdin, stdout, stderr = ssh_client.exec_command(full_command, timeout=timeout)

    # Get the channel for polling
    channel = stdout.channel

    # Poll for completion with interrupt checking
    poll_interval = 0.5
    elapsed_time = 0.0

    try:
        while not channel.exit_status_ready():
            # Check if user requested interrupt
            if is_interrupted():
                log_warning(f"⚠️  Interrupt detected, terminating remote SLURM job...")
                try:
                    channel.send('\x03')  # Send Ctrl+C
                    time.sleep(0.5)

                    if not channel.exit_status_ready():
                        # Try to cancel the SLURM job
                        # Note: This is a best-effort attempt. In production, you might want to
                        # track the SLURM job ID and use scancel
                        kill_cmd = f"pkill -P $(pgrep -f 'srun.*{partition}')"
                        try:
                            ssh_client.exec_command(kill_cmd, timeout=2)
                        except:
                            pass
                except Exception as e:
                    log_warning(f"⚠️  Could not terminate remote SLURM job: {e}")

                raise KeyboardInterrupt("Remote SLURM job interrupted by user")

            # Check for timeout
            if timeout is not None and elapsed_time >= timeout:
                log_warning(f"⚠️  Remote SLURM job timeout after {timeout}s")
                try:
                    channel.send('\x03')
                    time.sleep(0.5)
                except:
                    pass
                return {
                    "status": "timeout",
                    "error": f"SLURM job timed out after {timeout} seconds",
                    "command": full_command,
                }

            time.sleep(poll_interval)
            elapsed_time += poll_interval

        # Get exit status
        exit_code = channel.recv_exit_status()
        command_end_time = datetime.now()

    except KeyboardInterrupt:
        try:
            channel.close()
        except:
            pass
        return {
            "status": "interrupted",
            "error": "Remote SLURM calculation interrupted by user",
            "command": full_command,
        }

    # Get output
    stdout_data = stdout.read().decode("utf-8")
    stderr_data = stderr.read().decode("utf-8")

    # Calculate timing
    total_execution_time = (command_end_time - start_time).total_seconds()
    command_execution_time = (command_end_time - command_start_time).total_seconds()

    # Get remote system information
    remote_info_cmd = "hostname; whoami; pwd; uname -s; uname -a"
    try:
        _, remote_stdout, _ = ssh_client.exec_command(remote_info_cmd, timeout=10)
        remote_info_lines = remote_stdout.read().decode("utf-8").strip().split("\n")
        remote_hostname = remote_info_lines[0] if len(remote_info_lines) > 0 else "unknown"
        remote_user = remote_info_lines[1] if len(remote_info_lines) > 1 else "unknown"
        remote_pwd = remote_info_lines[2] if len(remote_info_lines) > 2 else "unknown"
        remote_os = remote_info_lines[3] if len(remote_info_lines) > 3 else "unknown"
        remote_platform = remote_info_lines[4] if len(remote_info_lines) > 4 else "unknown"
    except:
        remote_hostname = remote_user = remote_pwd = remote_os = remote_platform = "unknown"

    # Create enhanced log files remotely
    log_command = f"""cd {remote_dir}

# Create enhanced log.txt
cat > log.txt << 'EOF'
Command: {full_command}
Exit code: {exit_code}
SLURM partition: {partition}
Time start: {start_time.isoformat()}
Time end: {command_end_time.isoformat()}
Command execution time: {command_execution_time:.3f} seconds
Total execution time: {total_execution_time:.3f} seconds
Local user: {env_info.get('user', 'unknown')}
Local hostname: {env_info.get('hostname', 'unknown')}
Local operating system: {env_info.get('operating_system', 'unknown')}
Local working directory: {env_info.get('working_dir', 'unknown')}
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
            command=f"srun --partition={partition} {script}",
            protocol="slurm",
        )
        return {
            "status": "failed",
            "exit_code": exit_code,
            "error": error_message,
            "stderr": stderr_data,
            "command": full_command,
        }

    return {"status": "done", "stdout": stdout_data, "stderr": stderr_data}


class SlurmCalculator(Calculator):
    scheme = "slurm"

    def run(self, working_dir, calculator_uri, model, timeout=None,
            original_input_was_dir=False, original_cwd=None,
            input_files_list=None, static_entries=None):
        return run_slurm_calculation(
            working_dir, calculator_uri, model, timeout, input_files_list,
            static_entries=static_entries,
        )
