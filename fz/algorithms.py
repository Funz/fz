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
   Returns results to analysis
   Args:
       input_vars: List[Dict[str, float]] - All evaluated input combinations
       output_values: List[float] - All corresponding output values (may contain None)
   Returns:
       Dict with analysis information (can include 'text', 'data', 'plot', etc.)

   Note: Should handle None values in output_values (failed evaluations)

5. get_analysis_tmp(self, input_vars, output_values): [OPTIONAL]
   Display intermediate results at each iteration
   Args:
       input_vars: List[Dict[str, float]] - All evaluated inputs so far
       output_values: List[float] - All outputs so far (may contain None)
   Returns:
       Dict with analysis information (typically 'text' and 'data' keys)

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


class RAlgorithmWrapper:
    """
    Python wrapper for R algorithms loaded via rpy2

    This class wraps an R algorithm instance and exposes its methods as Python methods,
    handling data conversion between Python and R.
    """

    def __init__(self, r_instance, r_globals):
        """
        Initialize wrapper with R instance

        Args:
            r_instance: R algorithm instance from rpy2
            r_globals: R global environment containing generic functions
        """
        self.r_instance = r_instance
        self.r_globals = r_globals

    def get_initial_design(self, input_vars: Dict[str, Tuple[float, float]], output_vars: List[str]) -> List[Dict[str, float]]:
        """
        Call R's get_initial_design method and convert result to Python

        Args:
            input_vars: Dict of {var_name: (min, max)}
            output_vars: List of output variable names

        Returns:
            List of input variable combinations (Python dicts)
        """
        try:
            from rpy2 import robjects
            from rpy2.robjects import vectors
        except ImportError:
            raise ImportError("rpy2 is required to use R algorithms. Install with: pip install rpy2")

        # Convert input_vars to R format: named list with c(min, max) vectors
        r_input_vars = robjects.ListVector({
            var: vectors.FloatVector([bounds[0], bounds[1]])
            for var, bounds in input_vars.items()
        })

        # Convert output_vars to R character vector
        r_output_vars = vectors.StrVector(output_vars)

        # Call R method
        r_result = self.r_globals['get_initial_design'](self.r_instance, r_input_vars, r_output_vars)

        # Convert R list of lists to Python list of dicts
        return self._r_design_to_python(r_result)

    def get_next_design(self, X: List[Dict[str, float]], Y: List[float]) -> List[Dict[str, float]]:
        """
        Call R's get_next_design method and convert result to Python

        Args:
            X: Previous input combinations (list of dicts)
            Y: Previous output values (list of floats, may contain None)

        Returns:
            Next input variable combinations (Python dicts), or empty list if finished
        """
        try:
            from rpy2 import robjects
        except ImportError:
            raise ImportError("rpy2 is required to use R algorithms. Install with: pip install rpy2")

        # Convert X and Y to R format
        r_X = self._python_design_to_r(X)
        r_Y = self._python_outputs_to_r(Y)

        # Call R method
        r_result = self.r_globals['get_next_design'](self.r_instance, r_X, r_Y)

        # Convert result to Python
        return self._r_design_to_python(r_result)

    def get_analysis(self, X: List[Dict[str, float]], Y: List[float]) -> Dict[str, Any]:
        """
        Call R's get_analysis method and convert result to Python

        Args:
            X: All evaluated input combinations
            Y: All output values (may contain None)

        Returns:
            Dict with analysis information ('text', 'data', etc.)
        """
        try:
            from rpy2 import robjects
        except ImportError:
            raise ImportError("rpy2 is required to use R algorithms. Install with: pip install rpy2")

        # Convert X and Y to R format
        r_X = self._python_design_to_r(X)
        r_Y = self._python_outputs_to_r(Y)

        # Call R method
        r_result = self.r_globals['get_analysis'](self.r_instance, r_X, r_Y)

        # Convert R list to Python dict
        return self._r_dict_to_python(r_result)

    def get_analysis_tmp(self, X: List[Dict[str, float]], Y: List[float]) -> Dict[str, Any]:
        """
        Call R's get_analysis_tmp method if it exists

        Args:
            X: Evaluated input combinations so far
            Y: Output values so far (may contain None)

        Returns:
            Dict with intermediate analysis information, or None if method doesn't exist
        """
        try:
            from rpy2 import robjects
        except ImportError:
            raise ImportError("rpy2 is required to use R algorithms. Install with: pip install rpy2")

        # Check if method exists in R
        try:
            # Convert X and Y to R format
            r_X = self._python_design_to_r(X)
            r_Y = self._python_outputs_to_r(Y)

            # Call R method
            r_result = self.r_globals['get_analysis_tmp'](self.r_instance, r_X, r_Y)

            # Convert R list to Python dict
            return self._r_dict_to_python(r_result)
        except Exception:
            # Method doesn't exist or failed - return None
            return None

    def _python_design_to_r(self, design: List[Dict[str, float]]):
        """Convert Python design (list of dicts) to R list of lists"""
        from rpy2 import robjects
        from rpy2.robjects import vectors

        if not design:
            # Empty list
            return robjects.r('list()')

        # Convert to R list of lists
        r_list = robjects.r('list()')
        for point in design:
            r_point = robjects.ListVector(point)
            r_list = robjects.r.c(r_list, robjects.r.list(r_point))

        return r_list

    def _python_outputs_to_r(self, outputs: List[float]):
        """Convert Python outputs (list of floats/None) to R list"""
        from rpy2 import robjects

        # Convert Python list to R list, preserving None as NULL
        # Use R's list() function directly
        r_list = robjects.r('list()')

        for val in outputs:
            if val is None:
                # Append R NULL
                r_list = robjects.r.c(r_list, robjects.r('list(NULL)'))
            else:
                # Append numeric value
                r_list = robjects.r.c(r_list, robjects.r.list(val))

        return r_list

    def _r_design_to_python(self, r_design) -> List[Dict[str, float]]:
        """Convert R design (list of lists) to Python list of dicts"""
        if r_design is None or len(r_design) == 0:
            return []

        result = []
        for r_point in r_design:
            # Convert R list to Python dict
            point = {}
            for name in r_point.names:
                point[name] = float(r_point.rx2(name)[0])
            result.append(point)

        return result

    def _r_dict_to_python(self, r_list) -> Dict[str, Any]:
        """Convert R list to Python dict, handling nested structures"""
        from rpy2 import robjects
        from rpy2.robjects import vectors

        result = {}

        if r_list is None:
            return result

        for name in r_list.names:
            r_value = r_list.rx2(name)

            # Convert based on R type
            if isinstance(r_value, vectors.StrVector):
                # String or character vector
                if len(r_value) == 1:
                    result[name] = str(r_value[0])
                else:
                    result[name] = [str(v) for v in r_value]
            elif isinstance(r_value, (vectors.FloatVector, vectors.IntVector)):
                # Numeric vector
                if len(r_value) == 1:
                    result[name] = float(r_value[0])
                else:
                    result[name] = [float(v) for v in r_value]
            elif isinstance(r_value, vectors.ListVector):
                # Nested list - recursively convert
                result[name] = self._r_dict_to_python(r_value)
            else:
                # Try to convert to Python directly
                try:
                    result[name] = r_value
                except Exception:
                    # If conversion fails, store as string
                    result[name] = str(r_value)

        return result


