"""
Engine utilities for fz package: variable parsing, formula evaluation, and output parsing
"""
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Union, Any, Set


def parse_variables_from_content(content: str, varprefix: str = "$", delim: str = "()") -> Set[str]:
    """
    Parse variables from text content using specified prefix and delimiters

    Args:
        content: Text content to parse
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Set of variable names found
    """
    variables = set()

    # Pattern to match variables: varprefix + optional delim + varname + optional delim
    if len(delim) == 2:
        left_delim, right_delim = delim[0], delim[1]
        # Escape special regex characters
        esc_varprefix = re.escape(varprefix)
        esc_left = re.escape(left_delim)
        esc_right = re.escape(right_delim)
        pattern = rf"{esc_varprefix}(?:{esc_left}([a-zA-Z_][a-zA-Z0-9_]*){esc_right}|([a-zA-Z_][a-zA-Z0-9_]*))"
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


def replace_variables_in_content(content: str, varvalues: Dict[str, Any],
                                varprefix: str = "$", delim: str = "()") -> str:
    """
    Replace variables in content with their values

    Args:
        content: Text content to process
        varvalues: Dict of variable values
        varprefix: Variable prefix (e.g., "$")
        delim: Delimiter characters (e.g., "()")

    Returns:
        Content with variables replaced
    """
    # Replace variables
    if len(delim) == 2:
        left_delim, right_delim = delim[0], delim[1]
        for var, val in varvalues.items():
            # Pattern for delimited variables: $var or $(var)
            esc_varprefix = re.escape(varprefix)
            esc_var = re.escape(var)
            esc_left = re.escape(left_delim)
            esc_right = re.escape(right_delim)

            patterns = [
                rf"{esc_varprefix}{esc_left}{esc_var}{esc_right}",
                rf"{esc_varprefix}{esc_var}\b"
            ]

            for pattern in patterns:
                content = re.sub(pattern, str(val), content)
    else:
        # Simple prefix-only variables
        for var, val in varvalues.items():
            esc_varprefix = re.escape(varprefix)
            esc_var = re.escape(var)
            pattern = rf"{esc_varprefix}{esc_var}\b"
            content = re.sub(pattern, str(val), content)

    return content


def evaluate_formulas(content: str, model: Dict, varvalues: Dict, engine: str = "python") -> str:
    """
    Evaluate formulas in content using specified engine

    Args:
        content: Text content containing formulas
        model: Model definition dict
        varvalues: Dict of variable values
        engine: Engine for evaluation ("python", "R", etc.)

    Returns:
        Content with formulas evaluated
    """
    formulaprefix = model.get("formulaprefix", "@")
    delim = model.get("delim", "()")
    commentline = model.get("commentline", "#")

    if len(delim) != 2:
        raise ValueError("delim must be exactly 2 characters")

    left_delim, right_delim = delim[0], delim[1]

    # Collect formula context lines (comment + formula prefix) and preserve indentation
    context_lines = []
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(commentline + formulaprefix):
            # Extract the code part and preserve any indentation from original
            code_part = stripped[len(commentline + formulaprefix):]
            context_lines.append(code_part)

    # Setup engine environment
    if engine.lower() == "python":
        # Create execution environment
        env = dict(varvalues)  # Start with variable values

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
                for var, val in varvalues.items():
                    var_pattern = rf'\${re.escape(var)}\b'
                    formula = re.sub(var_pattern, str(val), formula)

                result = eval(formula, env)
                return str(result)
            except Exception as e:
                print(f"Warning: Error evaluating formula '{formula}': {e}")
                return match.group(0)  # Return original if evaluation fails

        content = re.sub(formula_pattern, replace_formula, content)

    else:
        # For other engines, we'd need to implement support
        print(f"Warning: Engine '{engine}' not yet implemented, skipping formula evaluation")

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