"""
Interpreter utilities for fz package: variable parsing, formula evaluation, and output parsing
"""
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Union, Any, Set


def parse_variables_from_content(content: str, varprefix: str = "$", delim: str = "{}") -> Set[str]:
    """
    Parse variables from text content using specified prefix and delimiters
    Supports default value syntax: ${var~default}

    Args:
        content: Text content to parse
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "{}")

    Returns:
        Set of variable names found (without default values)
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


def parse_variables_from_file(filepath: Path, varprefix: str = "$", delim: str = "{}") -> Set[str]:
    """
    Parse variables from a single file

    Args:
        filepath: Path to file to parse
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "{}")

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


def parse_variables_from_path(input_path: Path, varprefix: str = "$", delim: str = "{}") -> Set[str]:
    """
    Parse variables from file or directory

    Args:
        input_path: Path to input file or directory
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "{}")

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
                                varprefix: str = "$", delim: str = "{}") -> str:
    """
    Replace variables in content with their values
    Supports default value syntax: ${var~default}

    If a variable is not found in input_variables but has a default value,
    the default will be used and a warning will be printed.

    Args:
        content: Text content to process
        input_variables: Dict of variable values
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "{}")

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


def evaluate_formulas(content: str, model: Dict, input_variables: Dict, interpreter: str = "python") -> str:
    """
    Evaluate formulas in content using specified interpreter

    Args:
        content: Text content containing formulas
        model: Model definition dict
        input_variables: Dict of variable values
        interpreter: Interpreter for evaluation ("python", "R", etc.)

    Returns:
        Content with formulas evaluated
    """
    formulaprefix = model.get("formulaprefix", "@")
    delim = model.get("delim", "{}")
    commentline = model.get("commentline", "#")

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
                # Replace variables in formula with their values
                for var, val in input_variables.items():
                    var_pattern = rf'\${re.escape(var)}\b'
                    formula = re.sub(var_pattern, str(val), formula)

                result = eval(formula, env)
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
                    value = result[0] if len(result) > 0 else result
                
                # Apply format if specified
                if format_spec:
                    # Parse format like "0.0000" → 4 decimals
                    if '.' in format_spec:
                        decimals = len(format_spec.split('.')[1])
                        return f"{float(value):.{decimals}f}"
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