def _load_r_algorithm_from_file(file_path: Path, **options):
    """
    Load algorithm from an R file using rpy2

    Args:
        file_path: Path to R file containing algorithm S3 class
        **options: Options to pass to algorithm constructor

    Returns:
        RAlgorithmWrapper instance wrapping the R algorithm

    Raises:
        ImportError: If rpy2 is not installed
        ValueError: If R algorithm cannot be loaded
    """
    try:
        from rpy2 import robjects
        from rpy2.robjects import vectors
    except ImportError:
        raise ImportError(
            "rpy2 is required to use R algorithms.\n"
            "Install with: pip install rpy2\n"
            "Note: R must also be installed on your system."
        )

    # Parse metadata from R file
    metadata = _parse_algorithm_metadata(file_path)

    # Check and install required R packages if specified
    if 'require' in metadata:
        for package in metadata['require']:
            # Check if R package is available
            r_check = robjects.r(f'''
                if (!requireNamespace("{package}", quietly = TRUE)) {{
                    FALSE
                }} else {{
                    TRUE
                }}
            ''')

            if not r_check[0]:
                logging.warning(
                    f"⚠️  R package '{package}' not found.\n"
                    f"    Install in R with: install.packages('{package}')"
                )

    # Merge metadata options with passed options
    if 'options' in metadata:
        merged_options = metadata['options'].copy()
        merged_options.update(options)
        options = merged_options

    # Source the R file
    logging.info(f"Loading R algorithm from {file_path}")
    try:
        robjects.r.source(str(file_path))
    except Exception as e:
        raise ValueError(f"Failed to source R file {file_path}: {e}") from e

    # Get R global environment
    r_globals = robjects.globalenv

    # Find the algorithm constructor function
    # Search for functions in R global environment that could be constructors
    # Priority: try matching the file stem first, then search all functions

    # Try different naming conventions for the file stem
    possible_names = [
        file_path.stem,  # montecarlo_uniform
        file_path.stem.replace('_', '').title(),  # Montecarlouniform
        ''.join(word.capitalize() for word in file_path.stem.split('_')),  # MontecarloUniform
        '_'.join(word.capitalize() for word in file_path.stem.split('_')),  # Montecarlo_Uniform
        file_path.stem.title(),  # Montecarlo_Uniform
    ]

    constructor = None
    constructor_name = None

    # First, try the expected naming conventions
    for name in possible_names:
        if name in r_globals:
            constructor = r_globals[name]
            constructor_name = name
            logging.info(f"Found constructor by name matching: {name}")
            break

    # If not found, search all objects for likely constructors
    # Look for functions that match pattern: PascalCase or Mixed_Case
    if constructor is None:
        logging.info(f"Constructor not found in expected names: {possible_names}")
        logging.info("Searching all R objects for potential constructors...")

        for name in sorted(list(r_globals.keys()), reverse=True):  # Reverse sort to prefer longer/specific names
            # Skip generic functions (they have dots for S3 dispatch)
            if '.' in name:
                continue

            # Skip all-lowercase names (likely helper functions, not constructors)
            if name.islower():
                continue

            # Skip names starting with lowercase (not constructors)
            if name[0].islower():
                continue

            # Check if it's a function
            try:
                obj = r_globals[name]
                # Check if it's callable (function)
                if robjects.r['is.function'](obj)[0]:
                    constructor = obj
                    constructor_name = name
                    logging.info(f"Found potential constructor: {name}")
                    break
            except Exception:
                continue

    if constructor is None:
        available_objects = [name for name in r_globals.keys() if not name.startswith('.')]
        raise ValueError(
            f"No algorithm constructor found in {file_path}.\n"
            f"Tried names: {possible_names}\n"
            f"Available objects in R file: {available_objects}\n"
            f"The R file should define a constructor function matching the filename."
        )

    logging.info(f"Found R algorithm constructor: {constructor_name}")

    # Call constructor with options
    # R constructors use ... syntax, so we need to pass as named arguments
    # rpy2 requires explicit conversion for some types
    if options:
        # Convert Python options to R-compatible types and pass as kwargs
        r_kwargs = {}
        for k, v in options.items():
            if isinstance(v, bool):
                r_kwargs[k] = robjects.vectors.BoolVector([v])
            elif isinstance(v, int):
                r_kwargs[k] = robjects.vectors.IntVector([v])
            elif isinstance(v, float):
                r_kwargs[k] = robjects.vectors.FloatVector([v])
            elif isinstance(v, str):
                r_kwargs[k] = robjects.vectors.StrVector([v])
            else:
                r_kwargs[k] = v

        # Call with **kwargs - rpy2 will handle the ... properly
        r_instance = constructor(**r_kwargs)
    else:
        r_instance = constructor()

    logging.info(f"Created R algorithm instance of class: {robjects.r['class'](r_instance)[0]}")

    # Create and return wrapper
    return RAlgorithmWrapper(r_instance, r_globals)


