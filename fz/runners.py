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
import uuid

from .logging import log_error, log_warning, log_info, log_debug
from .config import get_config
from .shell import run_command, replace_commands_in_string
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


def _validate_calculator_uri(calculator_uri: str) -> None:
    """
    Validate calculator URI format and scheme

    Args:
        calculator_uri: Calculator URI string to validate

    Raises:
        ValueError: If URI has invalid format or unsupported scheme
    """
    if not calculator_uri:
        raise ValueError("Calculator URI cannot be empty")

    if not isinstance(calculator_uri, str):
        raise TypeError(f"Calculator URI must be a string, got {type(calculator_uri).__name__}")

    # Check if it has a scheme
    if "://" not in calculator_uri:
        raise ValueError(
            f"Invalid calculator URI format: '{calculator_uri}'. "
            "URI must include a scheme (e.g., 'sh://', 'ssh://', 'cache://', 'slurm://'). "
            "If using a calculator alias, ensure it exists in .fz/calculators/"
        )

    # Extract and validate scheme
    scheme = calculator_uri.split("://", 1)[0].lower()
    supported_schemes = ["sh", "ssh", "cache", "slurm", "funz"]

    if scheme not in supported_schemes:
        raise ValueError(
            f"Unsupported calculator scheme: '{scheme}'. "
            f"Supported schemes: {', '.join(supported_schemes)}"
        )

    # Validate SSH URI format if scheme is ssh
    if scheme == "ssh":
        try:
            parse_ssh_uri(calculator_uri)
        except ValueError as e:
            raise ValueError(f"Invalid SSH calculator URI: {e}")

    # Validate SLURM URI format if scheme is slurm
    if scheme == "slurm":
        try:
            parse_slurm_uri(calculator_uri)
        except ValueError as e:
            raise ValueError(f"Invalid SLURM calculator URI: {e}")


