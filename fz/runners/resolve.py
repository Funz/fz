"""Calculator URI validation and resolution, timeout resolution."""

from pathlib import Path
from typing import Dict, List, Union

from ..io import load_aliases
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
    supported_schemes = ["sh", "ssh", "cache", "slurm", "funz"]

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

    # Validate SLURM URI format if scheme is slurm
    if scheme == "slurm":
        try:
            parse_slurm_uri(calculator_uri)
        except ValueError as e:
            raise ValueError(f"Invalid SLURM calculator URI: {e}")


def resolve_calculators(
    calculators: Union[str, List[str], List[Dict]], model_id: str = None
) -> List[str]:
    """
    Resolve calculator aliases to URI strings and validate them

    Args:
        calculators: Calculator specifications (string, list of strings, or list of dicts)
        model_id: Optional model ID for model-specific calculator commands

    Returns:
        List of validated calculator URI strings

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

    result = []
    for calc in calculators:
        if isinstance(calc, dict):
            # Direct calculator dict
            uri = calc.get("uri", "sh://")
            # Handle models field if present and model_id provided
            if model_id and "models" in calc and model_id in calc["models"]:
                command = calc["models"][model_id]
                uri = f"{uri}{command}"
            _validate_calculator_uri(uri)
            result.append(uri)
        elif isinstance(calc, str):
            if "://" in calc:
                # Direct URI - validate it
                _validate_calculator_uri(calc)
                result.append(calc)
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
                    result.append(uri)
                else:
                    # Alias not found - raise error with helpful message
                    raise ValueError(
                        f"Calculator alias '{calc}' not found in .fz/calculators/. "
                        f"If this is a URI, it must include a scheme (e.g., 'sh://', 'ssh://', 'cache://')"
                    )
        else:
            raise TypeError(f"Calculator must be a string or dict, got {type(calc).__name__}")
    return result