def load_algorithm(algorithm_path: str, **options):
    """
    Load an algorithm from a Python or R file and create an instance with options

    Args:
        algorithm_path: Path to a Python (.py) or R (.R) file containing an algorithm class
                       Can be absolute or relative path (e.g., "my_algorithm.py", "algorithms/monte_carlo.R")
        **options: Algorithm-specific options passed to the algorithm's __init__ method

    Returns:
        Algorithm instance (Python object or R wrapper)

    Raises:
        ValueError: If the file doesn't exist, contains no valid algorithm class, or cannot be loaded
        ImportError: If rpy2 is not installed for .R files

    Example:
        >>> algo = load_algorithm("algorithms/monte_carlo.py", batch_size=10, max_iter=100)
        >>> algo = load_algorithm("algorithms/monte_carlo.R", batch_size=10, max_iter=100)  # requires rpy2
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
            f"Please provide a valid path to a Python (.py) or R (.R) file containing an algorithm class."
        )

    if not algo_path.is_file():
        raise ValueError(f"Algorithm path is not a file: {algo_path}")

    # Check file extension and load appropriately
    if str(algo_path).endswith('.py'):
        # Load Python algorithm
        return _load_algorithm_from_file(algo_path, **options)
    elif str(algo_path).endswith('.R'):
        # Load R algorithm
        return _load_r_algorithm_from_file(algo_path, **options)
    else:
        raise ValueError(
            f"Algorithm file must be a Python (.py) or R (.R) file: {algo_path}\n"
            f"Got: {algo_path.suffix}"
        )


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
        Format results for analysis

        Args:
            input_vars: All evaluated input combinations
            output_values: All corresponding output values

        Returns:
            Dict with analysis information
        """
        raise NotImplementedError()