def resolve_calculators(
    calculators: Union[str, List[str], List[Dict]], model_id: str = None
) -> List[str]:
    """
    Resolve calculator aliases to URI strings and validate them

    Args:
        calculators: Calculator specifications (string, list of strings, or list of dicts)
        model_id: Optional model ID for model-specific calculator commands

    Returns:
        List of validated calculator URI strings

    Raises:
        ValueError: If calculator URI is invalid or alias not found
        TypeError: If calculators have invalid types
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
            calculators = ["cache://_"] + calc_files
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
                uri = f"{uri}{command}"
            _validate_calculator_uri(uri)
            result.append(uri)
        elif isinstance(calc, str):
            if "://" in calc:
                # Direct URI - validate it
                _validate_calculator_uri(calc)
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
                        uri = f"{uri}{command}"
                    _validate_calculator_uri(uri)
                    result.append(uri)
                else:
                    # Alias not found - raise error with helpful message
                    raise ValueError(
                        f"Calculator alias '{calc}' not found in .fz/calculators/. "
                        f"If this is a URI, it must include a scheme (e.g., 'sh://', 'ssh://', 'cache://')"
                    )
        else:
            raise TypeError(f"Calculator must be a string or dict, got {type(calc).__name__}")
    return result


def run_calculation(
    working_dir: Path,
    calculator_uri: str,
    model: Dict,
    timeout: int = None,
    original_input_was_dir: bool = False,
    original_cwd: str = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run a single calculation on a calculator

    Args:
        working_dir: Directory containing input files
        calculator_uri: Calculator URI (e.g., "sh://command", "ssh://host/command", "slurm://partition/script")
        model: Model definition dict
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
        original_input_was_dir: Whether original input was a directory
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Use config default if timeout not specified
    if timeout is None:
        timeout = get_config().run_timeout
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

    elif base_uri.startswith("slurm://"):
        # SLURM execution (local or remote)
        return run_slurm_calculation(
            working_dir, base_uri, model, timeout, input_files_list
        )

    elif base_uri.startswith("funz://"):
        # Funz server execution
        return run_funz_calculation(
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
        # Check for both Unix (/) and Windows (\) separators
        if "/" in part or (os.name == 'nt' and "\\" in part):
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

            # On Windows, convert path to forward slashes for bash compatibility
            # MSYS2/Git Bash/WSL all expect Unix-style paths
            if os.name == 'nt':
                # Convert backslashes to forward slashes
                abs_path = abs_path.replace('\\', '/')

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
    timeout: int = None,
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
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
        original_input_was_dir: Whether original input was a directory
        original_cwd: Original working directory
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Use config default if timeout not specified
    if timeout is None:
        timeout = get_config().run_timeout
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

            # Apply shell path resolution to command if FZ_SHELL_PATH is set
            resolved_command = replace_commands_in_string(resolved_command)

            command_for_result = resolved_command
            full_command = resolved_command + f" {input_argument}"

            # Display warning if command was changed
            if was_changed:
                log_info(f"Info: sh:// command paths resolved to absolute:")
                log_info(f"  Original: {command}")
                log_info(f"  Resolved: {resolved_command}")
        else:
            # Try to infer command from model or use generic approach
            log_warning(f"Warning: No command specified for sh:// calculator, using default './{input_argument}'")
            full_command = f"./{input_argument}"
            command_for_result = None

        # Run calculation in the input directory (temp directory), files will be copied to result_dir afterwards
        working_dir = working_dir
        # Use absolute paths for output files to avoid race conditions in parallel execution
        out_file_path = working_dir / "out.txt"
        err_file_path = working_dir / "err.txt"
        log_info(f"Info: Running command: {full_command}")

        with open(out_file_path, "w") as out_file, open(err_file_path, "w") as err_file:
            # Start process with Popen to allow interrupt handling
            # Use centralized run_command that handles Windows bash and process flags
            process = run_command(
                full_command,
                shell=True,
                stdout=out_file,
                stderr=err_file,
                cwd=working_dir,
                use_popen=True,
            )

            # Poll process and check for interrupts
            # Use polling instead of blocking wait to allow interrupt handling on all platforms
            try:
                from .core import is_interrupted

                poll_interval = 0.5  # Poll every 500ms
                elapsed_time = 0.0

                while process.poll() is None:
                    # Check if user requested interrupt
                    if is_interrupted():
                        log_warning(f"⚠️  Interrupt detected, terminating process...")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            log_warning(f"⚠️  Process didn't terminate, killing...")
                            process.kill()
                            process.wait()
                        raise KeyboardInterrupt("Process interrupted by user")

                    # Check for timeout
                    if elapsed_time >= timeout:
                        raise subprocess.TimeoutExpired(full_command, timeout)

                    # Sleep briefly before next poll
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval

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
    except OSError as e:
        # Script file doesn't exist or cannot be executed - treat as failed execution (consistent across platforms)
        # OSError includes FileNotFoundError, PermissionError, etc.
        # On Windows, when trying to execute a non-existent or non-executable script via subprocess.Popen,
        # various OSError subtypes may be raised depending on the execution mode (shell=True/False)
        error_result = {"status": "failed", "error": f"Script execution failed: {str(e)}"}
        error_result["command"] = command_for_result
        return error_result
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
    timeout: int = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation via SSH

    Args:
        working_dir: Directory containing input files
        ssh_uri: SSH URI (e.g., "ssh://user:password@host:port/command")
        model: Model definition dict
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Use config default if timeout not specified
    if timeout is None:
        timeout = get_config().run_timeout

    # Import here to avoid circular imports
    from .core import is_interrupted

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


def run_slurm_calculation(
    working_dir: Path,
    slurm_uri: str,
    model: Dict,
    timeout: int = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation via SLURM workload manager

    Args:
        working_dir: Directory containing input files
        slurm_uri: SLURM URI (e.g., "slurm://partition/script" or "slurm://user@host:partition/script")
        model: Model definition dict
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Use config default if timeout not specified
    if timeout is None:
        timeout = get_config().run_timeout

    # Import here to avoid circular imports
    from .core import is_interrupted

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
                model, timeout, start_time, env_info, input_files_list
            )

    except Exception as e:
        return {"status": "error", "error": f"SLURM calculation failed: {str(e)}"}


def _run_local_slurm_calculation(
    working_dir: Path,
    partition: str,
    script: str,
    model: Dict,
    timeout: int,
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
    from .core import is_interrupted, fzo

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
                if elapsed_time >= timeout:
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

            return {
                "status": "failed",
                "exit_code": result.returncode,
                "error": f"SLURM job failed with exit code {result.returncode}",
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

        output_dict["status"] = "done"
        output_dict["calculator"] = f"slurm://{partition}"
        output_dict["command"] = full_command

        return output_dict

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
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
    timeout: int,
    start_time: datetime,
    env_info: Dict,
    input_files_list: List[str] = None,
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

    Returns:
        Dict containing calculation results and status
    """
    from .core import is_interrupted

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
            "timeout": min(timeout, 30),
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
            from .core import fzo

            if result["status"] == "done":
                try:
                    output_results = fzo(working_dir, model)
                    if hasattr(output_results, "to_dict"):
                        output_dict = output_results.iloc[0].to_dict()
                    else:
                        output_dict = output_results
                    result.update(output_dict)
                    result["calculator"] = f"slurm://{host}:{partition}"
                    result["command"] = f"srun --partition={partition} {script}"
                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    result["error"] = str(e)

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
    from .core import is_interrupted

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
            if elapsed_time >= timeout:
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
        return {"status": "failed", "exit_code": exit_code, "stderr": stderr_data}

    return {"status": "done", "stdout": stdout_data, "stderr": stderr_data}


