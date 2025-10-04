"""
Core functions for fz package: fzi, fzc, fzo, fzr
"""

import os
import re
import shutil
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

import itertools
import threading
from collections import defaultdict

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
from .io import (
    ensure_unique_directory,
    create_hash_file,
    resolve_cache_paths,
    find_cache_match,
    load_aliases,
)
from .engine import (
    parse_variables_from_path,
    replace_variables_in_content,
    evaluate_formulas,
    cast_output,
)
from .runners import resolve_calculators, run_calculation


# Global interrupt flag for graceful shutdown
_interrupt_requested = False
_original_sigint_handler = None


def _signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully"""
    global _interrupt_requested
    if not _interrupt_requested:
        _interrupt_requested = True
        log_warning("\n⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...")
        log_warning("⚠️  Press Ctrl+C again to force quit (not recommended)")
    else:
        log_error("\n❌ Force quit requested. Exiting immediately...")
        # Restore original handler and re-raise
        if _original_sigint_handler:
            signal.signal(signal.SIGINT, _original_sigint_handler)
        raise KeyboardInterrupt()


def _install_signal_handler():
    """Install custom SIGINT handler"""
    global _original_sigint_handler
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


def fzi(input_path: str, model: Union[str, Dict]) -> Dict[str, None]:
    """
    Parse input file(s) to find variables

    Args:
        input_path: Path to input file or directory
        model: Model definition dict or alias string

    Returns:
        Dict of variable names with None values
    """
    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    try:
        model = _resolve_model(model)

        varprefix = model.get("varprefix", "$")
        delim = model.get("delim", "()")

        input_path = Path(input_path).resolve()
        variables = parse_variables_from_path(input_path, varprefix, delim)

        return {var: None for var in sorted(variables)}
    finally:
        # Always restore the original working directory
        os.chdir(working_dir)


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
    """

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    model = _resolve_model(model)

    # Get the global formula interpreter
    from .config import get_interpreter
    interpreter = get_interpreter()

    varprefix = model.get("varprefix", "$")
    delim = model.get("delim", "()")

    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()

    # Ensure output directory is unique (rename existing with timestamp)
    output_dir, _ = ensure_unique_directory(output_dir)

    # Generate all combinations if lists are provided
    var_combinations = []
    var_names = list(input_variables.keys())

    # Check if any values are lists
    has_lists = any(isinstance(v, list) for v in input_variables.values())

    if has_lists:
        # Convert single values to lists for consistency
        list_values = []
        for var in var_names:
            val = input_variables[var]
            if isinstance(val, list):
                list_values.append(val)
            else:
                list_values.append([val])

        # Generate cartesian product
        for combination in itertools.product(*list_values):
            var_combinations.append(dict(zip(var_names, combination)))
    else:
        var_combinations = [input_variables]

    for i, var_combo in enumerate(var_combinations):
        # Create output subdirectory for this combination
        if len(var_combinations) > 1:
            subdir_name = ",".join(f"{k}={v}" for k, v in var_combo.items())
            current_output_dir = output_dir / subdir_name
        else:
            current_output_dir = output_dir

        current_output_dir.mkdir(parents=True, exist_ok=True)

        def compile_file(src_path: Path, dst_path: Path):
            try:
                with open(src_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Copy binary files as-is
                shutil.copy2(src_path, dst_path)
                return

            # Replace variables
            content = replace_variables_in_content(content, var_combo, varprefix, delim)

            # Evaluate formulas
            content = evaluate_formulas(content, model, var_combo, interpreter)

            # Write compiled content
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(content)

        if input_path.is_file():
            dst_path = current_output_dir / input_path.name
            compile_file(input_path, dst_path)
        elif input_path.is_dir():
            # Copy directory structure
            for src_file in input_path.rglob("*"):
                if src_file.is_file():
                    rel_path = src_file.relative_to(input_path)
                    dst_file = current_output_dir / rel_path
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    compile_file(src_file, dst_file)

        # Create hash file after compilation
        create_hash_file(current_output_dir)

    # Always restore the original working directory
    os.chdir(working_dir)


def fzo(
    output_path: str, model: Union[str, Dict]
) -> Union[Dict[str, Any], "pandas.DataFrame"]:
    """
    Read and parse output file(s) according to model

    Args:
        output_path: Path to output file or directory
        model: Model definition dict or alias string

    Returns:
        DataFrame with rows for each subdirectory (if any) with 'path' column (relative to output_dir)
        and columns for each parsed output. If no subdirectories, returns single row with '.' as path.
        If pandas not available, returns dict for backward compatibility.
    """

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    model = _resolve_model(model)
    output_spec = model.get("output", {})

    output_path = Path(output_path).resolve()
    rows = []  # List of dicts, one per subdirectory (or single row if no subdirs)

    # Compute output_path relative to original launch directory for path column
    try:
        if output_path.is_absolute():
            output_path_rel = output_path.relative_to(working_dir)
        else:
            output_path_rel = output_path
    except ValueError:
        # output_path is outside original launch directory, use as-is
        output_path_rel = output_path

    # Determine the working directory for commands and find subdirectories
    if output_path.is_file():
        work_dir = output_path.parent
        subdirs = []
        # For single file case, path should be the file itself
        path_for_no_subdirs = str(output_path_rel)
    elif output_path.is_dir():
        work_dir = output_path
        # For directory with no subdirs, path should be the directory itself
        path_for_no_subdirs = str(output_path_rel)
        # Find all subdirectories and sort them to match fzr() creation order
        # fzr() creates directories in the order of itertools.product()
        # Directory names follow pattern: key1=val1,key2=val2,...
        # We need to sort by parsing the key=value pairs and sorting by tuple of values
        def parse_dir_name(dirname: str):
            """Parse 'key1=val1,key2=val2' into list of values in original order"""
            parts = dirname.split(',')
            values = []
            for part in parts:
                if '=' in part:
                    key, val = part.split('=', 1)
                    # Try to convert to numeric for proper sorting
                    try:
                        if '.' in val:
                            val_sorted = float(val)
                        else:
                            val_sorted = int(val)
                    except ValueError:
                        val_sorted = val
                    values.append(val_sorted)
            # Return values in their original order (matches the order in directory name)
            return tuple(values)

        all_dirs = [d for d in output_path.iterdir() if d.is_dir()]
        subdirs = sorted(all_dirs, key=lambda d: parse_dir_name(d.name))
    else:
        raise FileNotFoundError(f"Output path '{output_path}' not found")

    # If there are subdirectories, create one row per subdirectory
    if subdirs:
        for subdir in subdirs:
            subdir_name = subdir.name
            # Build full relative path from original launch directory
            full_rel_path = output_path_rel / subdir_name
            row = {"path": str(full_rel_path)}  # Full relative path to subdirectory

            for key, command in output_spec.items():
                try:
                    # Execute shell command in subdirectory (use absolute path for cwd)
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=str(subdir.absolute()),
                    )

                    if result.returncode == 0:
                        raw_output = result.stdout.strip()
                        # Try to cast to appropriate Python type
                        parsed_value = cast_output(raw_output)
                        row[key] = parsed_value
                    else:
                        log_warning(
                            f"Warning: Command for '{subdir_name}/{key}' failed: {result.stderr}"
                        )
                        row[key] = None

                except Exception as e:
                    log_warning(
                        f"Warning: Error executing command for '{subdir_name}/{key}': {e}"
                    )
                    row[key] = None

            rows.append(row)
    else:
        # No subdirectories, create single row with output path
        row = {"path": path_for_no_subdirs}

        for key, command in output_spec.items():
            try:
                # Execute shell command in work_dir (use absolute path for cwd)
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, cwd=str(work_dir.absolute())
                )

                if result.returncode == 0:
                    raw_output = result.stdout.strip()
                    # Try to cast to appropriate Python type
                    parsed_value = cast_output(raw_output)
                    row[key] = parsed_value
                else:
                    log_warning(
                        f"Warning: Command for '{key}' failed: {result.stderr}"
                    )
                    row[key] = None

            except Exception as e:
                log_warning(f"Warning: Error executing command for '{key}': {e}")
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


