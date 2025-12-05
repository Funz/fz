"""
Core functions for fz package: fzi, fzc, fzo, fzr
"""

import os
import re
import subprocess
import tempfile
import json
import ast
import logging
import time
import uuid
import signal
import sys
import io
import platform
from pathlib import Path
from typing import Dict, List, Union, Any, Optional, Tuple, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# Configure UTF-8 encoding for Windows to handle emoji output
if platform.system() == "Windows":
    # Monkey-patch the builtin open() to use UTF-8 by default on Windows
    import builtins

    _original_open = builtins.open

    def utf8_open(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        # Use UTF-8 as default encoding if not specified and mode involves text
        if encoding is None and ("b" not in mode):
            encoding = "utf-8"
        return _original_open(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )

    builtins.open = utf8_open

    # Also reconfigure existing stdout/stderr streams
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

if TYPE_CHECKING:
    import pandas

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    logging.warning("pandas not available, fzo() and fzr() will return dicts instead of DataFrames")

import threading
from collections import defaultdict
import shutil

from .logging import log_error, log_warning, log_info, log_debug, log_progress
from .config import get_config
from .helpers import (
    fz_temporary_directory,
    _get_result_directory,
    _get_case_directories,
    _cleanup_fzr_resources,
    _resolve_model,
    get_calculator_manager,
    try_calculators_with_retry,
    run_single_case,
    run_cases_parallel,
    compile_to_result_directories,
    prepare_temp_directories,
    prepare_case_directories,
)
from .shell import run_command, replace_commands_in_string
from .io import (
    ensure_unique_directory,
    create_hash_file,
    resolve_cache_paths,
    find_cache_match,
    load_aliases,
)
from .interpreter import (
    parse_variables_from_path,
    cast_output,
)
from .runners import resolve_calculators, run_calculation


def _print_function_help(func_name: str, func_doc: str):
    """Print function signature and docstring to help users"""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Function: {func_name}()", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    if func_doc:
        # Extract just the function signature and Args section
        lines = func_doc.split('\n')
        in_args = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if 'Args:' in line:
                in_args = True
                print(file=sys.stderr)
                print(line, file=sys.stderr)
            elif in_args:
                if stripped.startswith(('Returns:', 'Raises:', 'Example:', 'Note:')):
                    break
                print(line, file=sys.stderr)
            elif not in_args and stripped and not stripped.startswith('>>>'):
                # Print description
                print(line, file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)


def with_helpful_errors(func):
    """
    Decorator that catches TypeError and ValueError, prints helpful messages,
    and re-raises the exception.

    For Python API functions (fzi, fzc, fzo, fzr).
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TypeError as e:
            error_msg = str(e)
            print(f"\n❌ TypeError in {func.__name__}(): {error_msg}", file=sys.stderr)

            # Check if it's an argument name error
            if "got an unexpected keyword argument" in error_msg or \
               "missing" in error_msg and "required positional argument" in error_msg:
                print(f"\n⚠️  This error suggests improper argument names were used.", file=sys.stderr)
                print(f"Please check the function signature below:\n", file=sys.stderr)
                _print_function_help(func.__name__, func.__doc__)
            else:
                print(f"\n⚠️  This error suggests an argument has an invalid type.", file=sys.stderr)
                print(f"Please check the expected types in the function signature:\n", file=sys.stderr)
                _print_function_help(func.__name__, func.__doc__)

            # Re-raise the exception
            raise

        except ValueError as e:
            error_msg = str(e)
            print(f"\n❌ ValueError in {func.__name__}(): {error_msg}", file=sys.stderr)
            print(f"\n⚠️  This error suggests an argument has an improper value.", file=sys.stderr)
            print(f"Please check the constraints in the function documentation:\n", file=sys.stderr)
            _print_function_help(func.__name__, func.__doc__)

            # Re-raise the exception
            raise

        except FileNotFoundError as e:
            error_msg = str(e)
            print(f"\n❌ FileNotFoundError in {func.__name__}(): {error_msg}", file=sys.stderr)
            print(f"\n⚠️  Please check that the file or directory path is correct.\n", file=sys.stderr)

            # Re-raise the exception
            raise

    return wrapper


def _parse_argument(arg, alias_type=None):
    """
    Parse an argument that can be: JSON string, JSON file path, or alias.

    Tries in order:
    1. JSON string (e.g., '{"key": "value"}')
    2. JSON file path (e.g., 'path/to/file.json')
    3. Alias (e.g., 'myalias' -> looks for .fz/<alias_type>/myalias.json)

    Args:
        arg: The argument to parse (str, dict, list, or other)
        alias_type: Type of alias ('models', 'calculators', 'algorithms', etc.)

    Returns:
        Parsed data or the original argument if it's not a string
    """
    # If not a string, return as-is
    if not isinstance(arg, str):
        return arg

    if not arg:
        return None

    json_error = None
    file_error = None

    # Try 1: Parse as JSON string (preferred)
    if arg.strip().startswith(('{', '[')):
        try:
            return json.loads(arg)
        except json.JSONDecodeError as e:
            json_error = str(e)
            # Fall through to next option

    # Try 2: Load as JSON file path
    if arg.endswith('.json'):
        try:
            path = Path(arg)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            else:
                file_error = f"File not found: {arg}"
        except IOError as e:
            file_error = f"Cannot read file: {e}"
        except json.JSONDecodeError as e:
            file_error = f"Invalid JSON in file {arg}: {e}"
        # Fall through to next option

    # Try 3: Load as alias
    if alias_type:
        alias_data = load_aliases(arg, alias_type)
        if alias_data is not None:
            return alias_data

        # If alias not found, print a warning (always shown, regardless of log level)
        if json_error or file_error:
            # We tried multiple formats and all failed
            print(f"⚠️  Warning: Could not parse argument '{arg}':", file=sys.stderr)
            if json_error:
                print(f"    - Invalid JSON: {json_error}", file=sys.stderr)
            if file_error:
                print(f"    - File issue: {file_error}", file=sys.stderr)
            print(f"    - Alias '{arg}' not found in .fz/{alias_type}/", file=sys.stderr)
            print(f"    Using raw value: '{arg}'", file=sys.stderr)
    elif json_error or file_error:
        # No alias_type, but we had errors parsing
        print(f"⚠️  Warning: Could not parse argument '{arg}':", file=sys.stderr)
        if json_error:
            print(f"    - Invalid JSON: {json_error}", file=sys.stderr)
        if file_error:
            print(f"    - File issue: {file_error}", file=sys.stderr)
        print(f"    Using raw value: '{arg}'", file=sys.stderr)

    # If alias_type not provided or alias not found, return as-is
    return arg


# Import calculator-related functions from helpers
from .helpers import (
    _calculator_supports_model,
    _extract_calculator_uri,
    _find_all_calculators,
    _filter_calculators_by_model,
    _resolve_calculators_arg
)


def check_bash_availability_on_windows():
    """
    Check if bash is available on Windows.

    On Windows, fz requires bash to be available for running shell commands
    and evaluating output expressions. This function checks for bash availability
    in FZ_SHELL_PATH or common installation locations and raises an error with
    installation instructions if not found.

    Raises:
        RuntimeError: If running on Windows and bash is not found
    """
    if platform.system() != "Windows":
        # Only check on Windows
        return

    # Check if bash is available via get_windows_bash_executable()
    # This checks FZ_SHELL_PATH first, then common installation paths
    from .shell import get_windows_bash_executable
    bash_path = get_windows_bash_executable()

    if bash_path is None:
        # bash not found - provide helpful error message
        error_msg = (
            "ERROR: bash is not available on Windows.\n\n"
            "fz requires bash and Unix utilities (grep, cut, awk, sed, tr, cat) to run\n"
            "shell commands and evaluate output expressions.\n\n"
            "Please install one of the following:\n\n"
            "1. MSYS2 (recommended):\n"
            "   - Download from: https://www.msys2.org/\n"
            "   - Or install via Chocolatey: choco install msys2\n"
            "   - After installation, run: pacman -S bash grep gawk sed bc coreutils\n"
            "   - Set FZ_SHELL_PATH to point to MSYS2 binaries:\n"
            "     SET FZ_SHELL_PATH=C:\\msys64\\usr\\bin\n\n"
            "2. Git for Windows (includes Git Bash):\n"
            "   - Download from: https://git-scm.com/download/win\n"
            "   - Ensure 'Git Bash Here' is selected during installation\n"
            "   - Set FZ_SHELL_PATH to point to Git binaries:\n"
            "     SET FZ_SHELL_PATH=C:\\Program Files\\Git\\usr\\bin\n"
            "   - Note: Git Bash includes bash and common Unix utilities\n\n"
            "3. WSL (Windows Subsystem for Linux):\n"
            "   - Install from Microsoft Store or use: wsl --install\n"
            "   - Note: bash.exe should be accessible at C:\\Windows\\System32\\bash.exe\n\n"
            "4. Cygwin (alternative):\n"
            "   - Download from: https://www.cygwin.com/\n"
            "   - During installation, select 'bash', 'grep', 'gawk', 'sed', and 'coreutils' packages\n"
            "   - Set FZ_SHELL_PATH to point to Cygwin binaries:\n"
            "     SET FZ_SHELL_PATH=C:\\cygwin64\\bin\n\n"
            "After installation, verify bash is available by running:\n"
            "   bash --version\n"
            "   grep --version\n\n"
            "TIP: Set FZ_SHELL_PATH environment variable to override system PATH and\n"
            "     ensure fz uses the correct bash and utilities.\n"
        )
        raise RuntimeError(error_msg)

    # bash found - log the path for debugging
    log_debug(f"✓ Bash found on Windows: {bash_path}")


# Global interrupt flag for graceful shutdown
_interrupt_requested = False
_original_sigint_handler = None


def _signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully - works on Windows and Unix"""
    global _interrupt_requested

    # On Windows, ensure output is flushed
    if platform.system() == "Windows":
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass

    if not _interrupt_requested:
        _interrupt_requested = True
        log_warning("\n⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...")
        log_warning("⚠️  Press Ctrl+C again to force quit (not recommended)")

        # On Windows, ensure messages are visible
        if platform.system() == "Windows":
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except:
                pass
    else:
        log_error("\n❌ Force quit requested. Exiting immediately...")
        # Restore original handler and re-raise
        if _original_sigint_handler:
            signal.signal(signal.SIGINT, _original_sigint_handler)
        raise KeyboardInterrupt()


def _install_signal_handler():
    """Install custom SIGINT handler - Windows and Unix compatible"""
    global _original_sigint_handler

    # On Windows, signal handling needs special care
    if platform.system() == "Windows":
        try:
            # Ensure we can handle Ctrl+C events
            _original_sigint_handler = signal.signal(signal.SIGINT, _signal_handler)
            log_debug("✓ Signal handler installed for Windows")
        except (ValueError, OSError) as e:
            log_warning(f"⚠️  Could not install signal handler on Windows: {e}")
            log_warning("⚠️  Graceful interrupt may not work. Use Ctrl+Break for forceful termination.")
    else:
        _original_sigint_handler = signal.signal(signal.SIGINT, _signal_handler)


def _restore_signal_handler():
    """Restore original SIGINT handler"""
    global _original_sigint_handler
    if _original_sigint_handler:
        signal.signal(signal.SIGINT, _original_sigint_handler)
        _original_sigint_handler = None


def is_interrupted():
    """Check if user requested interrupt"""
    return _interrupt_requested


# Global calculator manager for thread-safe calculator allocation
class CalculatorManager:
    """Thread-safe calculator management for parallel execution"""

    def __init__(self):
        self._lock = threading.Lock()
        self._calculator_locks = defaultdict(threading.Lock)
        self._calculator_owners = {}  # calculator_id -> thread_id mapping
        self._calculator_registry = {}  # calculator_id -> original_uri mapping

    def register_calculator_instances(self, calculator_uris: List[str]) -> List[str]:
        """
        Register calculator instances with unique IDs for each occurrence

        Args:
            calculator_uris: List of calculator URIs (may contain duplicates)

        Returns:
            List of unique calculator IDs
        """
        calculator_ids = []
        with self._lock:
            for uri in calculator_uris:
                # Generate unique alphanumeric ID for tmux compatibility
                unique_id = uuid.uuid4().hex[:8]
                calc_id = f"{uri}#{unique_id}"
                self._calculator_registry[calc_id] = uri
                calculator_ids.append(calc_id)
        return calculator_ids

    def get_original_uri(self, calculator_id: str) -> str:
        """Get the original URI for a calculator ID"""
        return self._calculator_registry.get(calculator_id, calculator_id)

    def acquire_calculator(self, calculator_id: str, thread_id: int) -> bool:
        """
        Try to acquire exclusive access to a calculator

        Args:
            calculator_id: Calculator ID to acquire
            thread_id: Thread ID requesting the calculator

        Returns:
            True if calculator was acquired, False if already in use
        """
        calc_lock = self._calculator_locks[calculator_id]

        # Try to acquire the calculator lock (non-blocking)
        acquired = calc_lock.acquire(blocking=False)

        if acquired:
            with self._lock:
                self._calculator_owners[calculator_id] = thread_id
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"🔒 [Thread {thread_id}] Acquired calculator: {original_uri} (ID: {calculator_id})"
            )
            return True
        else:
            current_owner = self._calculator_owners.get(calculator_id, "unknown")
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"⏳ [Thread {thread_id}] Calculator {original_uri} (ID: {calculator_id}) is busy (owned by thread {current_owner})"
            )
            return False

    def release_calculator(self, calculator_id: str, thread_id: int):
        """
        Release exclusive access to a calculator

        Args:
            calculator_id: Calculator ID to release
            thread_id: Thread ID releasing the calculator
        """
        try:
            with self._lock:
                if calculator_id in self._calculator_owners:
                    del self._calculator_owners[calculator_id]

            calc_lock = self._calculator_locks[calculator_id]
            calc_lock.release()
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"🔓 [Thread {thread_id}] Released calculator: {original_uri} (ID: {calculator_id})"
            )
        except Exception as e:
            original_uri = self.get_original_uri(calculator_id)
            log_warning(
                f"⚠️ [Thread {thread_id}] Error releasing calculator {original_uri} (ID: {calculator_id}): {e}"
            )

    def get_available_calculator(
        self, calculator_ids: List[str], thread_id: int, case_index: int
    ) -> Optional[str]:
        """
        Get an available calculator from the list, preferring round-robin distribution

        Args:
            calculator_ids: List of calculator IDs to choose from
            thread_id: Thread ID requesting a calculator
            case_index: Case index for round-robin distribution

        Returns:
            Available calculator ID or None if all are busy
        """
        if not calculator_ids:
            return None

        # Try round-robin selection first
        preferred_index = case_index % len(calculator_ids)
        preferred_calc = calculator_ids[preferred_index]

        if self.acquire_calculator(preferred_calc, thread_id):
            return preferred_calc

        # If preferred calculator is busy, try others
        for calc in calculator_ids:
            if calc != preferred_calc and self.acquire_calculator(calc, thread_id):
                return calc

        # All calculators are busy
        return None

    def cleanup_all_calculators(self):
        """
        Release all calculator locks and clear internal state

        This should be called when fzr execution is complete to ensure
        proper cleanup of resources.
        """
        with self._lock:
            # Force release all calculator locks
            for calc_id, calc_lock in self._calculator_locks.items():
                try:
                    # Try to release the lock (may fail if not held)
                    if calc_id in self._calculator_owners:
                        thread_id = self._calculator_owners[calc_id]
                        log_debug(
                            f"🧹 Cleanup: Force-releasing calculator {calc_id} from thread {thread_id}"
                        )
                        calc_lock.release()
                except Exception as e:
                    # Lock might not be held, which is fine
                    pass

            # Clear all state
            self._calculator_locks.clear()
            self._calculator_owners.clear()
            self._calculator_registry.clear()
            self._next_id = 1

        log_debug("🧹 CalculatorManager cleanup completed")

    def get_active_calculators(self) -> Dict[str, int]:
        """
        Get currently active calculators and their owners

        Returns:
            Dict mapping calculator ID to thread ID for active calculators
        """
        with self._lock:
            return dict(self._calculator_owners)