def run_funz_calculation(
    working_dir: Path,
    funz_uri: str,
    model: Dict,
    timeout: int = None,
    input_files_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Run calculation via Funz server protocol

    Args:
        working_dir: Directory containing input files
        funz_uri: Funz URI (e.g., "funz://:<port>/<code>")
        model: Model definition dict
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Use config default if timeout not specified
    if timeout is None:
        timeout = get_config().run_timeout
    # Import here to avoid circular imports
    from .core import is_interrupted, fzo

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": funz_uri,
        }

    start_time = datetime.now()
    env_info = get_environment_info()

    # Funz protocol constants (per org.funz.Protocol in Java source)
    METHOD_RESERVE = "RESERVE"
    METHOD_UNRESERVE = "UNRESERVE"
    METHOD_PUT_FILE = "PUTFILE"
    METHOD_NEW_CASE = "NEWCASE"
    METHOD_EXECUTE = "EXECUTE"
    METHOD_ARCH_RES = "ARCHIVE"
    METHOD_GET_ARCH = "GETFILE"
    METHOD_INTERRUPT = "INTERUPT"  # Note: typo in original Java code

    RET_YES = "Y"
    RET_NO = "N"
    RET_ERROR = "E"
    RET_INFO = "I"
    RET_HEARTBEAT = "H"
    RET_SYNC = "S"

    END_OF_REQ = "/"
    ARCHIVE_FILE = "results.zip"

    try:
        # Parse Funz URI: funz://:<port>/<code>
        # Format: funz://[host]:<port>/<code>
        log_debug(f"Parsing Funz URI: {funz_uri}")

        if not funz_uri.startswith("funz://"):
            return {"status": "error", "error": "Invalid Funz URI format"}

        uri_part = funz_uri[7:]  # Remove "funz://"
        log_debug(f"URI part after 'funz://': {uri_part}")

        # Parse host:port/code
        if "/" not in uri_part:
            return {"status": "error", "error": "Funz URI must specify code: funz://:<port>/<code>"}

        connection_part, code = uri_part.split("/", 1)
        log_debug(f"Connection part: {connection_part}, Code: {code}")

        # Parse host and UDP port
        host = "localhost"  # Default to localhost
        udp_port = 0

        if ":" in connection_part:
            # host:port format
            if connection_part.startswith(":"):
                # :port format (no host)
                port_str = connection_part[1:]
                try:
                    udp_port = int(port_str)
                    log_debug(f"Parsed UDP port (localhost): {udp_port}")
                except ValueError:
                    return {"status": "error", "error": f"Invalid port number: {port_str}"}
            else:
                # host:port format
                host, port_str = connection_part.rsplit(":", 1)
                try:
                    udp_port = int(port_str)
                    log_debug(f"Parsed host:UDP port: {host}:{udp_port}")
                except ValueError:
                    return {"status": "error", "error": f"Invalid port number: {port_str}"}
        else:
            return {"status": "error", "error": "Funz URI must specify UDP port: funz://:<port>/<code>"}

        if not code:
            return {"status": "error", "error": "Funz URI must specify code"}

        log_info(f"📡 Discovering Funz calculator via UDP broadcast on port {udp_port}...")
        log_info(f"🔧 Code: {code}")
        log_debug(f"Working directory: {working_dir}")
        log_debug(f"Timeout: {timeout}s")

        # Discover TCP port via UDP broadcast
        try:
            log_debug(f"Creating UDP socket to listen on port {udp_port}")
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_sock.bind(('', udp_port))
            udp_sock.settimeout(10)  # 10 second timeout for UDP discovery

            log_debug(f"Waiting for UDP broadcast from calculator...")
            data, addr = udp_sock.recvfrom(1024)
            udp_sock.close()

            # Parse UDP broadcast data
            # Format (lines):
            # 0: calculator name
            # 1: TCP port
            # 2: secret
            # 3: OS
            # 4: status
            # 5+: available codes
            lines = data.decode('utf-8').strip().split('\n')
            log_debug(f"Received UDP broadcast from {addr}:")
            for i, line in enumerate(lines):
                log_debug(f"  Line {i}: {line}")

            if len(lines) < 2:
                return {"status": "error", "error": "Invalid UDP broadcast format"}

            tcp_port = int(lines[1])
            calculator_name = lines[0]
            available_codes = lines[6:] if len(lines) > 6 else []

            log_info(f"✅ Discovered calculator '{calculator_name}' at {host}:{tcp_port}")
            log_debug(f"Available codes: {available_codes}")

            # Verify requested code is available
            if code not in available_codes:
                log_warning(f"⚠️  Requested code '{code}' not in available codes: {available_codes}")

        except socket.timeout:
            log_error(f"❌ UDP discovery timeout - no calculator found on port {udp_port}")
            return {"status": "error", "error": f"No calculator found on UDP port {udp_port}"}
        except Exception as e:
            log_error(f"❌ UDP discovery failed: {e}")
            return {"status": "error", "error": f"UDP discovery failed: {str(e)}"}

        # Create TCP socket connection to discovered port
        log_debug(f"Creating TCP socket connection to {host}:{tcp_port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_timeout = min(timeout, 30)
        sock.settimeout(connection_timeout)
        log_debug(f"Socket timeout set to {connection_timeout}s")

        try:
            log_debug(f"Attempting TCP connection to {host}:{tcp_port}...")
            sock.connect((host, tcp_port))
            log_info(f"✅ Connected to Funz server at {host}:{tcp_port}")
            log_debug(f"Socket state: connected, local={sock.getsockname()}, remote={sock.getpeername()}")

            # Create buffered reader/writer
            sock_file = sock.makefile('rw', buffering=1, encoding='utf-8', newline='\n')
            log_debug("Socket file created with UTF-8 encoding and line buffering")

            def send_message(*lines):
                """Send a protocol message"""
                log_debug(f"→ Sending message: {lines}")
                for line in lines:
                    sock_file.write(str(line) + '\n')
                sock_file.write(END_OF_REQ + '\n')
                sock_file.flush()
                log_debug(f"→ Message sent and flushed")

            def read_response():
                """Read a protocol response until END_OF_REQ

                Returns:
                    Tuple of (status, response_lines) where:
                    - status is the first line (RET_YES, RET_NO, RET_ERROR, etc.) or None on timeout/error
                    - response_lines is the full response including status line
                """
                response = []
                line_count = 0

                # Set socket timeout for reading
                original_timeout = sock.gettimeout()
                sock.settimeout(timeout)

                try:
                    while True:
                        try:
                            line = sock_file.readline().strip()
                        except socket.timeout:
                            log_error(f"❌ Timeout waiting for response after {timeout}s")
                            sock.settimeout(original_timeout)
                            return "TIMEOUT", []

                        line_count += 1
                        log_debug(f"← Received line {line_count}: '{line}'")

                        if not line:
                            # Connection closed
                            log_warning(f"⚠️  Connection closed by server (empty line received)")
                            sock.settimeout(original_timeout)
                            return None, []

                        if line == END_OF_REQ:
                            log_debug(f"← End of response marker received (total {line_count} lines)")
                            break

                        # Handle special responses
                        if line == RET_HEARTBEAT:
                            log_debug("← Heartbeat received, ignoring")
                            continue  # Ignore heartbeats

                        if line == RET_INFO:
                            # Info message - read next line
                            info_line = sock_file.readline().strip()
                            log_info(f"ℹ️  Funz info: {info_line}")
                            continue

                        response.append(line)

                    if not response:
                        log_debug("← Empty response received")
                        sock.settimeout(original_timeout)
                        return None, []

                    log_debug(f"← Response parsed: status={response[0]}, lines={len(response)}")
                    sock.settimeout(original_timeout)
                    return response[0], response

                except Exception as e:
                    log_error(f"❌ Error reading response: {e}")
                    sock.settimeout(original_timeout)
                    return "ERROR", []

            # Step 1: Reserve calculator (two-phase protocol)
            log_info("🔒 Step 1: Reserving calculator...")

            # Phase 1: Send RESERVE command
            log_debug(f"Sending {METHOD_RESERVE} request (phase 1)")
            send_message(METHOD_RESERVE)
            ret, response = read_response()

            # Check for errors/timeout
            if ret == "TIMEOUT":
                log_error(f"❌ Reservation timed out")
                return {"status": "timeout", "error": "Calculator reservation timed out"}
            elif ret == "ERROR":
                log_error(f"❌ Error during reservation")
                return {"status": "error", "error": "Error during calculator reservation"}
            elif ret != RET_YES:
                error_msg = response[1] if len(response) > 1 else "Unknown error"
                log_error(f"❌ Calculator reservation failed: {error_msg}")
                log_debug(f"Full response: {response}")
                return {"status": "error", "error": f"Failed to reserve calculator: {error_msg}"}

            log_debug(f"✅ Phase 1 complete")

            # Phase 2: Send project code and tagged values
            tagged_values = {
                "USERNAME": getpass.getuser()
            }

            log_debug(f"Sending project code '{code}' and tagged values (phase 2)")
            # Send code
            sock_file.write(code + '\n')
            # Send number of tagged values
            sock_file.write(str(len(tagged_values)) + '\n')
            # Send each tagged value
            for key, value in tagged_values.items():
                sock_file.write(key + '\n')
                sock_file.write(str(value) + '\n')
            sock_file.flush()

            # Read phase 2 response
            ret, response = read_response()

            if ret == "TIMEOUT":
                log_error(f"❌ Reservation phase 2 timed out")
                return {"status": "timeout", "error": "Calculator reservation phase 2 timed out"}
            elif ret != RET_YES:
                error_msg = response[1] if len(response) > 1 else "Unknown error"
                log_error(f"❌ Calculator reservation phase 2 failed: {error_msg}")
                return {"status": "error", "error": f"Failed to reserve calculator (phase 2): {error_msg}"}

            # Get secret code from response (for authentication)
            # Response contains: [RET_YES, secret, ip, security]
            secret_code = response[1] if len(response) > 1 else None
            log_info(f"✅ Calculator reserved successfully")
            log_debug(f"Secret code: {secret_code}")

            try:
                # Step 2: Create new case (MUST come before uploading files!)
                # The Funz protocol requires NEW_CASE before PUT_FILE
                log_info("📝 Step 2: Creating new case...")

                # Prepare variables (must include USERNAME)
                variables = {
                    "USERNAME": getpass.getuser()
                }

                log_debug(f"Sending {METHOD_NEW_CASE} request with variables: {variables}")
                send_message(METHOD_NEW_CASE)

                # Send variable count
                sock_file.write(str(len(variables)) + '\n')

                # Send each variable
                for key, value in variables.items():
                    # Truncate multi-line values to first line
                    value_str = str(value).split('\n')[0]
                    if '\n' in str(value):
                        value_str += "..."

                    sock_file.write(key + '\n')
                    sock_file.write(value_str + '\n')

                sock_file.flush()

                # Read response
                ret, case_response = read_response()

                if ret == "TIMEOUT":
                    log_error(f"❌ New case creation timed out")
                    return {"status": "timeout", "error": "New case creation timed out"}
                elif ret != RET_YES:
                    error_msg = case_response[1] if len(case_response) > 1 else "Unknown error"
                    log_error(f"❌ Failed to create new case: {error_msg}")
                    return {"status": "error", "error": f"Failed to create new case: {error_msg}"}

                log_info(f"✅ Case created successfully")

                # Step 3: Upload input files (after NEW_CASE)
                log_info("📤 Step 3: Uploading input files...")
                files_to_upload = [item for item in working_dir.iterdir() if item.is_file()]
                log_debug(f"Found {len(files_to_upload)} files to upload")

                uploaded_count = 0
                for item in files_to_upload:
                    # Send PUT_FILE request
                    file_size = item.stat().st_size
                    relative_path = item.name

                    log_info(f"  📄 Uploading {relative_path} ({file_size} bytes)")
                    log_debug(f"Sending {METHOD_PUT_FILE} request for {relative_path}")
                    send_message(METHOD_PUT_FILE, relative_path, file_size)

                    # Wait for acknowledgment
                    ret, ack_response = read_response()
                    if ret != RET_YES:
                        log_warning(f"❌ Failed to upload {relative_path}: {ack_response}")
                        continue

                    log_debug(f"Server ready to receive {relative_path}")

                    # Send file content
                    with open(item, 'rb') as f:
                        file_data = f.read()
                        bytes_sent = sock.sendall(file_data)
                        log_debug(f"Sent {len(file_data)} bytes of file data")

                    uploaded_count += 1
                    log_debug(f"✅ Successfully uploaded {relative_path}")

                log_info(f"✅ Uploaded {uploaded_count}/{len(files_to_upload)} files")

                # Step 4: Execute calculation
                log_info(f"⚙️  Step 4: Executing calculation...")
                log_info(f"  Code: {code}")
                log_debug(f"Sending {METHOD_EXECUTE} request")
                send_message(METHOD_EXECUTE, code)

                # Read execution response (may include INFO messages)
                execution_start = datetime.now()
                log_debug(f"Execution started at {execution_start.isoformat()}")
                ret, response = read_response()

                # Check for interrupt during execution
                if is_interrupted():
                    log_warning("⚠️  Interrupt detected, sending interrupt to Funz server...")
                    send_message(METHOD_INTERRUPT, secret_code if secret_code else "")
                    raise KeyboardInterrupt("Execution interrupted by user")

                if ret == "TIMEOUT":
                    log_error(f"❌ Execution timed out after {timeout}s")
                    return {"status": "timeout", "error": f"Execution timed out after {timeout}s"}
                elif ret == "ERROR":
                    log_error(f"❌ Error during execution")
                    return {"status": "error", "error": "Error during execution"}
                elif ret != RET_YES:
                    error_msg = response[1] if len(response) > 1 else "Execution failed"
                    log_error(f"❌ Execution failed: {error_msg}")
                    log_debug(f"Full response: {response}")
                    return {"status": "failed", "error": error_msg}

                execution_end = datetime.now()
                execution_time = (execution_end - execution_start).total_seconds()

                log_info(f"✅ Execution completed in {execution_time:.2f}s")
                log_debug(f"Execution ended at {execution_end.isoformat()}")

                # Step 5: Archive results (required before GET_ARCH)
                log_info("📦 Step 5: Archiving results...")
                log_debug(f"Sending {METHOD_ARCH_RES} request")
                send_message(METHOD_ARCH_RES)
                ret, arch_response = read_response()

                if ret != RET_YES:
                    log_error(f"❌ Failed to archive results: {arch_response}")
                    return {"status": "error", "error": "Failed to archive results"}

                log_info(f"✅ Results archived successfully")

                # Step 6: Download results archive
                log_info("📥 Step 6: Downloading results...")
                log_debug(f"Sending {METHOD_GET_ARCH} request")
                send_message(METHOD_GET_ARCH)

                # Read response (should be Y\n/\n, possibly with INFO messages)
                ret, response = read_response()

                if ret == "TIMEOUT":
                    log_error(f"❌ Archive download timed out")
                    return {"status": "timeout", "error": "Archive download timed out"}
                elif ret != RET_YES:
                    error_msg = response[1] if len(response) > 1 else "Unknown error"
                    log_error(f"❌ Failed to get results archive: {error_msg}")
                    return {"status": "error", "error": f"Failed to get results archive: {error_msg}"}

                # Read lines until we find one that's all digits (the size)
                # Skip any additional protocol responses (Y, /, INFO lines, etc.)
                # This is necessary because transferArchive sends multiple Y\n/\n responses
                max_lines = 50
                archive_size = None

                try:
                    for i in range(max_lines):
                        line = sock_file.readline().strip()
                        log_debug(f"Reading size line {i}: '{line}'")

                        if not line:
                            log_error(f"❌ Connection closed while reading archive size")
                            return {"status": "error", "error": "Connection closed while reading archive size"}

                        if line.isdigit():
                            archive_size = int(line)
                            log_info(f"  Archive size: {archive_size} bytes ({archive_size/1024:.2f} KB)")
                            break
                except socket.timeout:
                    log_error(f"❌ Timeout while reading archive size")
                    return {"status": "timeout", "error": "Timeout while reading archive size"}

                if archive_size is None:
                    log_error(f"❌ Could not find archive size in {max_lines} lines")
                    return {"status": "error", "error": "Could not determine archive size"}

                # Send acknowledgment (just a line, per Java: _reader.readLine())
                log_debug(f"Sending ACK for archive transfer")
                sock_file.write("ACK\n")
                sock_file.flush()

                # Receive archive data
                archive_data = b""
                bytes_received = 0
                chunk_count = 0

                log_debug(f"Receiving archive data in chunks...")
                while bytes_received < archive_size:
                    chunk_size = min(4096, archive_size - bytes_received)
                    chunk = sock.recv(chunk_size)
                    if not chunk:
                        log_warning(f"⚠️  Connection closed before all data received ({bytes_received}/{archive_size} bytes)")
                        break
                    archive_data += chunk
                    bytes_received += len(chunk)
                    chunk_count += 1

                    # Log progress every 100 chunks or at the end
                    if chunk_count % 100 == 0 or bytes_received >= archive_size:
                        progress = (bytes_received / archive_size * 100) if archive_size > 0 else 100
                        log_debug(f"Download progress: {bytes_received}/{archive_size} bytes ({progress:.1f}%)")

                log_info(f"✅ Downloaded {bytes_received} bytes in {chunk_count} chunks")

                # Extract archive to working directory
                if archive_data:
                    import zipfile
                    import io

                    log_debug(f"Extracting ZIP archive ({len(archive_data)} bytes)")
                    try:
                        with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
                            file_list = zf.namelist()
                            log_debug(f"Archive contains {len(file_list)} files: {file_list}")
                            zf.extractall(working_dir)
                            log_info(f"✅ Extracted {len(file_list)} files to {working_dir}")
                    except Exception as e:
                        log_error(f"❌ Failed to extract archive: {e}")
                        log_debug(f"Archive data (first 100 bytes): {archive_data[:100]}")
                else:
                    log_warning("⚠️  No archive data received")

                # Create log file
                end_time = datetime.now()
                total_time = (end_time - start_time).total_seconds()

                log_file_path = working_dir / "log.txt"
                with open(log_file_path, "w") as log_file:
                    log_file.write(f"Calculator: funz://{host}:{tcp_port}/{code}\n")
                    log_file.write(f"Exit code: 0\n")
                    log_file.write(f"Time start: {start_time.isoformat()}\n")
                    log_file.write(f"Time end: {end_time.isoformat()}\n")
                    log_file.write(f"Execution time: {execution_time:.3f} seconds\n")
                    log_file.write(f"Total time: {total_time:.3f} seconds\n")
                    log_file.write(f"User: {env_info['user']}\n")
                    log_file.write(f"Hostname: {env_info['hostname']}\n")
                    log_file.write(f"Funz server: {host}:{tcp_port}\n")
                    log_file.write(f"Timestamp: {time.ctime()}\n")

                # Parse output using fzo
                try:
                    output_results = fzo(working_dir, model)

                    # Convert DataFrame to dict if needed
                    if hasattr(output_results, "to_dict"):
                        output_dict = output_results.iloc[0].to_dict()
                    else:
                        output_dict = output_results

                    output_dict["status"] = "done"
                    output_dict["calculator"] = f"funz://{host}:{tcp_port}"
                    output_dict["command"] = code

                    return output_dict

                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    return {
                        "status": "done",
                        "calculator": f"funz://{host}:{tcp_port}",
                        "command": code,
                        "error": f"Output parsing failed: {str(e)}"
                    }

            finally:
                # Step 6: Unreserve calculator
                log_info("Unreserving calculator...")
                try:
                    send_message(METHOD_UNRESERVE, secret_code if secret_code else "")
                    read_response()  # Ignore response
                except Exception as e:
                    log_warning(f"Failed to unreserve: {e}")

        finally:
            try:
                sock_file.close()
            except:
                pass

            try:
                sock.close()
            except:
                pass

    except KeyboardInterrupt:
        return {
            "status": "interrupted",
            "error": "Funz calculation interrupted by user",
            "command": code if 'code' in locals() else funz_uri,
        }

    except socket.timeout:
        return {
            "status": "timeout",
            "error": f"Connection timed out after {timeout} seconds",
            "command": code if 'code' in locals() else funz_uri,
        }

    except Exception as e:
        import traceback
        log_error(f"Funz calculation failed: {e}")
        log_debug(traceback.format_exc())
        return {
            "status": "error",
            "error": f"Funz calculation failed: {str(e)}",
            "command": code if 'code' in locals() else funz_uri,
        }

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
    from .core import is_interrupted

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
            if elapsed_time >= timeout:
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
    timeout: int = None,
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
        timeout: Timeout in seconds (None uses FZ_RUN_TIMEOUT from config, default 600)
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
