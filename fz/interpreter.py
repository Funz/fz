"""
Interpreter utilities for fz package: variable parsing, formula evaluation, and output parsing
"""
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Union, Any, Set


def _get_comment_char(model: Dict) -> str:
    """
    Get comment character from model with support for multiple aliases
    
    Supported keys (in order of precedence):
    - commentline
    - comment_line  
    - comment_char
    - commentchar
    - comment
    
    Args:
        model: Model definition dict
        
    Returns:
        Comment character (default "#")
    """
    return model.get(
        "commentline",
        model.get(
            "comment_line",
            model.get(
                "comment_char",
                model.get(
                    "commentchar",
                    model.get("comment", "#")
                )
            )
        )
    )


def _get_var_prefix(model: Dict) -> str:
    """
    Get variable prefix from model with support for multiple aliases
    
    Supported keys (in order of precedence):
    - var_prefix
    - varprefix
    - var_char
    - varchar
    
    Args:
        model: Model definition dict
        
    Returns:
        Variable prefix (default "$")
    """
    return model.get(
        "var_prefix",
        model.get(
            "varprefix",
            model.get(
                "var_char",
                model.get("varchar", "$")
            )
        )
    )


def _get_formula_prefix(model: Dict) -> str:
    """
    Get formula prefix from model with support for multiple aliases
    
    Supported keys (in order of precedence):
    - formula_prefix
    - formulaprefix
    - form_prefix
    - formprefix
    - formula_char
    - form_char
    
    Args:
        model: Model definition dict
        
    Returns:
        Formula prefix (default "@")
    """
    return model.get(
        "formula_prefix",
        model.get(
            "formulaprefix",
            model.get(
                "form_prefix",
                model.get(
                    "formprefix",
                    model.get(
                        "formula_char",
                        model.get("form_char", "@")
                    )
                )
            )
        )
    )


def parse_variables_from_content(content: str, varprefix: str = "$", delim: str = "()") -> Set[str]:
    """
    Parse variables from text content using specified prefix and delimiters
    Supports default value syntax: $(var~default) or $(var~default;comment;bounds)

    Args:
        content: Text content to parse
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Set of variable names found (without default values and metadata)
    """
    variables = set()

    # Pattern to match variables: varprefix + optional delim + varname + optional default + optional delim
    if len(delim) == 2:
        left_delim, right_delim = delim[0], delim[1]
        # Escape special regex characters
        esc_varprefix = re.escape(varprefix)
        esc_left = re.escape(left_delim)
        esc_right = re.escape(right_delim)
        # Match ${var~default} or ${var} or $var
        pattern = rf"{esc_varprefix}(?:{esc_left}([a-zA-Z_][a-zA-Z0-9_]*)(?:~[^{esc_right}]*)?{esc_right}|([a-zA-Z_][a-zA-Z0-9_]*))"
    else:
        esc_varprefix = re.escape(varprefix)
        pattern = rf"{esc_varprefix}([a-zA-Z_][a-zA-Z0-9_]*)"

    matches = re.findall(pattern, content)
    for match in matches:
        if isinstance(match, tuple):
            var_name = match[0] or match[1]  # Get non-empty group
        else:
            var_name = match
        if var_name:
            variables.add(var_name)

    return variables