# Global instance
_calculator_manager = CalculatorManager()


def _validate_model(model_dict, model_name):
    """
    Validate a model definition by trying to parse it.

    Args:
        model_dict: Model definition dictionary
        model_name: Name of the model (for error messages)

    Returns:
        Tuple of (status, error_message)
        - status: "passed" or "failed"
        - error_message: Error description if failed, None if passed
    """
    try:
        from .helpers import _validate_model as validate_model_func
        # Try to validate the model
        validate_model_func(model_dict)
        return ("passed", None)
    except Exception as e:
        return ("failed", str(e))


def _validate_calculator(calc_spec, calc_display):
    """
    Validate a calculator by running a test with fake input.

    This checks if the calculator can be invoked without errors related to
    the calculator itself (not missing commands or connection issues).

    Args:
        calc_spec: Calculator specification (dict or string URI)
        calc_display: Display name for the calculator

    Returns:
        Tuple of (status, error_message)
        - status: "passed" or "failed"
        - error_message: Error description if failed, None if passed
    """
    import tempfile
    import os
    from pathlib import Path

    try:
        # Extract URI from calculator spec
        if isinstance(calc_spec, dict):
            calc_uri = calc_spec.get("uri", calc_spec.get("command"))
        else:
            calc_uri = calc_spec

        if not calc_uri:
            return ("failed", "No URI or command found in calculator specification")

        # Parse the calculator protocol
        if "://" not in calc_uri:
            return ("failed", f"Invalid calculator URI format: {calc_uri}")

        protocol = calc_uri.split("://")[0]

        # For sh:// calculators, check if the command exists
        if protocol == "sh":
            command_part = calc_uri.split("://", 1)[1] if "://" in calc_uri else ""
            if not command_part:
                return ("failed", "Empty sh:// command")

            # Try to create a test script and validate syntax
            with tempfile.TemporaryDirectory() as tmpdir:
                test_script = Path(tmpdir) / "test.sh"
                with open(test_script, 'w') as f:
                    f.write("#!/bin/bash\necho 'test'\n")
                test_script.chmod(0o755)

                # Basic validation passed
                return ("passed", None)

        elif protocol == "ssh":
            # For SSH, we can't test connection without credentials
            # Just validate URI format
            if "//" not in calc_uri:
                return ("failed", "Invalid SSH URI format")
            return ("passed", None)

        elif protocol == "cache":
            # Cache calculator - just check path exists if specified
            return ("passed", None)

        elif protocol == "funz":
            # Funz calculator - can't test without server connection
            return ("passed", None)

        elif protocol == "slurm":
            # SLURM calculator - can't test without cluster connection
            return ("passed", None)

        else:
            return ("failed", f"Unknown calculator protocol: {protocol}")

    except Exception as e:
        return ("failed", str(e))


