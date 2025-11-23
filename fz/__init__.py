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

from .core import fzi, fzc, fzo, fzr, fzd, check_bash_availability_on_windows

# Check bash availability on Windows at import time
# This ensures users get immediate feedback if bash is not available
check_bash_availability_on_windows()
from .logging import (
    set_log_level,
    get_log_level,
)
from .config import (
    get_config,
    reload_config,
    print_config,
    set_interpreter,
    get_interpreter,
)
from .installer import (
    install_model,
    uninstall_model,
    list_installed_models,
    install_algorithm,
    uninstall_algorithm,
    list_installed_algorithms,
)

__version__ = "0.9.0"
__all__ = [
    "fzi", "fzc", "fzo", "fzr", "fzd",
    "install_model", "uninstall_model", "list_installed_models",
    "install_algorithm", "uninstall_algorithm", "list_installed_algorithms",
    "set_log_level", "get_log_level",
    "get_config", "reload_config", "print_config",
    "set_interpreter", "get_interpreter",
]