def fzr(
    input_path: str,
    input_variables: Dict,
    model: Union[str, Dict],
    results_dir: str = "results",
    calculators: Union[str, List[str]] = None,
) -> Union[Dict[str, List[Any]], "pandas.DataFrame"]:
    """
    Run full parametric calculations

    Args:
        input_path: Path to input file or directory
        input_variables: Dict of variable values or lists of values for grid
        model: Model definition dict or alias string
        results_dir: Results directory
        calculators: Calculator specifications

    Returns:
        DataFrame with variable values and results (if pandas available), otherwise Dict with lists
    """

    # This represents the directory from which the function was launched
    working_dir = os.getcwd()

    # Install signal handler for graceful interrupt handling
    global _interrupt_requested
    _interrupt_requested = False
    _install_signal_handler()

    # Capture the session working directory (where fzr was called from)
    original_cwd = os.getcwd()

    model = _resolve_model(model)

    # Get the global formula interpreter
    from .config import get_interpreter
    interpreter = get_interpreter()

    if calculators is None:
        calculators = ["sh://"]

    # Get model ID for calculator resolution
    model_id = model.get("id") if isinstance(model, dict) else None
    calculators = resolve_calculators(calculators, model_id)

    # Convert to absolute paths immediately while we're in the correct working directory
    input_path = Path(input_path).resolve()
    results_dir = Path(results_dir).resolve()

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
    var_names = list(input_variables.keys())
    has_lists = any(isinstance(v, list) for v in input_variables.values())

    if has_lists:
        list_values = []
        for var in var_names:
            val = input_variables[var]
            if isinstance(val, list):
                list_values.append(val)
            else:
                list_values.append([val])

        var_combinations = [
            dict(zip(var_names, combo)) for combo in itertools.product(*list_values)
        ]
    else:
        var_combinations = [input_variables]

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

        # Compile all combinations directly to result directories, then prepare temp directories
        compile_to_result_directories(
            input_path, model, input_variables, var_combinations, results_dir
        )

        # Create temp directories and copy from result directories (excluding .fz_hash)
        prepare_temp_directories(var_combinations, temp_path, results_dir)

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

    # Return DataFrame if pandas is available, otherwise return list of dicts
    if PANDAS_AVAILABLE:
        return pd.DataFrame(results)
    else:
        return results
