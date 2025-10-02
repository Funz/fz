"""
Helper functions for fz package - internal utilities for core operations
"""
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple, Union, Any
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed

from .logging import log_debug, log_info, log_warning, log_error, log_progress, get_log_level, LogLevel
from .config import get_config


@contextmanager
def fz_temporary_directory(session_cwd=None):
    """
    Context manager for creating and managing temporary directories
    
    Args:
        session_cwd: Optional current working directory
        
    Yields:
        Path to temporary directory
    """
    import time
    import uuid
    
    # Use centralized temp base directory
    if session_cwd is None:
        session_cwd = os.getcwd()
    
    # Create temp directory structure under .fz/tmp
    fz_tmp_base = Path(session_cwd) / ".fz" / "tmp"
    fz_tmp_base.mkdir(parents=True, exist_ok=True)
    
    # Create unique temp directory name
    pid = os.getpid()
    unique_id = uuid.uuid4().hex[:12]
    timestamp = int(time.time())
    temp_name = f"fz_temp_{unique_id}_{timestamp}"
    temp_dir = fz_tmp_base / temp_name
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield str(temp_dir)
    finally:
        # Skip cleanup of temporary directory to allow inspection of case contents
        # if temp_dir.exists():
        #     shutil.rmtree(temp_dir)
        log_debug(f"🔍 Temporary directory preserved for inspection: {temp_dir}")
        pass


def _get_result_directory(var_combo: Dict, case_index: int, resultsdir: Path, total_cases: int) -> Tuple[Path, str]:
    """
    Get result directory path and case name for a given variable combination
    
    Args:
        var_combo: Variable combination dict
        case_index: Index of this case
        resultsdir: Base results directory
        total_cases: Total number of cases
        
    Returns:
        Tuple of (result_dir_path, case_name)
    """
    if total_cases > 1:
        # Multiple cases: create subdirectory based on variable values
        case_subdir = ",".join(f"{k}={v}" for k, v in var_combo.items())
        result_dir = resultsdir / case_subdir
        case_name = case_subdir
    else:
        # Single case: use base results directory
        result_dir = resultsdir
        case_name = "single case"
    
    return result_dir, case_name


def _get_case_directories(var_combo: Dict, case_index: int, temp_path: Path, resultsdir: Path, total_cases: int) -> Tuple[Path, Path, str]:
    """
    Determine temp and result directory paths for a case
    
    This centralized function ensures consistent directory naming and prevents mixing
    of temp/result directories across the codebase.
    
    Args:
        var_combo: Variable combination dict
        case_index: Index of this case
        temp_path: Base temporary path
        resultsdir: Base results directory
        total_cases: Total number of cases
        
    Returns:
        Tuple of (tmp_dir, result_dir, case_name)
    """
    # Get result directory path and case name
    result_dir, case_name = _get_result_directory(var_combo, case_index, resultsdir, total_cases)
    
    # Temp directory: mirror the result directory structure under temp_path
    if total_cases > 1:
        case_subdir = ",".join(f"{k}={v}" for k, v in var_combo.items())
        tmp_dir = temp_path / case_subdir
    else:
        tmp_dir = temp_path / "single_case"
    
    return tmp_dir, result_dir, case_name


# Global calculator manager instance
_calculator_manager = None

def _cleanup_fzr_resources():
    """Clean up global resources used by fzr"""
    global _calculator_manager
    if _calculator_manager is not None:
        # Force cleanup of all calculator locks
        try:
            _calculator_manager.cleanup_all_calculators()
            log_debug("🧹 CalculatorManager cleanup completed")
        except Exception as e:
            log_warning(f"⚠️ Error during calculator cleanup: {e}")
        _calculator_manager = None


def _resolve_model(model: Union[str, Dict]) -> Dict:
    """
    Resolve model definition from alias or dict
    
    Args:
        model: Model definition dict or alias string
        
    Returns:
        Model definition dict
        
    Raises:
        ValueError: If model alias not found
    """
    if isinstance(model, str):
        from .io import load_aliases
        model_def = load_aliases(model, "models")
        if model_def is None:
            raise ValueError(f"Model alias '{model}' not found in .fz/models/")
        return model_def
    return model


def get_calculator_manager():
    """
    Get or create the global calculator manager instance
    
    Returns:
        CalculatorManager instance
    """
    global _calculator_manager
    if _calculator_manager is None:
        from .core import CalculatorManager
        _calculator_manager = CalculatorManager()
    return _calculator_manager


