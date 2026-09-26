"""Local shell calculator."""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import Calculator
from ..logging import log_warning, log_info
from ..shell import run_command, replace_commands_in_string
from .manager import resolve_timeout, get_environment_info
from .errors import classify_error


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
        timeout: Timeout in seconds (None resolves via model["timeout"], then FZ_RUN_TIMEOUT config default, 3600)
        original_input_was_dir: Whether original input was a directory
        original_cwd: Original working directory
        input_files_list: List of input file names in order (from .fz_hash)

    Returns:
        Dict containing calculation results and status
    """
    # Resolve effective timeout: explicit arg > model's "timeout" entry > config default
    timeout = resolve_timeout(model, timeout)
    # Import here to avoid circular imports
    from ..core import fzo, is_interrupted

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
                command.replace("\\","/"), original_cwd
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
                from ..core import is_interrupted

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
                    if timeout is not None and elapsed_time >= timeout:
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

            # Classify the error to provide a human-readable message
            error_message = classify_error(
                stderr=stderr_content,
                exit_code=result.returncode,
                command=command_for_result or full_command,
                protocol="sh",
            )

            failure_result = {
                "status": "failed",
                "exit_code": result.returncode,
                "error": error_message,
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

        # Propagate _output_error from fzo if present
        output_error = output_dict.pop("_output_error", None)

        output_dict["status"] = "done"
        output_dict["calculator"] = "sh://"

        # Include command information
        output_dict["command"] = command_for_result

        # If output parsing had errors, report them
        if output_error:
            output_dict["error"] = f"Missing output: {output_error}"

        return output_dict

    except subprocess.TimeoutExpired:
        timeout_result = {
            "status": "timeout",
            "error": f"Command timed out after {timeout} seconds: '{command_for_result or 'unknown'}'",
        }
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
        classified = classify_error(str(e), exit_code=getattr(e, 'errno', None), command=command_for_result, protocol="sh")
        error_result = {"status": "failed", "error": classified}
        error_result["command"] = command_for_result
        return error_result
    except Exception as e:
        error_result = {"status": "error", "error": str(e)}
        error_result["command"] = command_for_result
        return error_result
    finally:
        os.chdir(original_cwd)


class ShCalculator(Calculator):
    scheme = "sh"

    def run(self, working_dir, calculator_uri, model, timeout=None,
            original_input_was_dir=False, original_cwd=None,
            input_files_list=None, static_entries=None):
        command = calculator_uri[5:] if calculator_uri.startswith("sh://") else ""
        return run_local_calculation(
            working_dir, command, model, timeout, original_input_was_dir,
            original_cwd, input_files_list,
        )
