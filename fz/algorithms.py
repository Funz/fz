"""
Algorithm framework for iterative design of experiments (fzd)

This module provides the base interface and utilities for algorithms used with fzd.

Algorithm Interface:
-------------------
Each algorithm must be a class with the following methods:

1. __init__(self, **options):
   Constructor that accepts algorithm-specific options

2. get_initial_design(self, input_vars, output_vars):
   Returns initial design of experiments
   Args:
       input_vars: Dict[str, tuple] - {var_name: (min, max)}
                   e.g., {"x": (0.0, 1.0), "y": (-5.0, 5.0)}
       output_vars: List[str] - List of output variable names
   Returns:
       List[Dict[str, float]] - List of input variable combinations to evaluate
                                e.g., [{"x": 0.5, "y": 0.0}, {"x": 0.7, "y": 2.3}]

3. get_next_design(self, previous_input_vars, previous_output_values):
   Returns next design of experiments based on previous results
   Args:
       previous_input_vars: List[Dict[str, float]] - Previous input combinations
                           e.g., [{"x": 0.5, "y": 0.0}, {"x": 0.7, "y": 2.3}]
       previous_output_values: List[float] - Corresponding output values (may contain None)
                              e.g., [1.5, None, 2.3, 0.8]
   Returns:
       List[Dict[str, float]] - Next input variable combinations to evaluate
       Returns empty list [] when algorithm is finished

   Note: While the interface uses Python lists, algorithms can convert to numpy arrays
         internally for numerical computation. Output values may contain None for failed
         evaluations, so filter these out before numerical operations.

4. get_analysis(self, input_vars, output_values):
   Returns results to display
   Args:
       input_vars: List[Dict[str, float]] - All evaluated input combinations
       output_values: List[float] - All corresponding output values (may contain None)
   Returns:
       Dict with display information (can include 'text', 'data', 'plot', etc.)

   Note: Should handle None values in output_values (failed evaluations)

5. get_analysis_tmp(self, input_vars, output_values): [OPTIONAL]
   Display intermediate results at each iteration
   Args:
       input_vars: List[Dict[str, float]] - All evaluated inputs so far
       output_values: List[float] - All outputs so far (may contain None)
   Returns:
       Dict with display information (typically 'text' and 'data' keys)

   Note: This method is optional. If present, it will be called after each iteration
         to show progress. If not present, no intermediate results are displayed.
"""

import re
import importlib
import importlib.util
import sys
import subprocess
import inspect
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging


def parse_input_vars(input_vars: Dict[str, str]) -> Dict[str, Tuple[float, float]]:
    """
    Parse input variable ranges from string descriptions

    Supports two formats:
    - Range (variable): "[min;max]" or "[min,max]" - will be varied by algorithm
    - Fixed (unique): single numeric value - will NOT be varied by algorithm

    Args:
        input_vars: Dict of {var_name: "[min;max]"} or {var_name: "value"}

    Returns:
        Dict of {var_name: (min, max)} for range variables only

    Examples:
        >>> parse_input_vars({"x": "[0;1]", "y": "[-5.5;5.5]"})
        {'x': (0.0, 1.0), 'y': (-5.5, 5.5)}

        >>> parse_input_vars({"x": "[0;1]", "z": "0.5"})  # z is fixed
        {'x': (0.0, 1.0)}
    """
    parsed = {}

    for var_name, range_str in input_vars.items():
        # Check if it's a range format [min;max] or [min,max]
        match = re.match(r'\[([^;,]+)[;,]([^;,]+)\]', range_str.strip())

        if match:
            # It's a range - parse it
            try:
                min_val = float(match.group(1).strip())
                max_val = float(match.group(2).strip())
            except ValueError as e:
                raise ValueError(
                    f"Invalid numeric values in range for variable '{var_name}': '{range_str}'"
                ) from e

            if min_val >= max_val:
                raise ValueError(
                    f"Invalid range for variable '{var_name}': min ({min_val}) must be < max ({max_val})"
                )

            parsed[var_name] = (min_val, max_val)
        else:
            # It's a fixed value - skip it (will be handled by parse_fixed_vars)
            # Try to validate it's a number
            try:
                float(range_str.strip())
            except ValueError:
                raise ValueError(
                    f"Invalid format for variable '{var_name}': '{range_str}'. "
                    f"Expected '[min;max]' for range or numeric value for fixed variable"
                )

    return parsed