def try_calculators_with_retry(non_cache_calculator_ids: List[str], case_index: int,
                              tmp_dir: Path, model: Dict, original_input_was_dir: bool,
                              thread_id: int, start_time: float, original_cwd: str = None,
                              input_files_list: List[str] = None) -> Tuple[Dict[str, Any], str]:
    """
    Try calculators with retry mechanism for failed calculations

    Args:
        non_cache_calculator_ids: List of available non-cache calculator IDs
        case_index: Index of the current case
        tmp_dir: Temporary directory path
        model: Model definition
        original_input_was_dir: Whether original input was a directory
        thread_id: Thread ID for logging
        start_time: Case start time
        original_cwd: Original working directory
        input_files_list: List of input file names in order

    Returns:
        Tuple of (calculation result dict, used calculator ID)
    """
    from .runners import run_single_case_calculation
    from .core import is_interrupted

    attempted_calculator_ids = []
    last_error = None

    # Get max retry attempts from configuration
    config = get_config()
    max_attempts = config.max_retries

    # Get calculator manager instance
    calc_mgr = get_calculator_manager()

    for attempt in range(max_attempts):
        # Check for interrupt before each attempt
        if is_interrupted():
            log_warning(f"⚠️ [Thread {thread_id}] Case {case_index}: Interrupted before calculator attempt")
            return {
                "status": "interrupted",
                "error": "Execution interrupted by user",
                "calculator_uri": "interrupted"
            }, "interrupted"
        # Select calculator using thread-safe manager, avoiding previously attempted ones
        available_calc_ids = [calc_id for calc_id in non_cache_calculator_ids if calc_id not in attempted_calculator_ids]
        if not available_calc_ids:
            # All calculators have been tried, pick from the original list
            available_calc_ids = non_cache_calculator_ids

        # Use thread-safe calculator manager to get an available calculator
        # Always use the same case_index for all retry attempts to maintain consistent calculator selection
        selected_calculator_id = calc_mgr.get_available_calculator(
            available_calc_ids, thread_id, case_index
        )

        if selected_calculator_id is None:
            # All calculators are currently busy, wait until one becomes available
            log_debug(f"⏳ [Thread {thread_id}] Case {case_index}: All calculators busy, waiting for one to become free...")

            # Wait with exponential backoff until a calculator becomes available
            wait_time = 0.1
            max_wait = 2.0
            while selected_calculator_id is None:
                time.sleep(wait_time)
                selected_calculator_id = calc_mgr.get_available_calculator(
                    available_calc_ids, thread_id, case_index
                )
                if selected_calculator_id is None:
                    # Increase wait time with exponential backoff, but cap it
                    wait_time = min(wait_time * 1.5, max_wait)
                    continue
                else:
                    selected_calculator_uri = calc_mgr.get_original_uri(selected_calculator_id)
                    log_info(f"✅ [Thread {thread_id}] Case {case_index}: Calculator became available: {selected_calculator_uri}")
                    break

        attempted_calculator_ids.append(selected_calculator_id)
        attempt_label = "retry" if attempt > 0 else "primary"
        selected_calculator_uri = calc_mgr.get_original_uri(selected_calculator_id)
        log_debug(f"🎯 [Thread {thread_id}] Case {case_index}: {attempt_label} attempt with calculator: {selected_calculator_uri}")

        try:
            calc_start = time.time()
            calc_result = run_single_case_calculation(
                tmp_dir, selected_calculator_uri, model, 300, original_input_was_dir, original_cwd, input_files_list
            )
            calc_elapsed = time.time() - calc_start

            log_debug(f"🎯 [Thread {thread_id}] Case {case_index}: Calculator returned in {calc_elapsed:.2f}s: {calc_result.get('status') if calc_result else 'None'}")

            # Check if calculation succeeded
            if calc_result and calc_result.get("status") == "done":
                used_calculator = calc_result.get("calculator_uri", selected_calculator_uri)
                elapsed = time.time() - start_time
                calc_type = "LOCAL" if used_calculator.startswith("sh://") else "REMOTE" if used_calculator.startswith("ssh://") else "CALCULATOR"
                success_label = f"✓ [Thread {thread_id}] Case {case_index}: {calc_type} ({used_calculator}) ({elapsed:.2f}s)"
                if attempt > 0:
                    success_label += f" [RETRY SUCCESS after {attempt} failed attempts]"
                log_info(success_label)
                # Release the calculator when successful
                calc_mgr.release_calculator(selected_calculator_id, thread_id)
                return calc_result, selected_calculator_id

            # Calculation failed - prepare for potential retry
            if calc_result:
                error_msg = calc_result.get("error", "Calculation failed")
                exit_code = calc_result.get("exit_code")
                status = calc_result.get("status", "failed")

                failure_info = f"status={status}"
                if exit_code is not None:
                    failure_info += f", exit_code={exit_code}"

                log_warning(f"⚠️ [Thread {thread_id}] Case {case_index}: Calculator {selected_calculator_uri} failed ({failure_info}): {error_msg}")
                last_error = calc_result
            else:
                log_warning(f"⚠️ [Thread {thread_id}] Case {case_index}: Calculator {selected_calculator_uri} returned None result")
                last_error = {
                    "status": "error",
                    "error": "Calculator returned None result",
                    "calculator_uri": selected_calculator_uri
                }

            # Release the calculator after failed calculation
            calc_mgr.release_calculator(selected_calculator_id, thread_id)

        except Exception as e:
            import traceback
            elapsed = time.time() - start_time
            error_msg = str(e)
            log_error(f"❌ [Thread {thread_id}] Case {case_index}: Calculator {selected_calculator_uri} failed with exception after {elapsed:.2f}s: {error_msg}")

            last_error = {
                "status": "error",
                "error": error_msg,
                "calculator_uri": selected_calculator_uri,
                "error_details": {
                    "calculator": selected_calculator_uri,
                    "tmp_dir": str(tmp_dir),
                    "exception_type": type(e).__name__,
                    "exception_message": error_msg,
                    "traceback": traceback.format_exc()
                }
            }

            # Release the calculator after exception
            calc_mgr.release_calculator(selected_calculator_id, thread_id)

        # If we have more attempts available, continue to retry
        if attempt < max_attempts - 1:
            log_debug(f"🔄 [Thread {thread_id}] Case {case_index}: Will retry with different calculator...")

    # All attempts failed
    final_error = last_error or {
        "status": "error",
        "error": "All calculators failed",
        "calculator_uri": "multiple_failed"
    }

    used_calculator_uri = final_error.get("calculator_uri", "unknown")
    log_error(f"❌ [Thread {thread_id}] Case {case_index}: All {len(attempted_calculator_ids)} calculator attempts failed")
    # Convert calculator IDs back to URIs for logging
    attempted_uris = [calc_mgr.get_original_uri(calc_id) for calc_id in attempted_calculator_ids]
    log_error(f"❌ [Thread {thread_id}] Case {case_index}: Attempted calculators: {attempted_uris}")

    # Return the final error and the last attempted calculator ID
    last_attempted_id = attempted_calculator_ids[-1] if attempted_calculator_ids else "unknown"
    return final_error, last_attempted_id



