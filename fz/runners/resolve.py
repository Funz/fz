"""Calculator URI validation and resolution, timeout resolution."""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from ..io import load_aliases
from ..logging import log_warning
from ..uri import redact_uri
from ..slurm_async import split_slurm_resources
from .ssh import parse_ssh_uri
from .slurm import parse_slurm_uri


def _validate_calculator_uri(calculator_uri: str) -> None:
    """
    Validate calculator URI format and scheme

    Args:
        calculator_uri: Calculator URI string to validate

    Raises:
        ValueError: If URI has invalid format or unsupported scheme
    """
    if not calculator_uri:
        raise ValueError("Calculator URI cannot be empty")

    if not isinstance(calculator_uri, str):
        raise TypeError(f"Calculator URI must be a string, got {type(calculator_uri).__name__}")

    # Check if it has a scheme
    if "://" not in calculator_uri:
        raise ValueError(
            f"Invalid calculator URI format: '{calculator_uri}'. "
            "URI must include a scheme (e.g., 'sh://', 'ssh://', 'cache://', 'slurm://'). "
            "If using a calculator alias, ensure it exists in .fz/calculators/"
        )

    # Extract and validate scheme
    scheme = calculator_uri.split("://", 1)[0].lower()
    supported_schemes = ["sh", "ssh", "cache", "slurm", "slurm-array", "funz"]

    if scheme not in supported_schemes:
        raise ValueError(
            f"Unsupported calculator scheme: '{scheme}'. "
            f"Supported schemes: {', '.join(supported_schemes)}"
        )

    # Validate SSH URI format if scheme is ssh
    if scheme == "ssh":
        try:
            parse_ssh_uri(calculator_uri)
        except ValueError as e:
            raise ValueError(f"Invalid SSH calculator URI: {e}")

    # Validate SLURM URI format if scheme is slurm or slurm-array (resources stripped first)
    if scheme in ("slurm", "slurm-array"):
        try:
            base_uri, _ = split_slurm_resources(calculator_uri)
            parse_slurm_uri(base_uri.replace("slurm-array://", "slurm://", 1))
        except ValueError as e:
            raise ValueError(f"Invalid SLURM calculator URI: {e}")


# Per-process cache of resolved code_id values keyed by (uri, version_cmd),
# so a version_cmd is only actually run once per calculator per session (CLI
# invocation / long-lived process), not once per case.
_code_id_cache: Dict[Tuple[str, str], Optional[str]] = {}
_code_id_cache_lock = threading.Lock()


def _version_cmd_output(uri: str, version_cmd: str, returncode: int, stdout: str, stderr: str) -> Optional[str]:
    """Return the identity printed by a version_cmd, or None if it failed (non-zero exit) or printed nothing.

    The output of a failing command is an error message, never a code identity:
    using it would make two broken installations share cache results."""
    if returncode != 0:
        log_warning(
            f"⚠️  version_cmd {version_cmd!r} for calculator '{redact_uri(uri)}' exited with status "
            f"{returncode}; code identity left undeclared"
        )
        return None
    # Some tools print their version on stderr with a zero exit (e.g. `java -version`)
    return (stdout or "").strip() or (stderr or "").strip() or None


def _run_version_cmd(uri: str, version_cmd: str) -> Optional[str]:
    """Run a calculator alias's version_cmd to resolve its code_id (sh:// and ssh:// only)."""
    scheme = uri.split("://", 1)[0].lower() if "://" in uri else ""
    try:
        if scheme == "sh":
            # FZ_SHELL_PATH lists directories to search for tools; it is not a
            # shell executable, so let fz's own shell handling pick bash.
            from ..shell import run_command
            result = run_command(version_cmd, capture_output=True, timeout=30)
            return _version_cmd_output(uri, version_cmd, result.returncode, result.stdout, result.stderr)

        if scheme == "ssh":
            return _run_version_cmd_ssh(uri, version_cmd)

        log_warning(
            f"⚠️  version_cmd is not supported for calculator scheme '{scheme}://'; "
            "declare 'code_id' explicitly on this calculator alias instead"
        )
        return None
    except Exception as e:
        log_warning(f"⚠️  Could not resolve version_cmd for calculator '{uri}': {e}")
        return None


def _run_version_cmd_ssh(uri: str, version_cmd: str) -> Optional[str]:
    from .ssh import PARAMIKO_AVAILABLE, get_host_key_policy

    if not PARAMIKO_AVAILABLE:
        return None

    import getpass
    import paramiko

    from ..config import get_config

    host, port, username, password, _ = parse_ssh_uri(uri)
    if not host:
        return None
    if not username:
        username = os.getenv("SSH_USER") or getpass.getuser()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(
        get_host_key_policy(password_provided=bool(password), auto_accept=get_config().ssh_auto_accept_hostkeys)
    )
    try:
        client.connect(host, port=port, username=username, password=password, timeout=15)
        _, stdout, stderr = client.exec_command(version_cmd, timeout=30)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        return _version_cmd_output(uri, version_cmd, stdout.channel.recv_exit_status(), out, err)
    finally:
        client.close()


