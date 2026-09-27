"""Error classification for calculator failures (sh, ssh, slurm, funz)."""

import re
import platform
from typing import Optional



# "bash: foo: command not found", "sh: 1: foo: not found",
# "bash: ./run.sh: No such file or directory" (exit code 127 only),
# "/bin/sh: line 1: foo: command not found"
_SHELL_MISSING_COMMAND_RE = re.compile(
    r"^(?:\S*/)?(?:ba|da|z|k)?sh(?:\.exe)?: (?:line )?(?:\d+: )?"
    r"([^:\n]+): (command not found|not found|no such file or directory)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# cmd.exe report of a missing command, capturing its name:
# "'grep' is not recognized as an internal or external command, ..."
_CMD_NOT_RECOGNIZED_RE = re.compile(
    r"^'?([^'\n]+?)'? is not recognized as an internal or external command",
    re.IGNORECASE | re.MULTILINE,
)

# Exit codes meaning "command not found": 127 (POSIX shells), 9009 (cmd.exe),
# 3 (cmd.exe ERROR_PATH_NOT_FOUND, for a command given with a wrong path)
_MISSING_COMMAND_EXIT_CODES = (127, 9009, 3)


def _missing_command(stderr: str, exit_code: int, cmd_name: str,
                     windows: bool = False) -> Optional[str]:
    """
    Name of the command or script the shell could not find, or None.

    Only messages the shell itself emits for a missing command count: a bare
    "not found" / "no such file or directory" may come from the simulation
    code (e.g. "library not found", a missing data file) and then says nothing
    about the command, so it counts only with the shell's exit code 127.

    With windows=True (local sh:// runs), cmd.exe messages are also recognized:
    "... is not recognized as an internal or external command" always, and
    "The system cannot find the path specified" only with a missing-command exit
    code, since programs print it for missing data paths too.
    """
    stderr_lower = stderr.lower() if stderr else ""
    match = _SHELL_MISSING_COMMAND_RE.search(stderr or "")
    if match and match.group(2).lower() == "no such file or directory" and exit_code != 127:
        match = None  # e.g. "bash: input.txt: No such file..." from a redirection
    if match:
        return match.group(1)
    if "command not found" in stderr_lower:
        return cmd_name
    if exit_code == 127 and any(p in stderr_lower for p in ("not found", "no such file or directory")):
        return cmd_name
    if windows:
        match = _CMD_NOT_RECOGNIZED_RE.search(stderr or "")
        if match:
            return match.group(1)
        if "is not recognized as" in stderr_lower:
            return cmd_name
        if exit_code in _MISSING_COMMAND_EXIT_CODES and "cannot find the path" in stderr_lower:
            return cmd_name
    return None


def _classify_sh_error(stderr: str, exit_code: int, command: str) -> Optional[str]:
    """
    Classify errors specific to the sh:// protocol (local shell execution).

    Handles Unix and Windows-specific shell errors including bash discovery,
    line ending issues, permission problems, and command resolution.

    Returns:
        Error message string if a sh-specific error is identified, None otherwise.
    """
    stderr_lower = stderr.lower() if stderr else ""
    cmd_name = command.split()[0] if command else "unknown"

    # --- Windows: line ending issues (\\r in scripts) ---
    if any(pattern in stderr_lower for pattern in [
        "\\r",
        "\r: command not found",
        "\r: no such file",
        "bad interpreter",
        "cannot execute binary file",
    ]):
        return (
            f"Script line ending error: '{cmd_name}' appears to have Windows-style "
            f"line endings (\\r\\n). Convert to Unix line endings (\\n) using "
            f"dos2unix or similar tool. "
            f"stderr: {stderr.strip()}"
        )

    # --- Windows: bash not found / not available ---
    if any(pattern in stderr_lower for pattern in [
        "bash: not found",
        "bash.exe: not found",
        "no bash found",
        "winerror 2",       # Windows: file not found in subprocess
        "winerror 193",     # Windows: not a valid Win32 application
    ]):
        return (
            f"Bash not found on Windows. Install MSYS2 (recommended), "
            f"Git for Windows, or set FZ_SHELL_PATH to a directory containing bash. "
            f"stderr: {stderr.strip()}"
        )

    # --- Command not found (local) ---
    missing = _missing_command(stderr, exit_code, cmd_name, windows=True)
    if missing:
        return (
            f"Command not found locally: '{missing}'. "
            f"Check that the command is installed and available in PATH. "
            f"stderr: {stderr.strip()}"
        )

    # --- Permission denied (local) ---
    if any(pattern in stderr_lower for pattern in [
        "permission denied",
        "operation not permitted",
        "access is denied",                  # Windows
        "is not a valid win32 application",  # Windows: wrong binary format
    ]):
        hint = "Check file permissions (chmod +x) and user privileges."
        if platform.system() == "Windows":
            hint = (
                "On Windows, chmod is a no-op under MSYS2. "
                "Ensure the script starts with a shebang (#!/bin/bash) "
                "and is invoked via 'bash script.sh' rather than './script.sh'."
            )
        return (
            f"Permission denied when executing '{cmd_name}'. {hint} "
            f"stderr: {stderr.strip()}"
        )

    # --- Script syntax errors ---
    if any(pattern in stderr_lower for pattern in [
        "syntax error",
        "unexpected token",
        "parse error",
    ]):
        return (
            f"Script syntax error in '{cmd_name}'. "
            f"stderr: {stderr.strip()}"
        )

    # --- Exit code 126: found but not executable ---
    if exit_code == 126:
        if platform.system() == "Windows":
            return (
                f"Command '{cmd_name}' found but not executable (exit code 126). "
                f"On Windows/MSYS2, chmod +x is a no-op. Use 'bash {cmd_name}' "
                f"instead of './{cmd_name}' to run shell scripts. "
                f"stderr: {stderr.strip()}"
            )
        return (
            f"Command '{cmd_name}' found but not executable (exit code 126). "
            f"Check file permissions (chmod +x). "
            f"stderr: {stderr.strip()}"
        )

    # --- Exit code 127: command not found ---
    if exit_code == 127:
        return (
            f"Command not found locally: '{cmd_name}' (exit code 127). "
            f"Check that the command is installed and available in PATH. "
            f"stderr: {stderr.strip()}"
        )

    return None


def _classify_ssh_error(stderr: str, exit_code: int, command: str) -> Optional[str]:
    """
    Classify errors specific to the ssh:// protocol (remote execution via SSH).

    Handles connection, authentication, host key, and remote execution errors.

    Returns:
        Error message string if an SSH-specific error is identified, None otherwise.
    """
    stderr_lower = stderr.lower() if stderr else ""
    cmd_name = command.split()[0] if command else "unknown"

    # --- SSH connection errors ---
    if any(pattern in stderr_lower for pattern in [
        "connection refused",
        "connection timed out",
        "connection reset",
        "no route to host",
        "network is unreachable",
    ]):
        return f"SSH connection error: {stderr.strip()}"

    # --- SSH authentication errors ---
    if any(pattern in stderr_lower for pattern in [
        "authentication failed",
        "auth fail",
        "permission denied (publickey",
        "no acceptable kex",
        "unable to authenticate",
    ]):
        return (
            f"SSH authentication failed. Check username, password, or SSH key. "
            f"stderr: {stderr.strip()}"
        )

    # --- Host key errors ---
    if any(pattern in stderr_lower for pattern in [
        "host key verification failed",
        "host key for",
        "known_hosts",
        "offending key",
    ]):
        return (
            f"SSH host key verification failed. The remote host's key is "
            f"unknown or has changed. Review and update ~/.ssh/known_hosts. "
            f"stderr: {stderr.strip()}"
        )

    # --- SFTP / file transfer errors ---
    if any(pattern in stderr_lower for pattern in [
        "sftp",
        "file transfer failed",
        "no such file",
        "failure" if "sftp" in stderr_lower else "",
    ]):
        if "sftp" in stderr_lower or "file transfer" in stderr_lower:
            return (
                f"SSH file transfer (SFTP) error. Check that the remote directory "
                f"is accessible and has sufficient disk space. "
                f"stderr: {stderr.strip()}"
            )

    # --- Remote command not found ---
    missing = _missing_command(stderr, exit_code, cmd_name)
    if missing:
        return (
            f"Command not found on remote server: '{missing}'. "
            f"Check that the command is installed and available in PATH on the remote host. "
            f"stderr: {stderr.strip()}"
        )

    # --- Remote permission denied ---
    if any(pattern in stderr_lower for pattern in [
        "permission denied",
        "operation not permitted",
    ]):
        return (
            f"Permission denied on remote server when executing '{cmd_name}'. "
            f"Check file permissions (chmod +x) and user privileges on the remote host. "
            f"stderr: {stderr.strip()}"
        )

    # --- Exit code 127: command not found on remote ---
    if exit_code == 127:
        return (
            f"Command not found on remote server: '{cmd_name}' (exit code 127). "
            f"Check that the command is installed and available in PATH on the remote host. "
            f"stderr: {stderr.strip()}"
        )

    # --- Exit code 126: not executable on remote ---
    if exit_code == 126:
        return (
            f"Command '{cmd_name}' found but not executable on remote server (exit code 126). "
            f"Check file permissions (chmod +x) on the remote host. "
            f"stderr: {stderr.strip()}"
        )

    return None


def _classify_slurm_error(stderr: str, exit_code: int, command: str) -> Optional[str]:
    """
    Classify errors specific to the slurm:// protocol (SLURM workload manager).

    Handles partition, account, resource allocation, and job submission errors.
    For remote SLURM, SSH errors are handled by the SSH classifier.

    Returns:
        Error message string if a SLURM-specific error is identified, None otherwise.
    """
    stderr_lower = stderr.lower() if stderr else ""
    cmd_name = command.split()[0] if command else "unknown"

    # --- SLURM partition errors ---
    if any(pattern in stderr_lower for pattern in [
        "invalid partition",
        "partition not available",
        "invalid partition name",
    ]):
        return (
            f"SLURM partition error. The requested partition does not exist or "
            f"is not available. Use 'sinfo' to list available partitions. "
            f"stderr: {stderr.strip()}"
        )

    # --- SLURM account errors ---
    if any(pattern in stderr_lower for pattern in [
        "invalid account",
        "invalid account or account/partition",
    ]):
        return (
            f"SLURM account error. The specified account is invalid or you do "
            f"not have access. Check your SLURM account with 'sacctmgr'. "
            f"stderr: {stderr.strip()}"
        )

    # --- SLURM resource allocation errors ---
    if any(pattern in stderr_lower for pattern in [
        "unable to allocate resources",
        "requested node configuration is not available",
        "job submit/allocate failed",
    ]):
        return (
            f"SLURM resource allocation failed. The cluster may be full or "
            f"the requested resources are not available. Check cluster status with 'sinfo'. "
            f"stderr: {stderr.strip()}"
        )

    # --- SLURM QOS errors ---
    if any(pattern in stderr_lower for pattern in [
        "invalid qos",
        "qos not permitted",
    ]):
        return (
            f"SLURM QOS error. The requested Quality of Service is invalid or "
            f"not permitted for your account. "
            f"stderr: {stderr.strip()}"
        )

    # --- SLURM node failures ---
    if any(pattern in stderr_lower for pattern in [
        "node failure",
        "node_fail",
        "nodes are not ready",
    ]):
        return (
            f"SLURM node failure. One or more compute nodes are unavailable. "
            f"Check node status with 'sinfo -N'. "
            f"stderr: {stderr.strip()}"
        )

    # --- srun/sbatch general errors ---
    if any(pattern in stderr_lower for pattern in [
        "sbatch: error",
        "srun: error",
    ]):
        return f"SLURM error: {stderr.strip()}"

    # --- Remote command not found (SLURM runs on remote) ---
    missing = _missing_command(stderr, exit_code, cmd_name)
    if missing:
        return (
            f"Command not found on remote server: '{missing}'. "
            f"Check that the command is installed and available in PATH on the SLURM node. "
            f"stderr: {stderr.strip()}"
        )

    # --- Permission denied on remote ---
    if any(pattern in stderr_lower for pattern in [
        "permission denied",
        "operation not permitted",
    ]):
        return (
            f"Permission denied on remote server when executing '{cmd_name}'. "
            f"Check file permissions (chmod +x) on the SLURM node. "
            f"stderr: {stderr.strip()}"
        )

    # --- Exit code 127: command not found ---
    if exit_code == 127:
        return (
            f"Command not found on remote server: '{cmd_name}' (exit code 127). "
            f"Check that the command is installed and available in PATH on the SLURM node. "
            f"stderr: {stderr.strip()}"
        )

    return None


def _classify_funz_error(stderr: str, exit_code: int, command: str) -> Optional[str]:
    """
    Classify errors specific to the funz:// protocol (Funz server communication).

    Handles UDP discovery, calculator reservation, protocol communication,
    and code availability errors.

    Returns:
        Error message string if a Funz-specific error is identified, None otherwise.
    """
    stderr_lower = stderr.lower() if stderr else ""

    # --- No calculator found (UDP discovery timeout) ---
    if any(pattern in stderr_lower for pattern in [
        "no calculator found",
        "udp discovery",
    ]):
        return (
            f"No Funz calculator found. Ensure a Funz calculator is running and "
            f"broadcasting on the expected UDP port. "
            f"stderr: {stderr.strip()}"
        )

    # --- Reservation errors ---
    if any(pattern in stderr_lower for pattern in [
        "reservation failed",
        "failed to reserve",
        "calculator reservation",
    ]):
        return (
            f"Funz calculator reservation failed. The calculator may be busy "
            f"or unavailable. Try again later or start additional calculators. "
            f"stderr: {stderr.strip()}"
        )

    # --- Case creation errors ---
    if "failed to create new case" in stderr_lower:
        return (
            f"Funz failed to create a new case on the calculator. "
            f"Check calculator logs for details. "
            f"stderr: {stderr.strip()}"
        )

    # --- Code not available ---
    if any(pattern in stderr_lower for pattern in [
        "code not available",
        "code not found",
        "unknown code",
    ]):
        return (
            f"Requested simulation code not available on the Funz calculator. "
            f"Check that the calculator supports the requested code. "
            f"stderr: {stderr.strip()}"
        )

    # --- TCP connection errors (after UDP discovery) ---
    if any(pattern in stderr_lower for pattern in [
        "connection refused",
        "connection timed out",
        "connection reset",
    ]):
        return (
            f"Funz TCP connection error after UDP discovery. The calculator was "
            f"found but the TCP connection failed. It may have gone offline. "
            f"stderr: {stderr.strip()}"
        )

    # --- Protocol response errors ---
    if any(pattern in stderr_lower for pattern in [
        "protocol error",
        "unexpected response",
        "invalid response",
    ]):
        return (
            f"Funz protocol communication error. The calculator returned an "
            f"unexpected response. Check protocol version compatibility. "
            f"stderr: {stderr.strip()}"
        )

    return None


def _classify_common_error(stderr: str, exit_code: int, command: str, protocol: str) -> str:
    """
    Classify errors common to all protocols (timeout, signals, OOM, disk, etc.).

    This is the fallback classifier called after protocol-specific classification
    returns None.

    Returns:
        A descriptive error message (always returns a string, never None).
    """
    stderr_lower = stderr.lower() if stderr else ""
    cmd_name = command.split()[0] if command else "unknown"
    location = "on remote server" if protocol in ("ssh", "slurm") else "locally"

    # --- Missing output file / output parsing failure (check before input file) ---
    if any(pattern in stderr_lower for pattern in [
        "output file not found",
        "no output produced",
        "missing output",
        "expected output",
        "output.txt: no such file",
    ]):
        return (
            f"Missing output file: the calculation did not produce expected output. "
            f"stderr: {stderr.strip()}"
        )

    # --- Missing input file ---
    if any(pattern in stderr_lower for pattern in [
        "no such file or directory",
        "cannot open",
        "failed to open",
        "input file not found",
        "file not found",
        "cannot find the file specified",   # Windows
    ]) and "command not found" not in stderr_lower:
        return (
            f"Input file not found {location}. "
            f"Check that all required input files exist and are accessible. "
            f"stderr: {stderr.strip()}"
        )

    # --- Out of memory ---
    if any(pattern in stderr_lower for pattern in [
        "out of memory",
        "cannot allocate memory",
        "killed",
        "oom",
        "memory allocation failed",
    ]):
        return (
            f"Process ran out of memory or was killed. "
            f"stderr: {stderr.strip()}"
        )

    # --- Disk / filesystem errors ---
    if any(pattern in stderr_lower for pattern in [
        "no space left on device",
        "disk quota exceeded",
        "read-only file system",
    ]):
        return (
            f"Filesystem error: {stderr.strip()}"
        )

    # --- Timeout (signal 124 or exit code 124) ---
    if exit_code == 124 or "timed out" in stderr_lower or "timeout" in stderr_lower:
        return (
            f"Command timed out. "
            f"stderr: {stderr.strip()}"
        )

    # --- Signal-based termination ---
    if exit_code is not None and exit_code < 0:
        import signal as sig
        try:
            signal_name = sig.Signals(-exit_code).name
        except (ValueError, AttributeError):
            signal_name = str(-exit_code)
        return (
            f"Process terminated by signal {signal_name} (exit code {exit_code}). "
            f"stderr: {stderr.strip()}"
        )

    # --- Fallback: generic error with as much context as possible ---
    parts = [f"Command failed with exit code {exit_code}"]
    if stderr and stderr.strip():
        parts.append(f"stderr: {stderr.strip()}")
    return ". ".join(parts)


def classify_error(stderr: str, exit_code: int = None, command: str = None, protocol: str = "sh") -> str:
    """
    Classify a calculation error based on stderr content and exit code,
    returning a human-readable error message.

    Dispatches to protocol-specific classifiers first, then falls back to
    common error classification.

    Args:
        stderr: Standard error output from the failed command
        exit_code: Process exit code (if available)
        command: The command that was executed (if available)
        protocol: The protocol used (sh, ssh, slurm, funz)

    Returns:
        A descriptive error message explaining the likely cause of failure
    """
    classifiers = {
        "sh": _classify_sh_error,
        "ssh": _classify_ssh_error,
        "slurm": _classify_slurm_error,
        "funz": _classify_funz_error,
    }

    classifier = classifiers.get(protocol)
    if classifier:
        result = classifier(stderr, exit_code, command)
        if result:
            return result

    return _classify_common_error(stderr, exit_code, command, protocol)