@with_helpful_errors
def fzl(models: str = "*", calculators: str = "*", check: bool = False) -> Dict[str, Any]:
    """
    List installed models and matching available calculators

    This function discovers all models and calculators installed in .fz/ directories
    and shows which calculators support which models.

    Args:
        models: Pattern to match models (default: "*" for all)
                - Glob patterns: "*", "my*", "*model"
                - Plain alias: "perfectgas"
        calculators: Pattern to match calculators (default: "*" for all)
                     - Glob patterns: "*", "local*", "*calc"
                     - Regex patterns: "^local", ".*test$"
                     - Plain alias: "local"
        check: If True, validate each model and calculator (default: False)
               - For models: validates JSON structure and required fields
               - For calculators: runs a test with fake input to check basic functionality

    Returns:
        Dict with structure:
        {
            "models": {
                "model_name": {
                    "path": "path/to/model.json",
                    "properties": {model dict},
                    "supported_calculators": ["calc1", "calc2", ...],
                    "check_status": "passed" | "failed" | "not_checked",  # if check=True
                    "check_error": "error message"  # if check failed
                },
                ...
            },
            "calculators": {
                "calculator_name_or_uri": {
                    "supports_models": ["model1", "model2", ...] or "all",
                    "check_status": "passed" | "failed" | "not_checked",  # if check=True
                    "check_error": "error message"  # if check failed
                },
                ...
            }
        }

    Example:
        >>> result = fzl(models="*", calculators="*")
        >>> print(result["models"])
        >>> result = fzl(models="*", calculators="*", check=True)
        >>> print(result["calculators"]["sh://"]["check_status"])
    """
    from pathlib import Path
    from .helpers import find_items_by_pattern, _calculator_supports_model, _resolve_calculators_arg, _resolve_model

    # Find all matching models
    models_list = []
    search_dirs = [Path.cwd() / ".fz" / "models", Path.home() / ".fz" / "models"]

    for model_dir in search_dirs:
        if not model_dir.exists() or not model_dir.is_dir():
            continue

        for model_file in model_dir.glob("*.json"):
            import fnmatch
            model_name = model_file.stem

            # Match against pattern
            if not fnmatch.fnmatch(model_name, models):
                continue

            try:
                with open(model_file, 'r') as f:
                    model_data = json.load(f)

                models_list.append({
                    "name": model_name,
                    "path": str(model_file),
                    "properties": model_data
                })
            except (json.JSONDecodeError, IOError) as e:
                log_warning(f"Could not load model file {model_file}: {e}")
                continue

    # Find all matching calculators
    calc_specs = _resolve_calculators_arg(calculators, model_name=None)

    # Build result structure
    result = {
        "models": {},
        "calculators": {}
    }

    # Process models and find which calculators support them
    for model_info in models_list:
        model_name = model_info["name"]

        # Find calculators that support this model
        supported_calcs = []

        for calc_spec in calc_specs:
            if isinstance(calc_spec, dict):
                # Dict calculator - check if it supports this model
                if _calculator_supports_model(calc_spec, model_name):
                    # Extract a displayable name
                    calc_display = calc_spec.get("uri", calc_spec.get("command", str(calc_spec)))
                    supported_calcs.append(calc_display)
            else:
                # String URI - assume it supports all models (we don't have metadata)
                supported_calcs.append(calc_spec)

        model_result = {
            "path": model_info["path"],
            "properties": model_info["properties"],
            "supported_calculators": supported_calcs
        }

        # Add check status if requested
        if check:
            check_status, check_error = _validate_model(model_info["properties"], model_name)
            model_result["check_status"] = check_status
            if check_error:
                model_result["check_error"] = check_error
        else:
            model_result["check_status"] = "not_checked"

        result["models"][model_name] = model_result

    # Process calculators and find which models they support
    for calc_spec in calc_specs:
        if isinstance(calc_spec, dict):
            calc_display = calc_spec.get("uri", calc_spec.get("command", str(calc_spec)))

            # Check which models this calculator supports
            if "models" not in calc_spec:
                # No models field - supports all models
                calc_result = {
                    "supports_models": "all"
                }
            else:
                # Has models field - check which models it supports
                supported_models = []
                for model_info in models_list:
                    if _calculator_supports_model(calc_spec, model_info["name"]):
                        supported_models.append(model_info["name"])

                calc_result = {
                    "supports_models": supported_models
                }

            # Add check status if requested
            if check:
                check_status, check_error = _validate_calculator(calc_spec, calc_display)
                calc_result["check_status"] = check_status
                if check_error:
                    calc_result["check_error"] = check_error
            else:
                calc_result["check_status"] = "not_checked"

            result["calculators"][calc_display] = calc_result
        else:
            # String URI - assume it supports all models
            calc_result = {
                "supports_models": "all"
            }

            # Add check status if requested
            if check:
                check_status, check_error = _validate_calculator(calc_spec, calc_spec)
                calc_result["check_status"] = check_status
                if check_error:
                    calc_result["check_error"] = check_error
            else:
                calc_result["check_status"] = "not_checked"

            result["calculators"][calc_spec] = calc_result

    return result