def parse_fixed_vars(input_vars: Dict[str, str]) -> Dict[str, float]:
    """
    Parse fixed (unique) input variables from string descriptions

    Fixed variables have single numeric values and will NOT be varied by the algorithm.

    Args:
        input_vars: Dict of {var_name: "value"}

    Returns:
        Dict of {var_name: value} for fixed variables only

    Examples:
        >>> parse_fixed_vars({"x": "[0;1]", "z": "0.5"})
        {'z': 0.5}
    """
    fixed = {}

    for var_name, value_str in input_vars.items():
        # Check if it's NOT a range format
        if not re.match(r'\[([^;,]+)[;,]([^;,]+)\]', value_str.strip()):
            try:
                fixed[var_name] = float(value_str.strip())
            except ValueError as e:
                raise ValueError(
                    f"Invalid numeric value for fixed variable '{var_name}': '{value_str}'"
                ) from e

    return fixed


def evaluate_output_expression(
    expression: str,
    output_data: Dict[str, Any]
) -> float:
    """
    Evaluate mathematical expression using output variables

    Args:
        expression: Mathematical expression like "output1 + output2 * 2"
        output_data: Dict of output variable values

    Returns:
        Evaluated numeric result

    Examples:
        >>> evaluate_output_expression("x + y * 2", {"x": 1.0, "y": 3.0})
        7.0
    """
    try:
        # Create a safe evaluation environment with only the output variables
        # and math functions
        import math
        safe_dict = {
            # Math functions
            'abs': abs,
            'min': min,
            'max': max,
            'pow': pow,
            'sqrt': math.sqrt,
            'exp': math.exp,
            'log': math.log,
            'log10': math.log10,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'atan2': math.atan2,
            'pi': math.pi,
            'e': math.e,
        }

        # Add output variables
        safe_dict.update(output_data)

        # Evaluate the expression
        result = eval(expression, {"__builtins__": {}}, safe_dict)

        return float(result)

    except Exception as e:
        raise ValueError(
            f"Failed to evaluate output expression '{expression}' with data {output_data}: {e}"
        ) from e


def _is_algorithm_class(obj) -> bool:
    """
    Check if an object is a valid algorithm class

    Args:
        obj: Object to check

    Returns:
        True if obj is a class with required algorithm methods
    """
    if not inspect.isclass(obj):
        return False

    # Check for required methods
    required_methods = ['get_initial_design', 'get_next_design', 'get_analysis']
    for method_name in required_methods:
        if not hasattr(obj, method_name):
            return False

    return True


