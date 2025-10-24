"""
Shell utilities for fz package: command execution and binary path resolution

Provides functionality to:
- Execute shell commands with proper bash handling for Windows
- Discover available binaries in custom shell paths
- Cache binary locations for performance
- Resolve command names to absolute paths
- Support Windows binary resolution with .exe extensions
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from contextlib import contextmanager

from .logging import log_debug, log_info, log_warning


def run_command(
    command: str,
    shell: bool = True,
    capture_output: bool = False,
    text: bool = True,
    cwd: Optional[str] = None,
    stdout=None,
    stderr=None,
    timeout: Optional[float] = None,
    use_popen: bool = False,
    **kwargs
):
    """
    Centralized function to run shell commands with proper bash handling for Windows.

    This function handles both subprocess.run and subprocess.Popen calls, automatically
    using bash on Windows when needed for shell commands.

    Args:
        command: Command string or list of command arguments
        shell: Whether to execute command through shell (default: True)
        capture_output: Whether to capture stdout/stderr (for run mode, default: False)
        text: Whether to decode output as text (default: True)
        cwd: Working directory for command execution
        stdout: File object or constant for stdout (for Popen mode)
        stderr: File object or constant for stderr (for Popen mode)
        timeout: Timeout in seconds for command execution
        use_popen: If True, returns Popen object; if False, uses run and returns CompletedProcess
        **kwargs: Additional keyword arguments to pass to subprocess

    Returns:
        subprocess.CompletedProcess if use_popen=False
        subprocess.Popen if use_popen=True

    Examples:
        # Using subprocess.run (default)
        result = run_command("echo hello", capture_output=True)
        print(result.stdout)

        # Using subprocess.Popen
        process = run_command("long_running_task", use_popen=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
    """
    # Get bash executable for Windows if needed
    from .helpers import get_windows_bash_executable

    executable = get_windows_bash_executable() if platform.system() == "Windows" else None

    # Prepare common arguments
    common_args = {
        "shell": shell,
        "cwd": cwd,
    }

    # Handle Windows-specific setup for Popen
    if platform.system() == "Windows" and use_popen:
        # Set up Windows process creation flags for proper interrupt handling
        creationflags = 0
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        elif hasattr(subprocess, 'CREATE_NO_WINDOW'):
            # Fallback for older Python versions
            creationflags = subprocess.CREATE_NO_WINDOW

        common_args["creationflags"] = creationflags

        # Handle bash executable and command modification
        if executable and isinstance(command, str):
            # Split command and replace 'bash' with executable path
            command_parts = command.split()
            command = [s.replace('bash', executable) for s in command_parts]
            common_args["shell"] = False  # Use direct execution with bash
            common_args["executable"] = None
        else:
            # Use default shell behavior
            common_args["executable"] = executable if not executable else None
    else:
        # Non-Windows or non-Popen: use executable directly
        # On Windows with shell=True, don't set executable because bash is already in PATH
        # and passing it causes subprocess issues with spaces in paths
        # Only set executable for non-shell or non-Windows cases
        if platform.system() == "Windows" and shell:
            # On Windows with shell=True, rely on PATH instead of executable parameter
            # This avoids subprocess issues with spaces in bash path
            common_args["executable"] = None
        else:
            # For non-Windows systems or non-shell execution, use the executable
            common_args["executable"] = executable

    # Merge with user-provided kwargs (allows override)
    common_args.update(kwargs)

    if use_popen:
        # Popen mode - return process object
        return subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            **common_args
        )
    else:
        # Run mode - execute and return completed process
        return subprocess.run(
            command,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            **common_args
        )


class ShellPathResolver:
    """Resolves binaries using custom shell path or system PATH"""

    def __init__(self, custom_shell_path: Optional[str] = None):
        """
        Initialize shell path resolver

        Args:
            custom_shell_path: Colon-separated (Unix) or semicolon-separated (Windows) paths.
                             If None, uses system PATH environment variable.
        """
        self.custom_shell_path = custom_shell_path
        self._binary_cache: Dict[str, Optional[str]] = {}
        self._on_windows = platform.system() == "Windows"

    def get_search_paths(self) -> List[str]:
        """
        Get list of directories to search for binaries

        Returns:
            List of directory paths to search
        """
        if self.custom_shell_path:
            # Split by appropriate separator based on OS
            separator = ';' if self._on_windows else ':'
            paths = self.custom_shell_path.split(separator)
            return [p.strip() for p in paths if p.strip()]

        # Fall back to system PATH
        path_env = os.getenv('PATH', '')
        separator = ';' if self._on_windows else ':'
        return path_env.split(separator)

    def resolve_command(self, command: str) -> Optional[str]:
        """
        Resolve command name to absolute path

        Checks cache first, then searches shell_path or system PATH.
        On Windows, tries both with and without .exe extension.

        Args:
            command: Command name (e.g., "grep", "awk")

        Returns:
            Absolute path to command if found, None otherwise
        """
        # Check cache first
        if command in self._binary_cache:
            return self._binary_cache[command]

        # Search for binary in paths
        search_paths = self.get_search_paths()

        for search_path in search_paths:
            if not search_path.strip():
                continue

            # Try direct command first
            full_path = Path(search_path) / command
            if full_path.exists() and full_path.is_file():
                resolved = str(full_path.absolute())
                self._binary_cache[command] = resolved
                log_debug(f"Resolved '{command}' to: {resolved}")
                return resolved

            # On Windows, also try with .exe extension
            if self._on_windows and not command.endswith('.exe'):
                exe_path = Path(search_path) / (command + '.exe')
                if exe_path.exists() and exe_path.is_file():
                    resolved = str(exe_path.absolute())
                    self._binary_cache[command] = resolved
                    log_debug(f"Resolved '{command}' to: {resolved}")
                    return resolved

        # Not found
        log_debug(f"Command '{command}' not found in shell path")
        self._binary_cache[command] = None
        return None

    def list_available_binaries(self) -> List[str]:
        """
        List all available binaries in shell path

        Useful for debugging and understanding what's available in custom shell paths.
        On Windows, excludes .exe extension from output for readability.

        Returns:
            Sorted list of available command names
        """
        binaries = set()
        search_paths = self.get_search_paths()

        for search_path in search_paths:
            if not search_path.strip():
                continue

            path_obj = Path(search_path)
            if not path_obj.exists() or not path_obj.is_dir():
                continue

            try:
                for item in path_obj.iterdir():
                    if item.is_file() and os.access(str(item), os.X_OK):
                        # Add binary name
                        name = item.name
                        # On Windows, remove .exe extension for display
                        if self._on_windows and name.endswith('.exe'):
                            name = name[:-4]
                        binaries.add(name)
            except (PermissionError, OSError) as e:
                log_debug(f"Could not list binaries in {search_path}: {e}")

        return sorted(list(binaries))

    def replace_commands_in_string(self, command_string: str) -> str:
        """
        Replace command names with absolute paths in a shell command string

        This function is useful for preparing model output expressions and
        local calculator scripts for execution. It identifies common shell
        commands and replaces them with their absolute paths.

        On Windows, this ensures commands are resolved from the configured
        FZ_SHELL_PATH instead of relying on system PATH.

        Args:
            command_string: Shell command string that may contain commands

        Returns:
            Modified command string with resolved paths, or original if no changes needed

        Example:
            >>> resolver = ShellPathResolver("C:\\msys64\\usr\\bin")
            >>> resolver.replace_commands_in_string("grep 'pattern' file.txt")
            "C:\\msys64\\usr\\bin\\grep.exe 'pattern' file.txt"
        """
        if not self.custom_shell_path:
            # No custom shell path, return original
            return command_string

        # List of common shell commands to replace
        common_commands = [
            'grep', 'awk', 'sed', 'cut', 'tr', 'cat', 'head', 'tail',
            'sort', 'uniq', 'wc', 'find', 'xargs', 'echo', 'printf',
            'bash', 'sh', 'gawk', 'perl', 'python', 'python3',
            'java', 'gcc', 'g++', 'make', 'cmake', 'git',
            'zip', 'unzip', 'tar', 'gzip', 'gunzip',
            'curl', 'wget', 'nc', 'ping', 'ssh', 'scp'
        ]

        modified = command_string
        for cmd in common_commands:
            resolved_path = self.resolve_command(cmd)
            if resolved_path:
                # Replace 'cmd ' (with space) to avoid partial replacements
                # Use word boundaries to be safe
                # IMPORTANT: escape resolved_path to avoid backslash issues on Windows
                import re
                pattern = r'\b' + re.escape(cmd) + r'\b'
                # Use a lambda function to properly handle backslashes in the replacement
                modified = re.sub(pattern, lambda m: resolved_path, modified)
                log_debug(f"Replaced '{cmd}' with '{resolved_path}' in command string")

        return modified

    def clear_cache(self):
        """Clear the binary resolution cache"""
        self._binary_cache.clear()
        log_debug("Cleared binary cache")


# Global resolver instance
_resolver: Optional[ShellPathResolver] = None


def get_resolver() -> ShellPathResolver:
    """
    Get the global shell path resolver instance

    Returns:
        ShellPathResolver instance initialized with FZ_SHELL_PATH if set
    """
    global _resolver
    if _resolver is None:
        from .config import get_config
        config = get_config()
        _resolver = ShellPathResolver(config.shell_path)
    return _resolver


def resolve_command(command: str) -> Optional[str]:
    """
    Resolve a command to its absolute path using global resolver

    Args:
        command: Command name (e.g., "grep")

    Returns:
        Absolute path to command if found, None otherwise
    """
    return get_resolver().resolve_command(command)


def replace_commands_in_string(command_string: str) -> str:
    """
    Replace command names with absolute paths in a shell command string

    Args:
        command_string: Shell command string

    Returns:
        Modified command string with resolved paths
    """
    return get_resolver().replace_commands_in_string(command_string)


def reinitialize_resolver():
    """Reinitialize the global resolver (useful after config reload)"""
    global _resolver
    from .config import get_config
    config = get_config()
    _resolver = ShellPathResolver(config.shell_path)
    log_info("Reinitialized shell path resolver")
