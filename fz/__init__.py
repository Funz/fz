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

from .core import fzi, fzc, fzo, fzr, check_bash_availability_on_windows

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
)


def install(model, global_install=False):
    """
    Install a model from a source (GitHub name, URL, or local zip file)

    Args:
        model: Model source to install (GitHub name, URL, or local zip file)
        global_install: If True, install to ~/.fz/models/, else ./.fz/models/

    Returns:
        Installation result dict with 'model_name' and 'install_path' keys

    Examples:
        >>> install(model='moret')
        >>> install(model='https://github.com/Funz/fz-moret')
        >>> install(model='fz-moret.zip')
        >>> install(model='moret', global_install=True)
    """
    return install_model(model, global_install=global_install)


def uninstall(model, global_uninstall=False):
    """
    Uninstall a model

    Args:
        model: Name of the model to uninstall
        global_uninstall: If True, uninstall from ~/.fz/models/, else from ./.fz/models/

    Returns:
        True if successful, False otherwise

    Examples:
        >>> uninstall(model='moret')
        >>> uninstall(model='moret', global_uninstall=True)
    """
    return uninstall_model(model, global_uninstall=global_uninstall)


def list_models(global_list=False):
    """
    List installed models

    Args:
        global_list: If True, list from ~/.fz/models/, else from ./.fz/models/

    Returns:
        Dict mapping model names to their definitions

    Examples:
        >>> list_models()
        >>> list_models(global_list=True)
    """
    return list_installed_models(global_list=global_list)


__version__ = "0.9.0"
__all__ = [
    "fzi", "fzc", "fzo", "fzr",
    "install", "uninstall", "list_models",
    "set_log_level", "get_log_level",
    "get_config", "reload_config", "print_config",
    "set_interpreter", "get_interpreter",
]