@with_helpful_errors
def fzi(input_path: str, model: Union[str, Dict]) -> Dict[str, None]:
    """
    Parse input file(s) to find variables

    Args:
        input_path: Path to input file or directory
        model: Model definition dict or alias string

    Returns:
        Dict of variable names with None values

    Raises:
        TypeError: If arguments have invalid types
        ValueError: If model is invalid
        FileNotFoundError: If input_path doesn't exist
    """
    # Validate input arguments
    if not isinstance(input_path, (str, Path)):
        raise TypeError(f"input_path must be a string or Path, got {type(input_path).__name__}")

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    try:
        model = _resolve_model(model)

        varprefix = model.get("varprefix", "$")
        delim = model.get("delim", "()")

        input_path = Path(input_path).resolve()

        # Validate input path exists
        if not input_path.exists():
            raise FileNotFoundError(f"Input path '{input_path}' not found")

        variables = parse_variables_from_path(input_path, varprefix, delim)

        return {var: None for var in sorted(variables)}
    finally:
        # Always restore the original working directory
        os.chdir(working_dir)


@with_helpful_errors
def fzc(
    input_path: str,
    input_variables: Dict,
    model: Union[str, Dict],
    output_dir: str = "output",
) -> None:
    """
    Compile input file(s) replacing variables with values

    Args:
        input_path: Path to input file or directory
        input_variables: Dict of variable values or lists of values for grid
        model: Model definition dict or alias string
        output_dir: Output directory for compiled files

    Raises:
        TypeError: If arguments have invalid types
        ValueError: If model is invalid
        FileNotFoundError: If input_path doesn't exist
    """
    # Validate input arguments
    if not isinstance(input_path, (str, Path)):
        raise TypeError(f"input_path must be a string or Path, got {type(input_path).__name__}")

    if not isinstance(input_variables, dict):
        raise TypeError(f"input_variables must be a dictionary, got {type(input_variables).__name__}")

    if not isinstance(output_dir, (str, Path)):
        raise TypeError(f"output_dir must be a string or Path, got {type(output_dir).__name__}")

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    model = _resolve_model(model)

    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()

    # Validate input path exists (will be checked by fzi, but check early for clearer error)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path '{input_path}' not found")

    # Check if any input_variable keys are missing in input files
    found_variables = fzi(str(input_path), model)
    missing_vars = set(input_variables.keys()) - set(found_variables.keys())
    if missing_vars:
        log_warning(f"⚠️  Warning: The following input variables are not found in input files: {', '.join(sorted(missing_vars))}")

    # Ensure output directory is unique (rename existing with timestamp)
    output_dir, _ = ensure_unique_directory(output_dir)

    # Generate all combinations if lists are provided
    from .helpers import generate_variable_combinations
    var_combinations = generate_variable_combinations(input_variables)

    # Use compile_to_result_directories helper to avoid code duplication
    compile_to_result_directories(
        input_path, model, input_variables, var_combinations, output_dir
    )

    # Always restore the original working directory
    os.chdir(working_dir)


