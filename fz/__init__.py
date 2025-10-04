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

__version__ = "0.8.0"
__all__ = [
    "fzi", "fzc", "fzo", "fzr",
    "set_log_level", "get_log_level",
    "get_config", "reload_config", "print_config",
    "set_interpreter", "get_interpreter",
]