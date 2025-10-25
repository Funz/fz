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


# ============================================================================
# Algorithm Installation Functions
# ============================================================================


def install_algo(algorithm, global_install=False):
    """
    Install an algorithm from a source (GitHub name, URL, or local zip file)

    Args:
        algorithm: Algorithm source to install (GitHub name, URL, or local zip file)
                   Examples: "montecarlo", "https://github.com/Funz/fz-montecarlo",
                            "fz-montecarlo.zip"
        global_install: If True, install to ~/.fz/algorithms/, else ./.fz/algorithms/

    Returns:
        Installation result dict with 'algorithm_name' and 'install_path' keys

    Examples:
        >>> install_algo(algorithm='montecarlo')
        >>> install_algo(algorithm='https://github.com/Funz/fz-montecarlo')
        >>> install_algo(algorithm='fz-montecarlo.zip')
        >>> install_algo(algorithm='montecarlo', global_install=True)
    """
    return install_algorithm(algorithm, global_install=global_install)


def uninstall_algo(algorithm, global_uninstall=False):
    """
    Uninstall an algorithm

    Args:
        algorithm: Name of the algorithm to uninstall (without .py or .R extension)
        global_uninstall: If True, uninstall from ~/.fz/algorithms/, else from ./.fz/algorithms/

    Returns:
        True if successful, False otherwise

    Examples:
        >>> uninstall_algo(algorithm='montecarlo')
        >>> uninstall_algo(algorithm='montecarlo', global_uninstall=True)
    """
    return uninstall_algorithm(algorithm, global_uninstall=global_uninstall)


def list_algorithms(global_list=False):
    """
    List installed algorithms

    Args:
        global_list: If True, list from ~/.fz/algorithms/, else from ./.fz/algorithms/

    Returns:
        Dict mapping algorithm names to their info (type, file path, global flag)

    Examples:
        >>> list_algorithms()
        >>> list_algorithms(global_list=True)
    """
    return list_installed_algorithms(global_list=global_list)


__version__ = "0.9.0"
__all__ = [
    "fzi", "fzc", "fzo", "fzr", "fzd",
    "install", "uninstall", "list_models",
    "install_algo", "uninstall_algo", "list_algorithms",
    "set_log_level", "get_log_level",
    "get_config", "reload_config", "print_config",
    "set_interpreter", "get_interpreter",
]