def parse_variables_from_file(filepath: Path, varprefix: str = "$", delim: str = "()") -> Set[str]:
    """
    Parse variables from a single file

    Args:
        filepath: Path to file to parse
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Set of variable names found
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files
        return set()

    return parse_variables_from_content(content, varprefix, delim)


def parse_variables_from_path(input_path: Path, varprefix: str = "$", delim: str = "()") -> Set[str]:
    """
    Parse variables from file or directory

    Args:
        input_path: Path to input file or directory
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Set of variable names found
    """
    variables = set()

    if input_path.is_file():
        variables.update(parse_variables_from_file(input_path, varprefix, delim))
    elif input_path.is_dir():
        for filepath in input_path.rglob("*"):
            if filepath.is_file():
                variables.update(parse_variables_from_file(filepath, varprefix, delim))
    else:
        raise FileNotFoundError(f"Input path '{input_path}' not found")

    return variables


def replace_variables_in_content(content: str, input_variables: Dict[str, Any],
                                varprefix: str = "$", delim: str = "()") -> str:
    """
    Replace variables in content with their values
    Supports default value syntax: $(var~default) or $(var~default;comment;bounds)

    If a variable is not found in input_variables but has a default value,
    the default will be used and a warning will be printed.

    Args:
        content: Text content to process
        input_variables: Dict of variable values
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Content with variables replaced
    """
    if len(delim) == 2:
        left_delim, right_delim = delim[0], delim[1]
        esc_varprefix = re.escape(varprefix)
        esc_left = re.escape(left_delim)
        esc_right = re.escape(right_delim)

        # Pattern to match ${var~default} or ${var} or $var
        # First handle delimited variables (with or without defaults)
        delim_pattern = rf"{esc_varprefix}{esc_left}([a-zA-Z_][a-zA-Z0-9_]*)(?:~([^{esc_right}]*))?{esc_right}"

        def replace_delimited(match):
            var_name = match.group(1)
            default_value = match.group(2)  # None if no default provided

            if var_name in input_variables:
                return str(input_variables[var_name])
            elif default_value is not None:
                print(f"Warning: Variable '{var_name}' not found in input_variables, using default value: '{default_value}'")
                return default_value
            else:
                # Variable not found and no default, leave unchanged
                return match.group(0)

        content = re.sub(delim_pattern, replace_delimited, content)

        # Then handle simple prefix-only variables (no defaults possible here)
        for var, val in input_variables.items():
            esc_var = re.escape(var)
            simple_pattern = rf"{esc_varprefix}{esc_var}\b"
            content = re.sub(simple_pattern, str(val), content)
    else:
        # Simple prefix-only variables (no default value support)
        for var, val in input_variables.items():
            esc_varprefix = re.escape(varprefix)
            esc_var = re.escape(var)
            pattern = rf"{esc_varprefix}{esc_var}\b"
            content = re.sub(pattern, str(val), content)

    return content


def parse_formulas_from_content(content: str, formula_prefix: str = "@", delim: str = "{}") -> List[str]:
    """
    Parse formulas from text content using specified prefix and delimiters

    Args:
        content: Text content to parse
        formula_prefix: Formula prefix (e.g., "@")
        delim: Delimiter characters (e.g., "{}")

    Returns:
        List of formula expressions found (without prefix and delimiters)
    """
    formulas = []

    if len(delim) != 2:
        return formulas  # No formulas without delimiters

    left_delim, right_delim = delim[0], delim[1]
    esc_formulaprefix = re.escape(formula_prefix)
    esc_left = re.escape(left_delim)
    esc_right = re.escape(right_delim)

    # Use a more sophisticated pattern to handle nested parentheses
    if left_delim == '(' and right_delim == ')':
        formula_pattern = rf"{esc_formulaprefix}\(([^()]*(?:\([^()]*\)[^()]*)*)\)"
    else:
        formula_pattern = rf"{esc_formulaprefix}{esc_left}([^{esc_right}]+){esc_right}"

    matches = re.findall(formula_pattern, content)
    for match in matches:
        formulas.append(match)

    return formulas


def parse_static_objects_from_content(content: str, commentline: str = "#", formula_prefix: str = "@") -> List[str]:
    """
    Parse static object definitions (constants, functions) from text content.
    These are lines that start with commentline + formula_prefix + ":"

    Args:
        content: Text content to parse
        commentline: Comment character (e.g., "#")
        formula_prefix: Formula prefix (e.g., "@")

    Returns:
        List of code lines for static object definitions
    """
    static_lines = []
    lines = content.split('\n')

    prefix = commentline + formula_prefix

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            # Extract the code part after the prefix
            code_part = stripped[len(prefix):]
            # Skip if it's a unit test (starts with ?)
            if code_part.lstrip().startswith('?'):
                continue
            # ONLY process lines that start with : (colon for static objects)
            if not code_part.lstrip().startswith(':'):
                continue
            # Skip if it's just a colon with nothing after
            if not code_part.strip() or code_part.strip() == ':':
                continue
            # Remove leading : and one space if present
            if code_part.lstrip().startswith(':'):
                # Find where the colon is
                colon_idx = code_part.index(':')
                # Take everything after the colon
                code_part = code_part[colon_idx + 1:]
                # Remove one space if present (but preserve other indentation)
                if code_part.startswith(' '):
                    code_part = code_part[1:]
            static_lines.append(code_part)

    return static_lines


def parse_static_objects_with_expressions(content: str, commentline: str = "#", formula_prefix: str = "@") -> Dict[str, str]:
    """
    Parse static object definitions and return a dict mapping object names to their original expressions.
    These are lines that start with commentline + formula_prefix + ":"

    Args:
        content: Text content to parse
        commentline: Comment character (e.g., "#")
        formula_prefix: Formula prefix (e.g., "@")

    Returns:
        Dict mapping object names to their original expressions (e.g., {"PI": "3.14159", "func": "def func(x): ..."})
    """
    static_lines = parse_static_objects_from_content(content, commentline, formula_prefix)
    
    if not static_lines:
        return {}
    
    # Join all lines and dedent
    import textwrap
    full_code = "\n".join(static_lines)
    dedented_code = textwrap.dedent(full_code)
    
    # Parse to find defined names and their expressions
    expressions = {}
    
    # Split into individual lines for parsing
    lines = dedented_code.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line or line.startswith('#'):
            i += 1
            continue
            
        # Check for Python assignment: name = value
        if '=' in line and not line.startswith('def ') and '<-' not in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                # Remove any type hints
                if ':' in name:
                    name = name.split(':')[0].strip()
                value = parts[1].strip()
                expressions[name] = value
                i += 1
                continue
        
        # Check for R assignment: name <- value or name <- function(...)
        if '<-' in line:
            parts = line.split('<-', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                value_part = parts[1].strip()
                
                # Check if it's a function definition
                if value_part.startswith('function('):
                    # Collect multi-line function (store only the RHS: function(...) {...})
                    func_lines = [value_part]  # Start with the function(...) part
                    i += 1
                    # Continue collecting lines that are part of the function
                    while i < len(lines):
                        next_line = lines[i]
                        # If line is indented or empty, it's part of the function
                        if not next_line.strip():
                            func_lines.append(next_line)
                            i += 1
                        elif next_line.startswith('    ') or next_line.startswith('\t'):
                            func_lines.append(next_line)
                            i += 1
                            # Check if this line contains the closing }
                            if '}' in next_line:
                                break
                        else:
                            break
                    
                    # Store only the function expression (RHS), not the assignment
                    expressions[name] = '\n'.join(func_lines)
                else:
                    # Simple R assignment - store only the RHS
                    expressions[name] = value_part
                    i += 1
                continue
        
        # Check for Python function definition: def name(...):
        if line.startswith('def '):
            # Extract function name
            match = re.match(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line)
            if match:
                func_name = match.group(1)
                # Collect the full function definition (multi-line)
                func_lines = [lines[i]]
                i += 1
                # Continue collecting lines that are indented or part of the function
                while i < len(lines):
                    next_line = lines[i]
                    # If line is indented or empty, it's part of the function
                    if not next_line.strip() or next_line.startswith('    ') or next_line.startswith('\t'):
                        func_lines.append(next_line)
                        i += 1
                    else:
                        break
                
                # Store the function definition
                expressions[func_name] = '\n'.join(func_lines)
                continue
        
        # Check for other statements (import, etc.)
        if line.startswith('import ') or line.startswith('from '):
            # Store import statements with a generic key
            import_key = f"_import_{i}"
            expressions[import_key] = line
        
        i += 1
    
    return expressions


def evaluate_static_objects(static_lines: List[str], interpreter: str = "python") -> Dict[str, Any]:
    """
    Evaluate static object definitions and extract their values.

    Args:
        static_lines: List of code lines to evaluate
        interpreter: Interpreter to use ("python" or "R")

    Returns:
        Dict of {name: value} for all defined constants and functions
    """
    if not static_lines:
        return {}

    static_objects = {}

    if interpreter.lower() == "python":
        # Create execution environment
        env = {}

        # Use textwrap.dedent for proper dedenting
        import textwrap
        full_code = "\n".join(static_lines)
        dedented_code = textwrap.dedent(full_code)

        try:
            exec(dedented_code, env)
            # Extract defined names (skip builtins)
            for name, value in env.items():
                if not name.startswith('__'):
                    static_objects[name] = value
        except Exception as e:
            print(f"Warning: Error executing static objects: {e}")

    elif interpreter.lower() == "r":
        try:
            from rpy2 import robjects as ro
            from rpy2.robjects import conversion, default_converter
        except ImportError:
            print("Warning: rpy2 not installed, cannot evaluate R static objects")
            return {}

        # Use textwrap.dedent for proper dedenting
        import textwrap
        full_code = "\n".join(static_lines)
        dedented_code = textwrap.dedent(full_code)

        try:
            ro.r(dedented_code)
            # Extract defined names from R global environment
            for name in ro.r('ls()'):
                try:
                    value = ro.r[name]
                    # Convert R objects to Python
                    with conversion.localconverter(default_converter):
                        static_objects[name] = conversion.rpy2py(value)
                except Exception:
                    # For functions or complex objects, store None
                    static_objects[name] = None
        except Exception as e:
            print(f"Warning: Error executing R static objects: {e}")

    return static_objects


def evaluate_single_formula(formula: str, model: Dict, input_variables: Dict, interpreter: str = "python") -> Any:
    """
    Evaluate a single formula expression and return its value

    Args:
        formula: Formula expression to evaluate (without prefix and delimiters)
        model: Model definition dict
        input_variables: Dict of variable values
        interpreter: Interpreter for evaluation ("python", "R", etc.)

    Returns:
        Evaluated value or None if evaluation fails
    """
    commentline = _get_comment_char(model)
    varprefix = _get_var_prefix(model)
    var_delim = model.get("var_delim", model.get("delim", "()"))

    # Extract context lines from model if available
    context_lines = []

    # Setup interpreter environment
    if interpreter.lower() == "python":
        env = dict(input_variables)

        # Import common math functions
        import math
        env.update({
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'log': math.log, 'log10': math.log10, 'exp': math.exp,
            'sqrt': math.sqrt, 'abs': abs, 'floor': math.floor,
            'ceil': math.ceil, 'pow': pow
        })

        # Handle format suffix if present
        format_spec = None
        if '|' in formula:
            formula, format_spec = formula.split('|', 1)
            formula = formula.strip()
            format_spec = format_spec.strip()

        # Replace variables in formula using the model's variable prefix
        # Handle both delimited and non-delimited variables
        for var, val in input_variables.items():
            if len(var_delim) == 2:
                # Try with delimiters first: $(...) or V(...)
                left_delim = var_delim[0]
                right_delim = var_delim[1]
                var_pattern_delim = rf'{re.escape(varprefix)}{re.escape(left_delim)}{re.escape(var)}{re.escape(right_delim)}'
                formula = re.sub(var_pattern_delim, str(val), formula)
            
            # Also try without delimiters: $var or Vvar
            var_pattern = rf'{re.escape(varprefix)}{re.escape(var)}\b'
            formula = re.sub(var_pattern, str(val), formula)

        try:
            result = eval(formula, env)

            # Apply format if specified
            if format_spec and '.' in format_spec:
                decimals = len(format_spec.split('.')[1])
                try:
                    return float(f"{float(result):.{decimals}f}")
                except (ValueError, TypeError):
                    return result

            return result
        except Exception as e:
            # Return None if evaluation fails
            return None

    elif interpreter.lower() == "r":
        try:
            from rpy2 import robjects
            from rpy2.robjects import r
        except ImportError:
            return None

        # Set R variables
        for var, val in input_variables.items():
            try:
                if isinstance(val, (int, float)):
                    robjects.globalenv[var] = val
                elif isinstance(val, str):
                    robjects.globalenv[var] = val
                elif isinstance(val, (list, tuple)):
                    robjects.globalenv[var] = robjects.FloatVector(val)
                elif hasattr(val, '__module__') and 'rpy2' in str(val.__module__):
                    # R object (function, vector, etc.) - assign directly
                    robjects.globalenv[var] = val
                else:
                    robjects.globalenv[var] = str(val)
            except Exception:
                pass

        # Handle format suffix
        format_spec = None
        if '|' in formula:
            formula, format_spec = formula.split('|', 1)
            formula = formula.strip()
            format_spec = format_spec.strip()

        # Replace variables in formula (remove variable prefix for R)
        # Handle both delimited and non-delimited variables
        r_formula = formula
        for var in input_variables.keys():
            if len(var_delim) == 2:
                # Try with delimiters first
                left_delim = var_delim[0]
                right_delim = var_delim[1]
                var_pattern_delim = rf'{re.escape(varprefix)}{re.escape(left_delim)}{re.escape(var)}{re.escape(right_delim)}'
                r_formula = re.sub(var_pattern_delim, var, r_formula)
            
            # Also try without delimiters
            var_pattern = rf'{re.escape(varprefix)}{re.escape(var)}\b'
            r_formula = re.sub(var_pattern, var, r_formula)

        try:
            result = r(r_formula)
            if hasattr(result, '__len__') and len(result) == 1:
                value = result[0]
            else:
                value = result if not (hasattr(result, '__len__') and len(result) == 0) else result

            # Apply format if specified
            if format_spec and '.' in format_spec:
                decimals = len(format_spec.split('.')[1])
                try:
                    return float(f"{float(value):.{decimals}f}")
                except (ValueError, TypeError):
                    return value

            return value
        except Exception:
            return None

    return None


def evaluate_formulas(content: str, model: Dict, input_variables: Dict, interpreter: str = "python") -> str:
    """
    Evaluate formulas in content using specified interpreter
    Supports format specifier: @{expr | format}

    Args:
        content: Text content containing formulas
        model: Model definition dict
        input_variables: Dict of variable values
        interpreter: Interpreter for evaluation ("python", "R", etc.)

    Returns:
        Content with formulas evaluated
    """
    # Formula prefix: support multiple aliases
    formulaprefix = _get_formula_prefix(model)
    # Formula delimiters: use formula_delim if set, else delim if set, else default to {}
    delim = model.get("formula_delim", model.get("delim", "{}"))
    commentline = _get_comment_char(model)

    # Only validate delim if it will be used (when we have delimiters)
    if len(delim) != 2 and len(delim) != 0:
        raise ValueError("delim must be exactly 2 characters or empty")

    if len(delim) == 2:
        left_delim, right_delim = delim[0], delim[1]
    else:
        left_delim, right_delim = "", ""

    # Collect formula context lines (comment + formula prefix) and preserve indentation
    context_lines = []
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(commentline + formulaprefix):
            # Extract the code part and preserve any indentation from original
            code_part = stripped[len(commentline + formulaprefix):]
            # Remove Funz-specific prefixes (: for code, ? for tests)
            if code_part.startswith(':') or code_part.startswith('?'):
                code_part = code_part[1:]
            context_lines.append(code_part)

    # If delimiters are empty, skip formula evaluation (no formulas possible)
    if len(delim) == 0:
        return content

    # Setup interpreter environment
    if interpreter.lower() == "python":
        # Create execution environment
        env = dict(input_variables)  # Start with variable values

        # Execute context lines (collect them first to handle multi-line functions)
        if context_lines:
            # Find minimum indentation for proper dedenting
            non_empty_lines = [line for line in context_lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines if line.strip())
                dedented_lines = []
                for line in context_lines:
                    if line.strip():  # Non-empty line
                        dedented_lines.append(line[min_indent:] if len(line) > min_indent else line.lstrip())
                    else:  # Empty line
                        dedented_lines.append("")

                full_context = "\n".join(dedented_lines)
                try:
                    exec(full_context, env)
                except Exception as e:
                    print(f"Warning: Error executing full context: {e}")
                    # Try line by line if full context fails
                    for context_line in dedented_lines:
                        if context_line.strip():
                            try:
                                exec(context_line, env)
                            except Exception as e:
                                print(f"Warning: Error executing context line '{context_line}': {e}")

        # Find and evaluate formulas
        esc_formulaprefix = re.escape(formulaprefix)
        esc_left = re.escape(left_delim)
        esc_right = re.escape(right_delim)

        # Use a more sophisticated pattern to handle nested parentheses
        if left_delim == '(' and right_delim == ')':
            formula_pattern = rf"{esc_formulaprefix}\(([^()]*(?:\([^()]*\)[^()]*)*)\)"
        else:
            formula_pattern = rf"{esc_formulaprefix}{esc_left}([^{esc_right}]+){esc_right}"

        def replace_formula(match):
            formula = match.group(1)
            try:
                # Handle format suffix (e.g., "expr | 0.0000" for number formatting)
                format_spec = None
                if '|' in formula:
                    formula, format_spec = formula.split('|', 1)
                    formula = formula.strip()
                    format_spec = format_spec.strip()

                # Replace variables in formula with their values
                for var, val in input_variables.items():
                    var_pattern = rf'\${re.escape(var)}\b'
                    formula = re.sub(var_pattern, str(val), formula)

                result = eval(formula, env)

                # Apply format if specified
                if format_spec:
                    # Parse format like "0.0000" → 4 decimals
                    if '.' in format_spec:
                        decimals = len(format_spec.split('.')[1])
                        try:
                            return f"{float(result):.{decimals}f}"
                        except (ValueError, TypeError):
                            return str(result)
                    else:
                        return str(result)
                else:
                    return str(result)
            except Exception as e:
                print(f"Warning: Error evaluating formula '{formula}': {e}")
                return match.group(0)  # Return original if evaluation fails

        content = re.sub(formula_pattern, replace_formula, content)

    elif interpreter.lower() == "r":
        # R interpreter using rpy2
        try:
            from rpy2 import robjects
            from rpy2.robjects import r
        except ImportError:
            print("Warning: rpy2 package not installed. Install with: pip install rpy2")
            print("Skipping formula evaluation")
            return content

        # Create R environment with variable values
        for var, val in input_variables.items():
            try:
                # Convert Python values to R
                if isinstance(val, (int, float)):
                    robjects.globalenv[var] = val
                elif isinstance(val, str):
                    robjects.globalenv[var] = val
                elif isinstance(val, (list, tuple)):
                    robjects.globalenv[var] = robjects.FloatVector(val)
                else:
                    robjects.globalenv[var] = str(val)
            except Exception as e:
                print(f"Warning: Error setting R variable '{var}': {e}")

        # Execute context lines (function definitions, imports, etc.)
        if context_lines:
            # Find minimum indentation for proper dedenting
            non_empty_lines = [line for line in context_lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines if line.strip())
                dedented_lines = []
                for line in context_lines:
                    if line.strip():  # Non-empty line
                        dedented_lines.append(line[min_indent:] if len(line) > min_indent else line.lstrip())
                    else:  # Empty line
                        dedented_lines.append("")

                full_context = "\n".join(dedented_lines)
                try:
                    r(full_context)
                except Exception as e:
                    print(f"Warning: Error executing R context: {e}")
                    # Try line by line if full context fails
                    for context_line in dedented_lines:
                        if context_line.strip():
                            try:
                                r(context_line)
                            except Exception as e:
                                print(f"Warning: Error executing R context line '{context_line}': {e}")

        # Find and evaluate formulas
        esc_formulaprefix = re.escape(formulaprefix)
        esc_left = re.escape(left_delim)
        esc_right = re.escape(right_delim)

        # Use a more sophisticated pattern to handle nested parentheses
        if left_delim == '(' and right_delim == ')':
            formula_pattern = rf"{esc_formulaprefix}\(([^()]*(?:\([^()]*\)[^()]*)*)\)"
        else:
            formula_pattern = rf"{esc_formulaprefix}{esc_left}([^{esc_right}]+){esc_right}"

        def replace_formula(match):
            formula = match.group(1)
            try:
                # Handle format suffix (e.g., "expr|0.0000" for number formatting)
                format_spec = None
                if '|' in formula:
                    formula, format_spec = formula.split('|', 1)
                    formula = formula.strip()
                    format_spec = format_spec.strip()
                
                # Replace variables in formula with their values (R uses variable names directly)
                # So we just remove the $ prefix for R
                r_formula = formula
                for var in input_variables.keys():
                    var_pattern = rf'\${re.escape(var)}\b'
                    r_formula = re.sub(var_pattern, var, r_formula)

                # Evaluate using R
                result = r(r_formula)
                # Convert R result to Python
                if hasattr(result, '__len__') and len(result) == 1:
                    value = result[0]
                else:
                    value = result if not (hasattr(result, '__len__') and len(result) == 0) else result
                
                # Apply format if specified
                if format_spec:
                    # Parse format like "0.0000" → 4 decimals
                    if '.' in format_spec:
                        decimals = len(format_spec.split('.')[1])
                        try:
                            return f"{float(value):.{decimals}f}"
                        except (ValueError, TypeError):
                            return str(value)
                    else:
                        return str(value)
                else:
                    return str(value)
            except Exception as e:
                print(f"Warning: Error evaluating R formula '{formula}': {e}")
                return match.group(0)  # Return original if evaluation fails

        content = re.sub(formula_pattern, replace_formula, content)

    else:
        # For other interpreters, we'd need to implement support
        print(f"Warning: Interpreter '{interpreter}' not yet implemented, skipping formula evaluation")

    return content


def cast_output(value: str) -> Any:
    """
    Try to cast string output to appropriate Python type

    Args:
        value: String value to cast

    Returns:
        Value cast to appropriate type (int, float, dict, list, etc.)
        If result is a list/array of length 1, returns the single element instead
    """
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    # Try JSON first (handles dicts, lists, etc.)
    try:
        result = json.loads(value)
        # Simplify single-element arrays to scalar
        if isinstance(result, list) and len(result) == 1:
            return result[0]
        return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try Python literal evaluation
    try:
        result = ast.literal_eval(value)
        # Simplify single-element arrays to scalar
        if isinstance(result, (list, tuple)) and len(result) == 1:
            return result[0]
        return result
    except (ValueError, SyntaxError):
        pass

    # Try numeric types
    try:
        if '.' in value or 'e' in value.lower():
            return float(value)
        else:
            return int(value)
    except ValueError:
        pass

    # Return as string
    return value