def _parse_algorithm_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Parse metadata from algorithm file comments

    Looks for comments like:
    #title: Algorithm title
    #author: Author name
    #type: algorithm type
    #options: key1=value1;key2=value2
    #require: package1;package2;package3

    Args:
        file_path: Path to algorithm file

    Returns:
        Dict with parsed metadata
    """
    metadata = {}

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()

                # Stop at first non-comment line
                if line and not line.startswith('#'):
                    break

                # Parse metadata lines
                if line.startswith('#'):
                    # Remove leading # and split on first :
                    content = line[1:].strip()
                    if ':' in content:
                        key, value = content.split(':', 1)
                        key = key.strip()
                        value = value.strip()

                        # Store metadata
                        if key == 'options':
                            # Parse options as key=value pairs separated by semicolons
                            options_dict = {}
                            for opt in value.split(';'):
                                if '=' in opt:
                                    opt_key, opt_val = opt.split('=', 1)
                                    options_dict[opt_key.strip()] = opt_val.strip()
                            metadata[key] = options_dict
                        elif key == 'require':
                            # Parse requirements as semicolon-separated list
                            metadata[key] = [pkg.strip() for pkg in value.split(';')]
                        else:
                            metadata[key] = value
    except Exception as e:
        logging.warning(f"Failed to parse metadata from {file_path}: {e}")

    return metadata


def _load_algorithm_from_file(file_path: Path, **options):
    """
    Load algorithm class from a Python file

    Args:
        file_path: Path to Python file containing algorithm class
        **options: Options to pass to algorithm constructor

    Returns:
        Algorithm instance

    Raises:
        ValueError: If no valid algorithm class is found in the file
    """
    # Parse metadata from file
    metadata = _parse_algorithm_metadata(file_path)

    # Check and install required packages if specified
    if 'require' in metadata:
        for package in metadata['require']:
            try:
                importlib.import_module(package)
                logging.info(f"✓ Package '{package}' is available")
            except ImportError:
                logging.info(f"⚠️  Package '{package}' not found - attempting to install...")
                try:
                    # Install the package using pip
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", package],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE
                    )
                    logging.info(f"✓ Successfully installed '{package}'")

                    # Verify the installation
                    try:
                        importlib.import_module(package)
                    except ImportError:
                        logging.warning(
                            f"Package '{package}' was installed but could not be imported. "
                            f"You may need to restart your Python session."
                        )
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode('utf-8') if e.stderr else ''
                    raise RuntimeError(
                        f"Failed to install required package '{package}'. "
                        f"Please install it manually with: pip install {package}\n"
                        f"Error: {error_msg}"
                    ) from e
                except Exception as e:
                    raise RuntimeError(
                        f"Unexpected error while installing package '{package}': {e}\n"
                        f"Please install it manually with: pip install {package}"
                    ) from e

    # Merge metadata options with passed options (passed options take precedence)
    if 'options' in metadata:
        merged_options = metadata['options'].copy()
        merged_options.update(options)
        options = merged_options

    # Load the Python module from file
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)

    if spec is None or spec.loader is None:
        raise ValueError(f"Failed to load module from {file_path}")

    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules to allow imports within the module
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        # Clean up sys.modules on failure
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise ValueError(f"Failed to execute module from {file_path}: {e}") from e

    # Find algorithm classes in the module
    algorithm_classes = []
    for name, obj in inspect.getmembers(module):
        if _is_algorithm_class(obj):
            algorithm_classes.append((name, obj))

    if not algorithm_classes:
        raise ValueError(
            f"No valid algorithm class found in {file_path}. "
            f"Algorithm class must have methods: get_initial_design, get_next_design, get_analysis"
        )

    # If multiple classes found, prefer one that's not BaseAlgorithm
    if len(algorithm_classes) > 1:
        algorithm_classes = [(n, c) for n, c in algorithm_classes if n != 'BaseAlgorithm']

    if not algorithm_classes:
        raise ValueError(f"No valid algorithm class found in {file_path} (only BaseAlgorithm found)")

    # Use the first (or only) algorithm class
    algorithm_name, algorithm_class = algorithm_classes[0]

    logging.info(f"Loaded algorithm class '{algorithm_name}' from {file_path}")
    if metadata:
        logging.info(f"Algorithm metadata: {metadata}")

    # Create and return instance
    return algorithm_class(**options)


def load_algorithm(algorithm_path: str, **options):
    """
    Load an algorithm from a Python file and create an instance with options

    Args:
        algorithm_path: Path to a Python file containing an algorithm class
                       Can be absolute or relative path (e.g., "my_algorithm.py", "algorithms/monte_carlo.py")
        **options: Algorithm-specific options passed to the algorithm's __init__ method

    Returns:
        Algorithm instance

    Raises:
        ValueError: If the file doesn't exist, contains no valid algorithm class, or cannot be loaded

    Example:
        >>> algo = load_algorithm("algorithms/monte_carlo.py", batch_size=10, max_iter=100)
        >>> algo = load_algorithm("/absolute/path/to/algorithm.py", seed=42)
    """
    # Convert to Path object
    algo_path = Path(algorithm_path)

    # Resolve to absolute path if relative
    if not algo_path.is_absolute():
        algo_path = Path.cwd() / algo_path

    # Validate path
    if not algo_path.exists():
        raise ValueError(
            f"Algorithm file not found: {algo_path}\n"
            f"Please provide a valid path to a Python file containing an algorithm class."
        )

    if not algo_path.is_file():
        raise ValueError(f"Algorithm path is not a file: {algo_path}")

    if not str(algo_path).endswith('.py'):
        raise ValueError(
            f"Algorithm file must be a Python file (.py): {algo_path}\n"
            f"Got: {algo_path.suffix}"
        )

    # Load algorithm from file
    return _load_algorithm_from_file(algo_path, **options)


class BaseAlgorithm:
    """
    Base class for algorithms (optional, for reference)

    Algorithms don't need to inherit from this, but it documents the interface
    """

    def __init__(self, **options):
        """Initialize algorithm with options"""
        self.options = options

    def get_initial_design(
        self,
        input_vars: Dict[str, Tuple[float, float]],
        output_vars: List[str]
    ) -> List[Dict[str, float]]:
        """
        Generate initial design of experiments

        Args:
            input_vars: Dict of {var_name: (min, max)}
            output_vars: List of output variable names

        Returns:
            List of input variable combinations to evaluate
        """
        raise NotImplementedError()

    def get_next_design(
        self,
        previous_input_vars: List[Dict[str, float]],
        previous_output_values: List[float]
    ) -> List[Dict[str, float]]:
        """
        Generate next design based on previous results

        Args:
            previous_input_vars: Previous input combinations
            previous_output_values: Corresponding output values

        Returns:
            Next input variable combinations to evaluate
            Returns empty list when finished
        """
        raise NotImplementedError()

    def get_analysis(
        self,
        input_vars: List[Dict[str, float]],
        output_values: List[float]
    ) -> Dict[str, Any]:
        """
        Format results for display

        Args:
            input_vars: All evaluated input combinations
            output_values: All corresponding output values

        Returns:
            Dict with display information
        """
        raise NotImplementedError()
