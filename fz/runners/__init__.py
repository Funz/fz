"""
Calculation runners for fz package: calculator resolution and execution.

One module per backend (sh, ssh, slurm, funz, cache) behind the abstract
``Calculator`` interface in ``base``; the historical ``fz.runners`` names are
re-exported here.
"""

import platform  # noqa: F401  (kept for ``fz.runners.platform`` patching)

from .base import (
    Calculator,
)  # noqa: F401

from .errors import (
    _SHELL_MISSING_COMMAND_RE,
    _CMD_NOT_RECOGNIZED_RE,
    _MISSING_COMMAND_EXIT_CODES,
    _missing_command,
    _classify_sh_error,
    _classify_ssh_error,
    _classify_slurm_error,
    _classify_funz_error,
    _classify_common_error,
    classify_error,
)  # noqa: F401

from .manager import (
    get_environment_info,
    CalculatorManager,
    _calculator_manager,
    resolve_timeout,
)  # noqa: F401

from .ssh import (
    InteractiveHostKeyPolicy,
    get_host_key_policy,
    validate_ssh_connection_security,
    parse_ssh_uri,
    run_ssh_calculation,
    _transfer_files_to_remote,
    _sftp_mkdir_p,
    transfer_static_files_to_remote_sftp,
    _execute_remote_command,
    _transfer_results_from_remote,
    SshCalculator,
    PARAMIKO_AVAILABLE,
)  # noqa: F401

from .slurm import (
    parse_slurm_uri,
    run_slurm_calculation,
    _run_local_slurm_calculation,
    _run_remote_slurm_calculation,
    _execute_remote_slurm_command,
    SlurmCalculator,
)  # noqa: F401

from .resolve import (
    _validate_calculator_uri,
    resolve_calculators,
)  # noqa: F401

from .sh import (
    resolve_all_paths_in_command,
    _resolve_paths_in_segment,
    run_local_calculation,
    ShCalculator,
)  # noqa: F401

from .funz import (
    _parse_funz_broadcast,
    discover_funz_servers,
    run_funz_calculation,
    FunzCalculator,
)  # noqa: F401

from .cache import (
    run_cache_calculation,
    CacheCalculator,
)  # noqa: F401

from .dispatch import (
    run_calculation,
    select_calculator_for_case,
    run_single_case_calculation,
)  # noqa: F401


__all__ = [
    "Calculator",
    "classify_error",
    "get_environment_info",
    "CalculatorManager",
    "resolve_timeout",
    "InteractiveHostKeyPolicy",
    "get_host_key_policy",
    "validate_ssh_connection_security",
    "parse_ssh_uri",
    "run_ssh_calculation",
    "transfer_static_files_to_remote_sftp",
    "SshCalculator",
    "PARAMIKO_AVAILABLE",
    "parse_slurm_uri",
    "run_slurm_calculation",
    "SlurmCalculator",
    "resolve_calculators",
    "resolve_all_paths_in_command",
    "run_local_calculation",
    "ShCalculator",
    "discover_funz_servers",
    "run_funz_calculation",
    "FunzCalculator",
    "run_cache_calculation",
    "CacheCalculator",
    "run_calculation",
    "select_calculator_for_case",
    "run_single_case_calculation",
]