def _resolve_calculator_code_id(calc_data: Optional[Dict], uri: str) -> Optional[str]:
    """Resolve a calculator's declared code identity: its explicit "code_id", or the (cached) output of its "version_cmd"."""
    if not calc_data:
        return None

    code_id = calc_data.get("code_id")
    if code_id:
        return str(code_id)

    version_cmd = calc_data.get("version_cmd")
    if not version_cmd:
        return None

    cache_key = (uri, version_cmd)
    with _code_id_cache_lock:
        if cache_key in _code_id_cache:
            return _code_id_cache[cache_key]

    resolved = _run_version_cmd(uri, version_cmd)

    with _code_id_cache_lock:
        _code_id_cache[cache_key] = resolved
    return resolved


def resolve_calculators_with_metadata(
    calculators: Union[str, List[str], List[Dict]], model_id: str = None
) -> Tuple[List[str], List[Optional[str]]]:
    """
    Resolve calculator aliases to URI strings and validate them, also
    resolving each one's declared code identity (code_id/version_cmd) - see
    fz/io.py's find_cache_match(), which uses it to decide whether a cache://
    match is safe to reuse across calculators.

    Args:
        calculators: Calculator specifications (string, list of strings, or list of dicts)
        model_id: Optional model ID for model-specific calculator commands

    Returns:
        (uris, code_ids): parallel lists - uris[i]'s declared code_id (or
        None) is code_ids[i]

    Raises:
        ValueError: If calculator URI is invalid or alias not found
        TypeError: If calculators have invalid types
    """
    if isinstance(calculators, str):
        if calculators == "*":
            # Find all calculator files
            calc_files = []
            search_dirs = [Path.cwd() / ".fz", Path.home() / ".fz"]
            for base_dir in search_dirs:
                calc_dir = base_dir / "calculators"
                if calc_dir.exists():
                    calc_files.extend([f.stem for f in calc_dir.glob("*.json")])

            # Implicitly include cache calculator as first option when using "*"
            # This ensures cache is checked before running new calculations
            calculators = ["cache://_"] + calc_files
        else:
            calculators = [calculators]

    uris: List[str] = []
    code_ids: List[Optional[str]] = []
    for calc in calculators:
        if isinstance(calc, dict):
            # Direct calculator dict
            uri = calc.get("uri", "sh://")
            # Handle models field if present and model_id provided
            if model_id and "models" in calc and model_id in calc["models"]:
                command = calc["models"][model_id]
                uri = f"{uri}{command}"
            _validate_calculator_uri(uri)
            uris.append(uri)
            code_ids.append(_resolve_calculator_code_id(calc, uri))
        elif isinstance(calc, str):
            if "://" in calc:
                # Direct URI - validate it (no alias data, so no code_id)
                _validate_calculator_uri(calc)
                uris.append(calc)
                code_ids.append(None)
            else:
                # Alias - load from file
                calc_data = load_aliases(calc, "calculators")
                if calc_data:
                    uri = calc_data.get("uri", "sh://")
                    # Handle models field if present and model_id provided
                    if (
                        model_id
                        and "models" in calc_data
                        and model_id in calc_data["models"]
                    ):
                        command = calc_data["models"][model_id]
                        uri = f"{uri}{command}"
                    _validate_calculator_uri(uri)
                    uris.append(uri)
                    code_ids.append(_resolve_calculator_code_id(calc_data, uri))
                else:
                    # Alias not found - raise error with helpful message
                    raise ValueError(
                        f"Calculator alias '{calc}' not found in .fz/calculators/. "
                        f"If this is a URI, it must include a scheme (e.g., 'sh://', 'ssh://', 'cache://')"
                    )
        else:
            raise TypeError(f"Calculator must be a string or dict, got {type(calc).__name__}")
    return uris, code_ids


def resolve_calculators(
    calculators: Union[str, List[str], List[Dict]], model_id: str = None
) -> List[str]:
    """
    Resolve calculator aliases to URI strings and validate them.

    Returns:
        List of validated calculator URI strings

    Raises:
        ValueError: If calculator URI is invalid or alias not found
        TypeError: If calculators have invalid types
    """
    uris, _ = resolve_calculators_with_metadata(calculators, model_id)
    return uris