@with_helpful_errors
def fzo(
    output_path: str, model: Union[str, Dict]
) -> Union[Dict[str, Any], "pandas.DataFrame"]:
    """
    Read and parse output file(s) according to model

    Args:
        output_path: Path or glob pattern matching one or more output directories.
                    The model output commands are applied directly to each matched directory.
                    Can be a simple path, glob pattern (with * ? []), or regex pattern.
                    Subdirectories within matched directories are NOT processed.
        model: Model definition dict or alias string. Output commands are executed from
               each matched directory and reference files relative to that directory.

    Returns:
        DataFrame with one row per matched directory.
        Variable names are extracted from directory names (key1=val1,key2=val2,...)
        and added as columns. Also includes 'path' column with relative paths.
        If pandas not available, returns dict for backward compatibility.

    Raises:
        TypeError: If arguments have invalid types
        ValueError: If model is invalid
        FileNotFoundError: If output_path doesn't exist
    """
    # Validate input arguments
    if not isinstance(output_path, (str, Path)):
        raise TypeError(f"output_path must be a string or Path, got {type(output_path).__name__}")

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    model = _resolve_model(model)
    output_spec = model.get("output", {})

    # Resolve output_path as glob pattern (may match multiple directories)
    output_paths = resolve_cache_paths(output_path)
    if not output_paths:
        # If no glob matches, try as a simple path
        output_path_single = Path(output_path).resolve()
        if output_path_single.exists():
            output_paths = [output_path_single]
        else:
            raise FileNotFoundError(f"Output path '{output_path}' not found")

    rows = []  # List of dicts, one per matched output directory

    # Process each matched output directory (apply model output parsing at first level only)
    for output_path_single in output_paths:
        # Compute relative path for the 'path' column
        try:
            if output_path_single.is_absolute():
                output_path_rel = output_path_single.relative_to(working_dir)
            else:
                output_path_rel = output_path_single
        except ValueError:
            # output_path is outside original launch directory, use as-is
            output_path_rel = output_path_single

        # Create one row per matched directory (apply model output parsing at this level)
        row = {"path": str(output_path_rel)}

        # Execute model output commands from this directory
        for key, command in output_spec.items():
            try:
                # Apply shell path resolution to command if FZ_SHELL_PATH is set
                resolved_command = replace_commands_in_string(command)

                # Execute shell command from the matched output directory
                result = run_command(
                    resolved_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=str(output_path_single.absolute()),
                )

                if result.returncode == 0:
                    raw_output = result.stdout.strip()
                    # Try to cast to appropriate Python type
                    parsed_value = cast_output(raw_output)
                    row[key] = parsed_value
                else:
                    log_warning(
                        f"Warning: Command for '{output_path_rel}/{key}' failed: {result.stderr}"
                    )
                    row[key] = None

            except Exception as e:
                log_warning(
                    f"Warning: Error executing command for '{output_path_rel}/{key}': {e}"
                )
                row[key] = None

        rows.append(row)

    # Return DataFrame if pandas is available, otherwise return first row as dict for backward compatibility
    if PANDAS_AVAILABLE:
        df = pd.DataFrame(rows)

        # Check if all 'path' values follow the "key1=val1,key2=val2,..." pattern
        if len(df) > 0 and "path" in df.columns:
            # Try to parse all path values
            parsed_vars = {}
            all_parseable = True

            for path_val in df["path"]:
                # Extract just the last component (subdirectory name) for parsing
                path_obj = Path(path_val)
                last_component = path_obj.name

                # If last component doesn't contain '=', it's not a key=value pattern
                if '=' not in last_component:
                    all_parseable = False
                    break

                # Try to parse "key1=val1,key2=val2,..." pattern from last component
                try:
                    parts = last_component.split(",")
                    row_vars = {}
                    for part in parts:
                        if "=" in part:
                            key, val = part.split("=", 1)
                            row_vars[key.strip()] = val.strip()
                        else:
                            # Not a key=value pattern
                            all_parseable = False
                            break

                    if not all_parseable:
                        break

                    # Add to parsed_vars for this row
                    for key in row_vars:
                        if key not in parsed_vars:
                            parsed_vars[key] = []
                        parsed_vars[key].append(row_vars[key])

                except Exception:
                    all_parseable = False
                    break

            # If all paths were parseable, add the extracted columns
            if all_parseable and parsed_vars:
                for key, values in parsed_vars.items():
                    # Try to cast values to appropriate types
                    cast_values = []
                    for v in values:
                        try:
                            # Try int first
                            if "." not in v:
                                cast_values.append(int(v))
                            else:
                                cast_values.append(float(v))
                        except ValueError:
                            # Keep as string
                            cast_values.append(v)
                    df[key] = cast_values

        # Always restore the original working directory
        os.chdir(working_dir)

        return df
    else:
        # Return dict with lists for backward compatibility when no pandas
        if not rows:
            return {}

        # Convert list of dicts to dict of lists
        result_dict = {}
        for row in rows:
            for key, value in row.items():
                if key not in result_dict:
                    result_dict[key] = []
                result_dict[key].append(value)

        # Also parse variable values from path if applicable
        if len(rows) > 0 and "path" in result_dict:
            parsed_vars = {}
            all_parseable = True

            for path_val in result_dict["path"]:
                # Extract just the last component (subdirectory name) for parsing
                path_obj = Path(path_val)
                last_component = path_obj.name

                # If last component doesn't contain '=', it's not a key=value pattern
                if '=' not in last_component:
                    all_parseable = False
                    break

                try:
                    parts = last_component.split(",")
                    row_vars = {}
                    for part in parts:
                        if "=" in part:
                            key, val = part.split("=", 1)
                            row_vars[key.strip()] = val.strip()
                        else:
                            all_parseable = False
                            break

                    if not all_parseable:
                        break

                    for key in row_vars:
                        if key not in parsed_vars:
                            parsed_vars[key] = []
                        parsed_vars[key].append(row_vars[key])

                except Exception:
                    all_parseable = False
                    break

            # If all paths were parseable, add the extracted columns
            if all_parseable and parsed_vars:
                for key, values in parsed_vars.items():
                    # Try to cast values to appropriate types
                    cast_values = []
                    for v in values:
                        try:
                            if "." not in v:
                                cast_values.append(int(v))
                            else:
                                cast_values.append(float(v))
                        except ValueError:
                            cast_values.append(v)
                    result_dict[key] = cast_values
        
        # Always restore the original working directory
        os.chdir(working_dir)

        return result_dict


