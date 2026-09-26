"""Calculator dispatch by URI scheme and per-case execution."""

from pathlib import Path
from typing import Dict, List, Any

from .cache import run_cache_calculation
from .sh import run_local_calculation
from .ssh import run_ssh_calculation
from .slurm import run_slurm_calculation
from .funz import run_funz_calculation


def run_calculation(
    working_dir: Path,
    calculator_uri: str,
    model: Dict,
    timeout: int = None,
    original_input_was_dir: bool = False,
    original_cwd: str = None,
    input_files_list: List[str] = None,
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a single calculation on a calculator

    Args:
        working_dir: Directory containing input files
        calculator_uri: Calculator URI (e.g., "sh://command", "ssh://host/command", "slurm://partition/script")
        model: Model definition dict
        timeout: Timeout in seconds (None resolves via the model's "timeout" entry, then
            FZ_RUN_TIMEOUT from config, default 3600)
        original_input_was_dir: Whether original input was a directory
        input_files_list: List of input file names in order (from .fz_hash)
        static_entries: Pre-resolved input_static entries (see
            helpers.resolve_static_files). Relative entries live outside
            input_path/working_dir (only symlinked there for local execution), so
            remote calculators (ssh/slurm-remote/funz) transfer them explicitly from
            their real source path. Absolute entries are never transferred - assumed
            already present at that path on the calculator side.

    Returns:
        Dict containing calculation results and status
    """
    # Resolution (explicit arg > model's "timeout" entry > config default) happens
    # in the per-protocol run_*_calculation functions, since they accept model too.
    base_uri = calculator_uri

    # Handle different calculator types
    if base_uri.startswith("cache://"):
        # Cache handling is now done at fzr level, this should not be reached
        return run_cache_calculation()

    elif base_uri.startswith("sh://") or base_uri == "sh:":
        # Local shell execution - static_files are already symlinked into
        # working_dir (same filesystem), nothing extra to transfer
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
            working_dir, base_uri, model, timeout, input_files_list, static_entries=static_entries
        )

    elif base_uri.startswith("slurm://"):
        # SLURM execution (local or remote)
        return run_slurm_calculation(
            working_dir, base_uri, model, timeout, input_files_list, static_entries=static_entries
        )

    elif base_uri.startswith("funz://"):
        # Funz server execution
        return run_funz_calculation(
            working_dir, base_uri, model, timeout, input_files_list, static_entries=static_entries
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
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run calculation for a single case on a specific calculator

    Args:
        working_dir: Directory containing input files
        calculator_uri: Calculator URI to use for this case
        model: Model definition dict
        timeout: Timeout in seconds (None resolves via model["timeout"], then FZ_RUN_TIMEOUT config default, 3600)
        original_input_was_dir: Whether original input was a directory
        original_cwd: Original working directory
        input_files_list: List of input file names in order
        static_entries: Pre-resolved input_static entries (see
            helpers.resolve_static_files), force-transferred to remote calculators

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
            static_entries=static_entries,
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