def run_single_case(case_info: Dict) -> Dict[str, Any]:
    """
    Run a single case calculation

    Args:
        case_info: Dict containing case information

    Returns:
        Dict with case results
    """
    from .runners import select_calculator_for_case, run_single_case_calculation
    from .io import resolve_cache_paths, find_cache_match
    from .core import fzo

    var_combo = case_info["var_combo"]
    case_index = case_info["case_index"]
    temp_path = case_info["temp_path"]
    resultsdir = case_info["resultsdir"]
    calculators = case_info["calculators"]  # Original URIs for compatibility
    calculator_ids = case_info.get("calculator_ids", calculators)  # Unique IDs for locking
    id_to_uri_map = case_info.get("id_to_uri_map", {})  # ID to URI mapping
    model = case_info["model"]
    original_input_was_dir = case_info["original_input_was_dir"]
    output_keys = case_info["output_keys"]
    original_cwd = case_info.get("original_cwd")

    # Get thread ID for debugging
    thread_id = threading.get_ident()

    # Determine case directories using centralized function to prevent mixing
    tmp_dir, result_dir, case_name = _get_case_directories(
        var_combo, case_index, temp_path, resultsdir, len(case_info["total_cases"])
    )

    log_debug(f"🔄 [Thread {thread_id}] Starting {case_name}")
    start_time = time.time()

    # Validate that result directory exists (should have been created in preparation phase)
    if not result_dir.exists():
        log_error(f"❌ [Thread {thread_id}] {case_name}: CRITICAL ERROR - Result directory missing: {result_dir}")
        log_error(f"❌ [Thread {thread_id}] {case_name}: This indicates a serious problem with the preparation phase")
        # Return early with error result since we cannot proceed
        elapsed = time.time() - start_time
        return {
            "var_combo": var_combo,
            "calculator": "error",
            "status": "failed",
            "error": "Result directory missing",
            "command": None
        }

    log_debug(f"🔄 [Thread {thread_id}] {case_name}: tmp_dir={tmp_dir}, result_dir={result_dir}")

    # Check for cache matches first (hash file already created upfront)
    calc_result = None
    used_calculator = None
    current_hash_file = result_dir / ".fz_hash"

    log_debug(f"🔄 [Thread {thread_id}] {case_name}: Checking {len(calculators)} calculators: {calculators}")

    # Find corresponding calculator IDs for cache calculators
    for i, calculator in enumerate(calculators):
        if calculator.startswith("cache://"):
            cache_pattern = calculator[8:]  # Remove "cache://"
            cache_paths = resolve_cache_paths(cache_pattern)

            # Try to find a match in any of the resolved cache directories
            cache_match = None
            for cache_path in cache_paths:
                potential_match = find_cache_match(cache_path, current_hash_file)
                if potential_match:
                    cache_match = potential_match
                    break

            if cache_match:
                try:
                    # Copy all files from matching cache subdirectory to result directory
                    for item in cache_match.iterdir():
                        if item.is_file() and item.name != ".fz_hash":  # Don't overwrite current hash
                            dest_path = result_dir / item.name
                            # Overwrite any existing files (these would be calculation results)
                            shutil.copy2(item, dest_path)

                    # Validate that cached outputs don't contain None values
                    try:
                        cached_output = fzo(result_dir, model)
                        output_keys = list(model.get("output", {}).keys())

                        # Check if any expected output is None
                        has_none_outputs = any(cached_output.get(key) is None for key in output_keys)

                        if has_none_outputs:
                            none_keys = [key for key in output_keys if cached_output.get(key) is None]
                            log_warning(f"⚠️ [Thread {thread_id}] Case {case_index}: Cache contains None outputs for {none_keys}, skipping cache")
                            # Don't use this cache result, continue to next calculator
                            continue

                        log_debug(f"📦 [Thread {thread_id}] Case {case_index}: Cache validated and restored from: {cache_match}")
                        calc_result = {"status": "done"}

                    except Exception as validation_error:
                        log_warning(f"⚠️ [Thread {thread_id}] Case {case_index}: Cache validation failed: {validation_error}, skipping cache")
                        # Don't use this cache result, continue to next calculator
                        continue
                    # Find the corresponding calculator ID for this cache calculator
                    cache_calculator_id = calculator_ids[i] if i < len(calculator_ids) else calculator
                    used_calculator = cache_calculator_id

                    # Display completion info for cache hit
                    elapsed = time.time() - start_time
                    log_info(f"✓ [Thread {thread_id}] Case {case_index}: CACHED from {cache_match} ({elapsed:.2f}s)")

                    break  # Cache hit, skip other calculators

                except Exception as e:
                    log_warning(f"Cache restoration error: {e}")
                    # Continue to next calculator on cache error
                    continue
            else:
                # Cache miss, continue to next calculator
                continue

    # If no cache hit, run calculation with retry mechanism
    if calc_result is None:
        # Filter non-cache calculators from IDs and map them
        non_cache_calculator_ids = []
        for calc_id in calculator_ids:
            original_uri = id_to_uri_map.get(calc_id, calc_id)
            if not original_uri.startswith("cache://"):
                non_cache_calculator_ids.append(calc_id)

        if non_cache_calculator_ids:
            # Read input files list from result_dir/.fz_hash
            input_files_list = []
            hash_file = result_dir / ".fz_hash"
            if hash_file.exists():
                with open(hash_file, 'r') as f:
                    lines = [line.strip() for line in f if line.strip()]
                for line in lines:
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        input_files_list.append(parts[1])

            # Try calculators with retry mechanism using unique IDs
            calc_result, used_calculator_id = try_calculators_with_retry(
                non_cache_calculator_ids, case_index, tmp_dir, model,
                original_input_was_dir, thread_id, start_time, original_cwd, input_files_list
            )
            # Use calculator ID directly (includes #n suffix for duplicate URIs)
            used_calculator = used_calculator_id
        else:
            log_error(f"❌ [Thread {thread_id}] Case {case_index}: No non-cache calculators available")
            calc_result = {
                "status": "error",
                "error": "No non-cache calculators available",
                "calculator_uri": "none"
            }
            used_calculator = "none"

    # Prepare result
    result = {"var_combo": var_combo}

    # Add relative path to results directory
    result["path"] = case_name

    # Always copy files back from temp to result directories, regardless of calculation success/failure
    # This ensures that log.txt and other output files are preserved even for failed calculations
    if calc_result:
        status = calc_result.get("status", "unknown")
        if status == "done":
            log_debug(f"🔄 [Thread {thread_id}] {case_name}: Processing successful result")
        else:
            log_debug(f"🔄 [Thread {thread_id}] {case_name}: Processing failed result (status: {status})")

        # Validate directory integrity before copying
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Validating directory mapping")
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Source (tmp_dir): {tmp_dir}")
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Destination (result_dir): {result_dir}")
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Temp dir exists: {tmp_dir.exists()}")
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Result dir exists: {result_dir.exists()}")

        # Copy calculation results from tmp_dir to result_dir with retry logic
        copy_success = True
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries and copy_success:
            try:
                if tmp_dir.exists():
                    # Validate that result directory already exists (should have been created upfront)
                    if not result_dir.exists():
                        log_error(f"❌ [Thread {thread_id}] {case_name}: CRITICAL ERROR - Result directory does not exist: {result_dir}")
                        log_error(f"❌ [Thread {thread_id}] {case_name}: This indicates a problem with the preparation phase")
                        copy_success = False
                        break

                    files_copied = 0
                    files_skipped = 0
                    # Get list of files once and use it for both debugging and copying
                    all_files = []
                    try:
                        all_files = list(tmp_dir.iterdir())
                    except (OSError, FileNotFoundError) as e:
                        log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Failed to list directory on attempt {retry_count + 1}: {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(0.2 * retry_count)  # Exponential backoff
                            continue
                        else:
                            copy_success = False
                            break

                    file_names = [f.name for f in all_files if f.is_file()]
                    log_debug(f"🔍 [Thread {thread_id}] {case_name}: Files in tmp_dir before copying: {file_names}")

                    # Copy each file from the already-retrieved list
                    for item in all_files:
                        try:
                            if item.is_file() and item.name != ".fz_hash":  # Don't overwrite our hash
                                dest_file = result_dir / item.name

                                # Additional validation: ensure we're copying to the right place
                                if not dest_file.parent == result_dir:
                                    log_error(f"❌ [Thread {thread_id}] {case_name}: DIRECTORY MISMATCH! dest_file.parent={dest_file.parent}, expected result_dir={result_dir}")
                                    copy_success = False
                                    break

                                # Copy the file to the existing result directory
                                shutil.copy2(item, dest_file)
                                files_copied += 1
                                log_debug(f"📁 [Thread {thread_id}] {case_name}: Copied {item.name}: {item} → {dest_file}")

                            else:
                                files_skipped += 1

                        except (OSError, FileNotFoundError) as e:
                            log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Failed to copy {item.name}: {e}")
                            log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Source: {item}, Dest: {dest_file}")
                            log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Source exists: {item.exists()}, Dest dir exists: {dest_file.parent.exists()}")
                            # Continue with other files, don't fail entirely

                    log_debug(f"🔄 [Thread {thread_id}] {case_name}: Copied {files_copied} files, skipped {files_skipped} files")
                    break  # Success, exit retry loop
                else:
                    log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Temp directory does not exist: {tmp_dir}")
                    copy_success = False
                    break
            except Exception as e:
                log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Copy attempt {retry_count + 1} failed: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(0.2 * retry_count)  # Exponential backoff
                else:
                    log_warning(f"⚠️ [Thread {thread_id}] {case_name}: All copy attempts failed")
                    copy_success = False

        # Parse output from the result directory
        parse_success = True
        parse_error = None
        try:
            # Add debugging before parsing
            log_debug(f"🔍 [Thread {thread_id}] {case_name}: About to parse result_dir: {result_dir.absolute()}")
            log_debug(f"🔍 [Thread {thread_id}] {case_name}: result_dir.exists(): {result_dir.exists()}")
            if result_dir.exists():
                files_in_result_dir = [f.name for f in result_dir.iterdir() if f.is_file()]
                log_debug(f"🔍 [Thread {thread_id}] {case_name}: Files in result_dir: {files_in_result_dir}")

            result_output = fzo(result_dir, model)
            log_debug(f"🔄 [Thread {thread_id}] {case_name}: Parsed output: {list(result_output.keys())}")
            for key in output_keys:
                value = result_output.get(key)
                # Extract scalar from pandas Series if applicable
                if hasattr(value, 'iloc'):
                    # It's a pandas Series, extract first (and only) value
                    result[key] = value.iloc[0] if len(value) > 0 else None
                elif isinstance(value, list):
                    # It's a list (dict mode), extract first value
                    result[key] = value[0] if len(value) > 0 else None
                else:
                    # Already a scalar
                    result[key] = value
        except Exception as e:
            log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Could not parse output from result directory: {e}")
            # Add more debugging for parse failures
            log_debug(f"🔍 [Thread {thread_id}] {case_name}: DEBUG - result_dir path: {result_dir}")
            log_debug(f"🔍 [Thread {thread_id}] {case_name}: DEBUG - result_dir.exists(): {result_dir.exists()}")
            if result_dir.exists():
                files_in_result_dir = [f.name for f in result_dir.iterdir() if f.is_file()]
                log_debug(f"🔍 [Thread {thread_id}] {case_name}: DEBUG - Files in result_dir: {files_in_result_dir}")
            parse_success = False
            parse_error = str(e)
            # Fallback to None values
            for key in output_keys:
                result[key] = None

        # Determine final status
        if not copy_success or not parse_success:
            # Post-calculation error occurred
            result["status"] = "error"
            error_message = []
            if not copy_success:
                error_message.append("Failed to copy calculation results")
            if not parse_success:
                error_message.append(f"Failed to parse output: {parse_error}")
            result["error"] = "; ".join(error_message)
            result["calculator"] = used_calculator or "unknown"

            # Preserve additional fields from the calculation result even in error case
            if calc_result:
                if "command" in calc_result:
                    result["command"] = calc_result["command"]

            elapsed = time.time() - start_time
            log_error(f"❌ [Thread {thread_id}] {case_name}: FAILED during post-processing ({elapsed:.2f}s total)")
        else:
            # File copying and parsing successful - use original calculation status
            result["calculator"] = used_calculator or "unknown"
            original_status = calc_result.get("status", "unknown") if calc_result else "unknown"
            result["status"] = original_status

            # Preserve additional fields from the calculation result
            if calc_result:
                for key in ["command", "error", "exit_code", "stderr"]:
                    if key in calc_result:
                        result[key] = calc_result[key]

            elapsed = time.time() - start_time
            if original_status == "done":
                log_info(f"✅ [Thread {thread_id}] {case_name}: COMPLETED successfully ({elapsed:.2f}s total)")
            else:
                log_debug(f"📁 [Thread {thread_id}] {case_name}: Files preserved for failed calculation ({elapsed:.2f}s total)")
    else:
        # Failed calculation - provide detailed error information
        elapsed = time.time() - start_time
        log_error(f"❌ [Thread {thread_id}] {case_name}: FAILED after {elapsed:.2f}s")

        # Extract detailed error information
        if calc_result:
            calculator_used = calc_result.get("calculator_uri", "unknown")
            error_details = calc_result.get("error_details", {})
            status = calc_result.get("status", "unknown")
            error_msg = calc_result.get("error", "No error message")

            case_name = ",".join(f"{k}={v}" for k, v in var_combo.items()) if len(case_info["total_cases"]) > 1 else "single case"
            log_error(f"✗ Calculation FAILED for {case_name}")
            log_error(f"  Calculator: {calculator_used}")
            log_error(f"  Status: {status}")
            log_error(f"  Error: {error_msg}")

            # Print additional details if available
            if error_details:
                if "exit_code" in error_details and error_details["exit_code"] is not None:
                    log_error(f"  Exit code: {error_details['exit_code']}")
                if "stderr" in error_details and error_details["stderr"]:
                    stderr_preview = error_details["stderr"][:200] + "..." if len(error_details["stderr"]) > 200 else error_details["stderr"]
                    log_error(f"  Stderr: {stderr_preview}")
                if "exception_type" in error_details:
                    log_error(f"  Exception: {error_details['exception_type']}")
                if "traceback" in error_details:
                    # Just show the last few lines of traceback
                    tb_lines = error_details["traceback"].strip().split('\n')
                    if len(tb_lines) > 3:
                        log_error(f"  Traceback (last 3 lines):")
                        for line in tb_lines[-3:]:
                            log_error(f"    {line}")
                    else:
                        log_error(f"  Traceback: {error_details['traceback']}")

            # Store error in result using "error" key as specified
            result["calculator"] = calculator_used
            result["error"] = error_msg
            # Keep error_details for debugging purposes
            if error_details:
                result["error_details"] = error_details

            # Preserve additional fields from the calculation result
            if "command" in calc_result:
                result["command"] = calc_result["command"]
        else:
            case_name = ",".join(f"{k}={v}" for k, v in var_combo.items()) if len(case_info["total_cases"]) > 1 else "single case"
            log_error(f"✗ Calculation FAILED for {case_name}: No calculators available or all failed")
            result["calculator"] = "no_calculators"
            result["error"] = "No calculators available or all failed"

        # Set all output values to None for failed calculations
        for key in output_keys:
            result[key] = None
        result["status"] = "error"

    # Clean up tmp_dir after calculation (unless in DEBUG mode)
    from .logging import get_log_level, LogLevel
    if get_log_level() != LogLevel.DEBUG:
        if tmp_dir.exists():
            try:
                shutil.rmtree(tmp_dir)
                log_debug(f"🧹 [Thread {thread_id}] {case_name}: Cleaned up temp directory: {tmp_dir}")
            except Exception as e:
                log_warning(f"⚠️ [Thread {thread_id}] {case_name}: Could not clean up temp directory {tmp_dir}: {e}")
    else:
        log_debug(f"🔍 [Thread {thread_id}] {case_name}: Temporary directory preserved for inspection: {tmp_dir}")

    return result



def run_cases_parallel(var_combinations: List[Dict], temp_path: Path, resultsdir: Path,
                      calculators: List[str], model: Dict, original_input_was_dir: bool,
                      var_names: List[str], output_keys: List[str], original_cwd: str = None) -> List[Dict[str, Any]]:
    """
    Run multiple cases in parallel across available calculators

    Args:
        var_combinations: List of variable combinations (cases)
        temp_path: Temporary path with compiled inputs
        resultsdir: Results directory
        calculators: List of calculator URIs
        model: Model definition
        original_input_was_dir: Whether original input was a directory
        var_names: List of variable names
        output_keys: List of output keys

    Returns:
        List of case results in the same order as var_combinations
    """
    from .core import is_interrupted

    if not var_combinations:
        return []

    # Get calculator manager instance
    calc_mgr = get_calculator_manager()

    # Register calculator instances with unique IDs to handle duplicate URIs
    calculator_ids = calc_mgr.register_calculator_instances(calculators)

    log_info(f"🚀 Starting parallel execution of {len(var_combinations)} cases")
    log_info(f"🚀 Available calculators: {calculators}")

    # Map calculator IDs back to original URIs for case processing
    id_to_uri_map = {calc_id: calc_mgr.get_original_uri(calc_id) for calc_id in calculator_ids}

    # Prepare case information for each case
    case_infos = []
    for i, var_combo in enumerate(var_combinations):
        case_info = {
            "var_combo": var_combo,
            "case_index": i,
            "temp_path": temp_path,
            "resultsdir": resultsdir,
            "calculators": calculators,  # Keep original for compatibility
            "calculator_ids": calculator_ids,  # Add unique calculator IDs
            "id_to_uri_map": id_to_uri_map,  # Add mapping for conversion
            "model": model,
            "original_input_was_dir": original_input_was_dir,
            "output_keys": output_keys,
            "total_cases": var_combinations,
            "original_cwd": original_cwd
        }
        case_infos.append(case_info)
        case_name = ",".join(f"{k}={v}" for k, v in var_combo.items()) if len(var_combinations) > 1 else "single case"
        log_info(f"🚀 Case {i}: {case_name}")

    # Determine number of worker threads (number of non-cache calculators)
    non_cache_calculators = [calc for calc in calculators if not calc.startswith("cache://")]
    config = get_config()

    # Calculate max workers based on configuration and available resources
    if config.max_workers is not None:
        # Use configured max workers, but don't exceed available calculators or cases
        max_workers = min(config.max_workers, len(non_cache_calculators), len(var_combinations)) if non_cache_calculators else 1
    else:
        # Default behavior: use number of calculators, limited by number of cases
        max_workers = min(len(non_cache_calculators), len(var_combinations)) if non_cache_calculators else 1

    log_info(f"🚀 Execution plan: {len(var_combinations)} cases, {len(non_cache_calculators)} calculators, {max_workers} workers")

    # Track timing
    start_time = time.time()

    # Show initial progress for multiple cases
    if len(var_combinations) > 1:
        log_progress(f"📊 Progress: 0/{len(var_combinations)} cases completed (0.0%)")

    # Run cases in parallel
    if len(var_combinations) == 1 or max_workers == 1:
        # Single case or single calculator - run sequentially
        log_info(f"🚀 Running sequentially (single case or single calculator)")
        results = []
        for i, case_info in enumerate(case_infos):
            # Check for interrupt before starting next case
            if is_interrupted():
                log_warning(f"⚠️  Interrupt detected. Stopping after {i} completed cases.")
                break

            case_start_time = time.time()
            result = run_single_case(case_info)
            results.append(result)

            # Progress tracking for multiple cases
            if len(var_combinations) > 1:
                completed_count = i + 1
                case_elapsed = time.time() - case_start_time
                total_elapsed = time.time() - start_time

                # Estimate remaining time based on average time per case
                if completed_count > 0:
                    avg_time_per_case = total_elapsed / completed_count
                    remaining_cases = len(var_combinations) - completed_count
                    estimated_remaining = avg_time_per_case * remaining_cases

                    # Format time estimates
                    def format_time(seconds):
                        if seconds < 60:
                            return f"{seconds:.1f}s"
                        elif seconds < 3600:
                            return f"{seconds/60:.1f}m"
                        else:
                            return f"{seconds/3600:.1f}h"

                    log_progress(f"📊 Progress: {completed_count}/{len(var_combinations)} cases completed "
                           f"({completed_count/len(var_combinations)*100:.1f}%), "
                           f"ETA: {format_time(estimated_remaining)}")

        elapsed = time.time() - start_time
        if is_interrupted():
            log_warning(f"⚠️  Sequential execution interrupted after {elapsed:.2f}s. Completed {len(results)}/{len(var_combinations)} cases.")
        else:
            log_info(f"🏁 Sequential execution completed in {elapsed:.2f}s")
        return results
    else:
        # Multiple cases and calculators - run in parallel
        log_info(f"🚀 Running in parallel with {max_workers} threads")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                # Submit all cases
                future_to_index = {
                    executor.submit(run_single_case, case_info): i
                    for i, case_info in enumerate(case_infos)
                }
                log_info(f"🚀 Submitted {len(future_to_index)} tasks to thread pool")

                # Collect results in order
                case_results = [None] * len(var_combinations)
                completed_count = 0

                # Helper function to format time
                def format_time(seconds):
                    if seconds < 60:
                        return f"{seconds:.1f}s"
                    elif seconds < 3600:
                        return f"{seconds/60:.1f}m"
                    else:
                        return f"{seconds/3600:.1f}h"

                for future in as_completed(future_to_index):
                    # Check for interrupt
                    if is_interrupted():
                        log_warning(f"⚠️  Interrupt detected during parallel execution.")
                        log_warning(f"⚠️  Cancelling remaining {len(future_to_index) - completed_count} tasks...")

                        # Cancel all pending futures
                        for pending_future in future_to_index.keys():
                            if not pending_future.done():
                                pending_future.cancel()

                        # Force shutdown of executor
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    completed_count += 1
                    index = future_to_index[future]
                    current_time = time.time()
                    total_elapsed = current_time - start_time

                    try:
                        case_results[index] = future.result()

                        # Enhanced progress tracking with time estimation
                        if len(var_combinations) > 1:
                            # Calculate ETA based on average time per case
                            if completed_count > 0:
                                avg_time_per_case = total_elapsed / completed_count
                                remaining_cases = len(var_combinations) - completed_count
                                estimated_remaining = avg_time_per_case * remaining_cases

                                progress_pct = (completed_count / len(var_combinations)) * 100

                                # Show periodic progress updates
                                if remaining_cases == 0:
                                    log_progress(f"📊 Progress: {completed_count}/{len(var_combinations)} cases completed (100.0%)")
                                elif completed_count % max(1, len(var_combinations) // 10) == 0 or remaining_cases <= 5:
                                    log_progress(f"📊 Progress: {completed_count}/{len(var_combinations)} cases completed "
                                           f"({progress_pct:.1f}%), ETA: {format_time(estimated_remaining)}")
                                else:
                                    log_debug(f"🏁 Task {index} completed successfully ({completed_count}/{len(var_combinations)})")
                            else:
                                log_debug(f"🏁 Task {index} completed successfully ({completed_count}/{len(var_combinations)})")
                        else:
                            log_info(f"🏁 Task {index} completed successfully ({completed_count}/{len(var_combinations)})")

                    except Exception as e:
                        import traceback
                        log_error(f"🏁 Task {index} failed with exception ({completed_count}/{len(var_combinations)}): {e}")
                        log_error(f"🏁 Traceback: {traceback.format_exc()}")
                        # Create failed result
                        var_combo = var_combinations[index]
                        failed_result = {"var_combo": var_combo}
                        for key in output_keys:
                            failed_result[key] = None
                        failed_result["calculator"] = "error"
                        failed_result["status"] = "error"
                        failed_result["error_message"] = str(e)
                        failed_result["command"] = None
                        case_results[index] = failed_result

                        # Show progress for failed cases too
                        if len(var_combinations) > 1:
                            if completed_count > 0:
                                avg_time_per_case = total_elapsed / completed_count
                                remaining_cases = len(var_combinations) - completed_count
                                estimated_remaining = avg_time_per_case * remaining_cases
                                progress_pct = (completed_count / len(var_combinations)) * 100

                                if remaining_cases == 0:
                                    log_progress(f"📊 Progress: {completed_count}/{len(var_combinations)} cases completed (100.0%)")
                                elif completed_count % max(1, len(var_combinations) // 10) == 0 or remaining_cases <= 5:
                                    log_progress(f"📊 Progress: {completed_count}/{len(var_combinations)} cases completed "
                                           f"({progress_pct:.1f}%), ETA: {format_time(estimated_remaining)}")

                elapsed = time.time() - start_time
                if is_interrupted():
                    log_warning(f"⚠️  Parallel execution interrupted after {elapsed:.2f}s")
                    # Filter out None results from incomplete cases
                    completed_results = [r for r in case_results if r is not None]
                    log_warning(f"⚠️  Completed {len(completed_results)}/{len(var_combinations)} cases before interrupt")
                else:
                    log_info(f"🏁 Parallel execution completed in {elapsed:.2f}s")

                # Add explicit shutdown to ensure all threads complete their work
                log_debug(f"🧹 ThreadPoolExecutor shutting down {max_workers} threads...")
                executor.shutdown(wait=True)
                log_debug(f"🧹 All worker threads have completed")

                return case_results
            except Exception as e:
                log_error(f"❌ Error in parallel execution: {e}")
                # Ensure shutdown even if there's an exception
                executor.shutdown(wait=True)
                raise



def compile_to_result_directories(input_path: str, model: Dict, varvalues: Dict,
                                 engine: str, var_combinations: List[Dict],
                                 resultsdir: Path) -> None:
    """
    Compile input files directly to result directories for each case

    Args:
        input_path: Path to input file or directory
        model: Model definition dict
        varvalues: Dict of variable values
        engine: Engine for formula evaluation
        var_combinations: List of variable combinations (cases)
        resultsdir: Results directory
    """
    from .engine import replace_variables_in_content, evaluate_formulas
    from .io import create_hash_file

    varprefix = model.get("varprefix", "$")
    delim = model.get("delim", "()")
    input_path = Path(input_path)

    # Ensure main results directory exists
    resultsdir.mkdir(parents=True, exist_ok=True)

    for case_index, var_combo in enumerate(var_combinations):
        # Use dedicated result directory function to avoid any temp_path contamination
        result_dir, case_name = _get_result_directory(
            var_combo, case_index, resultsdir, len(var_combinations)
        )

        # Create result directory
        result_dir.mkdir(parents=True, exist_ok=True)

        def compile_file(src_path: Path, dst_path: Path):
            try:
                with open(src_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Copy binary files as-is
                shutil.copy2(src_path, dst_path)
                return

            # Replace variables
            content = replace_variables_in_content(content, var_combo, varprefix, delim)

            # Evaluate formulas
            content = evaluate_formulas(content, model, var_combo, engine)

            # Write compiled content
            with open(dst_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Compile files to result directory and track input file names in order
        input_files_list = []
        if input_path.is_file():
            dst_path = result_dir / input_path.name
            compile_file(input_path, dst_path)
            input_files_list.append(input_path.name)
        elif input_path.is_dir():
            # Copy directory structure
            for src_file in input_path.rglob("*"):
                if src_file.is_file():
                    rel_path = src_file.relative_to(input_path)
                    dst_file = result_dir / rel_path
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    compile_file(src_file, dst_file)
                    input_files_list.append(str(rel_path))

        # Create hash file of compiled input files with input files in order
        try:
            create_hash_file(result_dir, input_files_list)
            log_info(f"Created result hash file: {result_dir}/.fz_hash")
        except Exception as e:
            log_warning(f"Warning: Could not create hash file for case {var_combo}: {e}")



def prepare_temp_directories(var_combinations: List[Dict], temp_path: Path, resultsdir: Path) -> None:
    """
    Create temporary directories and copy files from result directories (excluding .fz_hash)

    Args:
        var_combinations: List of variable combinations (cases)
        temp_path: Temporary path for calculations
        resultsdir: Results directory with compiled files and hashes
    """
    for case_index, var_combo in enumerate(var_combinations):
        # Use centralized directory determination
        tmp_dir, result_dir, case_name = _get_case_directories(
            var_combo, case_index, temp_path, resultsdir, len(var_combinations)
        )

        # Create temp directory for this case, cleaning up any existing files first
        if tmp_dir.exists():
            # Clean up existing temp directory to ensure no stale files remain
            try:
                shutil.rmtree(tmp_dir)
                log_debug(f"Cleaned up existing temp directory: {tmp_dir}")
            except Exception as e:
                log_warning(f"Warning: Could not clean up existing temp directory {tmp_dir}: {e}")

        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Copy files from result directory to temp directory (excluding .fz_hash)
        try:
            if result_dir.exists():
                files_copied = 0
                for item in result_dir.iterdir():
                    if item.is_file() and item.name != ".fz_hash":
                        shutil.copy2(item, tmp_dir)
                        files_copied += 1

                log_debug(f"Prepared temp directory: {tmp_dir} ({files_copied} files copied from {result_dir})")
        except Exception as e:
            log_warning(f"Warning: Could not copy files to temp directory for case {var_combo}: {e}")



def prepare_case_directories(var_combinations: List[Dict], temp_path: Path, resultsdir: Path) -> None:
    """
    Create result directories and compute hashes for all cases upfront

    Args:
        var_combinations: List of variable combinations (cases)
        temp_path: Temporary path with compiled inputs
        resultsdir: Results directory
    """
    from .io import create_hash_file

    # Ensure main results directory exists first
    resultsdir.mkdir(parents=True, exist_ok=True)

    for case_index, var_combo in enumerate(var_combinations):
        # Use centralized directory determination to ensure consistency
        tmp_dir, result_dir, case_name = _get_case_directories(
            var_combo, case_index, temp_path, resultsdir, len(var_combinations)
        )

        # Create result directory (parent already exists, so this should be safe)
        result_dir.mkdir(parents=True, exist_ok=True)

        # Copy compiled input files to result directory (excluding .fz_hash)
        try:
            if tmp_dir.exists():
                for item in tmp_dir.iterdir():
                    if item.is_file() and item.name != ".fz_hash":
                        shutil.copy2(item, result_dir)
        except Exception as e:
            log_warning(f"Warning: Could not copy input files for case {var_combo}: {e}")

        # Create hash file of input files
        try:
            create_hash_file(result_dir)
            log_info(f"Created result hash file: {result_dir}/.fz_hash")
        except Exception as e:
            log_warning(f"Warning: Could not create hash file for case {var_combo}: {e}")