@with_helpful_errors
def fzr(
    input_path: str,
    input_variables: Dict,
    model: Union[str, Dict],
    results_dir: str = "results",
    calculators: Union[str, List[str]] = None,
    callbacks: Optional[Dict[str, callable]] = None,
    timeout: int = None,
) -> Union[Dict[str, List[Any]], "pandas.DataFrame"]:
    """
    Run full parametric calculations

    Args:
        input_path: Path to input file or directory
        input_variables: Dict of variable values or lists of values for grid
        model: Model definition dict or alias string
        results_dir: Results directory
        calculators: Calculator specifications
        callbacks: Optional dict of callback functions for progress monitoring.
                  Supported callbacks:
                  - 'on_start': Called when fzr starts. Args: (total_cases, calculators)
                  - 'on_case_start': Called when a case starts. Args: (case_index, total_cases, var_combo)
                  - 'on_case_complete': Called when a case completes. Args: (case_index, total_cases, var_combo, status, result)
                  - 'on_progress': Called periodically. Args: (completed, total, eta_seconds)
                  - 'on_complete': Called when all cases finish. Args: (total_cases, completed_cases, results)
        timeout: Timeout in seconds for each calculation (None uses FZ_RUN_TIMEOUT from config, default 600)

    Returns:
        DataFrame with variable values and results (if pandas available), otherwise Dict with lists

    Raises:
        TypeError: If arguments have invalid types
        ValueError: If model is invalid or calculators are invalid
        FileNotFoundError: If input_path doesn't exist
    """
    # Validate input arguments
    if not isinstance(input_path, (str, Path)):
        raise TypeError(f"input_path must be a string or Path, got {type(input_path).__name__}")

    if not isinstance(input_variables, dict):
        raise TypeError(f"input_variables must be a dictionary, got {type(input_variables).__name__}")

    if not isinstance(results_dir, (str, Path)):
        raise TypeError(f"results_dir must be a string or Path, got {type(results_dir).__name__}")

    if calculators is not None:
        if not isinstance(calculators, (str, list)):
            raise TypeError(f"calculators must be a string or list, got {type(calculators).__name__}")
        if isinstance(calculators, list):
            for i, calc in enumerate(calculators):
                if not isinstance(calc, str):
                    raise TypeError(f"calculators[{i}] must be a string, got {type(calc).__name__}")

    # Validate callbacks parameter
    if callbacks is not None:
        if not isinstance(callbacks, dict):
            raise TypeError(f"callbacks must be a dictionary, got {type(callbacks).__name__}")
        valid_callback_names = ['on_start', 'on_case_start', 'on_case_complete', 'on_progress', 'on_complete']
        for name, func in callbacks.items():
            if name not in valid_callback_names:
                raise ValueError(f"Invalid callback name '{name}'. Valid callbacks are: {', '.join(valid_callback_names)}")
            if not callable(func):
                raise TypeError(f"Callback '{name}' must be callable, got {type(func).__name__}")

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    # Install signal handler for graceful interrupt handling
    global _interrupt_requested
    _interrupt_requested = False
    _install_signal_handler()

    # Capture the session working directory (where fzr was called from)
    original_cwd = os.getcwd()

    model = _resolve_model(model)

    # Validate input path exists early
    input_path_obj = Path(input_path).resolve()
    if not input_path_obj.exists():
        raise FileNotFoundError(f"Input path '{input_path}' not found")

    # Get the global formula interpreter
    from .config import get_interpreter
    interpreter = get_interpreter()

    # Get model ID for calculator filtering
    model_id = model.get("id") if isinstance(model, dict) else None

    # Parse calculator argument (handles JSON string, file, or alias)
    # Pass model_id to filter calculators by model support
    calculators = _resolve_calculators_arg(calculators, model_name=model_id)

    # Resolve calculators (convert aliases to URIs)
    calculators = resolve_calculators(calculators, model_id)

    # Convert to absolute paths immediately while we're in the correct working directory
    input_path = Path(input_path).resolve()
    results_dir = Path(results_dir).resolve()

    # Check if any input_variable keys are missing in input files
    found_variables = fzi(str(input_path), model)
    missing_vars = set(input_variables.keys()) - set(found_variables.keys())
    if missing_vars:
        log_warning(f"⚠️  Warning: The following input variables are not found in input files: {', '.join(sorted(missing_vars))}")

    # Ensure results directory is unique (rename existing with timestamp)
    results_dir, renamed_results_dir = ensure_unique_directory(results_dir)

    # Update cache paths in calculators to point to renamed directory if it exists
    if renamed_results_dir is not None:
        updated_calculators = []
        for calc in calculators:
            if calc == "cache://_":
                # Point to the renamed directory instead
                updated_calculators.append(f"cache://{renamed_results_dir}")
            else:
                updated_calculators.append(calc)
        calculators = updated_calculators

    # Remember if the original input was a directory
    original_input_was_dir = input_path.is_dir()

    # Generate variable combinations
    from .helpers import generate_variable_combinations
    var_combinations = generate_variable_combinations(input_variables)
    var_names = list(input_variables.keys())

    # Call on_start callback
    if callbacks and 'on_start' in callbacks:
        try:
            callbacks['on_start'](len(var_combinations), calculators)
        except Exception as e:
            log_warning(f"⚠️  Error in on_start callback: {e}")

    # Prepare results structure
    results = {var: [] for var in var_names}
    output_keys = list(model.get("output", {}).keys())
    for key in output_keys:
        results[key] = []
    results["path"] = []
    results["calculator"] = []
    results["status"] = []
    results["error"] = []
    results["command"] = []

    # Create temporary compilation directory
    with fz_temporary_directory(original_cwd) as temp_dir:
        temp_path = Path(temp_dir)

        # Determine if input_variables is non-empty for directory structure decisions
        has_input_variables = bool(input_variables)

        # Compile all combinations directly to result directories, then prepare temp directories
        compile_to_result_directories(
            input_path, model, input_variables, var_combinations, results_dir
        )

        # Create temp directories and copy from result directories (excluding .fz_hash)
        prepare_temp_directories(var_combinations, temp_path, results_dir, has_input_variables)

        # Run calculations in parallel across cases
        try:
            case_results = run_cases_parallel(
                var_combinations,
                temp_path,
                results_dir,
                calculators,
                model,
                original_input_was_dir,
                var_names,
                output_keys,
                original_cwd,
                has_input_variables,
                callbacks,
                timeout,
            )

            # Collect results in the correct order, filtering out None (interrupted/incomplete cases)
            for case_result in case_results:
                # Skip None results (incomplete cases from interrupts)
                if case_result is None:
                    continue

                for var in var_names:
                    results[var].append(case_result["var_combo"][var])

                for key in output_keys:
                    results[key].append(case_result.get(key))

                results["path"].append(case_result.get("path", "."))
                results["calculator"].append(case_result.get("calculator", "unknown"))
                results["status"].append(case_result.get("status", "unknown"))
                results["error"].append(case_result.get("error", None))
                results["command"].append(case_result.get("command", None))

        finally:
            # Cleanup calculators and threading resources
            # IMPORTANT: This must happen BEFORE the fz_temporary_directory() exits
            # otherwise the temp files that cases are trying to copy will be deleted

            # Add a small delay to ensure all file I/O operations from worker threads are complete
            # This prevents race conditions where cleanup happens while threads are still copying files
            time.sleep(0.1)  # 100ms delay to ensure all file operations are complete

            log_debug("🧹 fzr execution completed, cleaning up resources...")
            _cleanup_fzr_resources()

            # Restore signal handler
            _restore_signal_handler()

    # Always restore the original working directory
    os.chdir(original_cwd)

    # Check if interrupted and provide user feedback
    if _interrupt_requested:
        log_warning("⚠️  Execution was interrupted. Partial results may be available.")

    # Always restore the original working directory
    os.chdir(working_dir)

    # Prepare final results
    if PANDAS_AVAILABLE:
        final_results = pd.DataFrame(results)
    else:
        final_results = results

    # Call on_complete callback
    if callbacks and 'on_complete' in callbacks:
        try:
            completed_cases = len([r for r in results["status"] if r is not None])
            callbacks['on_complete'](len(var_combinations), completed_cases, final_results)
        except Exception as e:
            log_warning(f"⚠️  Error in on_complete callback: {e}")

    # Return final results
    return final_results
