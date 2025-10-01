"""
fz: Parametric scientific computing framework

A Python package for wrapping parametric simulations with support for:
- Parsing input files with variables and formulas
- Compiling input files with variable values
- Running calculations on local/remote resources with parallel execution
- Graceful interrupt handling (Ctrl+C)
- Reading and parsing output results
- Smart caching and retry mechanisms
"""

from .core import fzi, fzc, fzo, fzr
from .io import (
    ensure_unique_directory,
    create_hash_file,
    resolve_cache_paths,
    find_cache_match,
    load_aliases
)
from .engine import (
    parse_variables_from_content,
    parse_variables_from_file,
    parse_variables_from_path,
    replace_variables_in_content,
    evaluate_formulas,
    cast_output
)
from .runners import (
    resolve_calculators,
    run_calculation,
    run_local_calculation,
    run_ssh_calculation,
    parse_ssh_uri,
    validate_ssh_connection_security
)
from .logging import (
    LogLevel,
    set_log_level,
    get_log_level,
    set_log_level_from_string,
    log_error,
    log_warning,
    log_info,
    log_debug,
    log_progress
)
from .config import (
    get_config,
    reload_config,
    print_config,
    DefaultFormulaEngine
)

__version__ = "0.8.0"
__all__ = [
    "fzi", "fzc", "fzo", "fzr",
    "ensure_unique_directory", "create_hash_file",
    "resolve_cache_paths", "find_cache_match", "load_aliases",
    "parse_variables_from_content", "parse_variables_from_file", "parse_variables_from_path",
    "replace_variables_in_content", "evaluate_formulas", "cast_output",
    "resolve_calculators", "run_calculation", "run_local_calculation", "run_ssh_calculation",
    "parse_ssh_uri", "validate_ssh_connection_security",
    "LogLevel", "set_log_level", "get_log_level", "set_log_level_from_string",
    "log_error", "log_warning", "log_info", "log_debug", "log_progress",
    "get_config", "reload_config", "print_config", "DefaultFormulaEngine"
]