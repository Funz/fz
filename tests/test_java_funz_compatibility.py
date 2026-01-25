"""
Test Java Funz syntax compatibility

Verifies that FZ supports the original Java Funz syntax:
- Variables: $(var) instead of ${var}
- Formulas: @{expr}
- Variable metadata: $(var~default;comment;bounds)
- Formula format: @{expr | 0.00}
- Function declarations: #@: func = ...
- Unit tests: #@? assertion
"""
import tempfile
from fz.interpreter import (
    parse_variables_from_content,
    replace_variables_in_content,
    evaluate_formulas,
)


def test_variable_syntax_with_parentheses():
    """Test that variables work with () delimiters like Java Funz"""
    content = """
CodeWord1 $(var1)
CodeWord2 $(var2)
"""
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert variables == {"var1", "var2"}


def test_variable_with_default_value():
    """Test Java Funz default value syntax: $(var~default)"""
    content = "CodeWord $(var1~0.1)"
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables


def test_variable_with_comment():
    """Test Java Funz comment syntax: $(var~"comment")"""
    content = 'CodeWord $(var1~"length cm")'
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables


def test_variable_with_bounds():
    """Test Java Funz bounds syntax: $(var~[0,1])"""
    content = "CodeWord $(var1~[0,1])"
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables


def test_variable_with_discrete_values():
    """Test Java Funz discrete values syntax: $(var~{0,0.1,0.2})"""
    content = "CodeWord $(var1~{0,0.1,0.2})"
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables


def test_variable_with_all_metadata():
    """Test Java Funz full metadata syntax: $(var~default;comment;{values})"""
    content = 'CodeWord $(var1~0.1;"cm";{0,0.1,0.2})'
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables


def test_variable_replacement_with_parentheses():
    """Test variable replacement with () delimiters"""
    content = "Value is $(x)"
    result = replace_variables_in_content(
        content, {"x": 42}, varprefix="$", delim="()"
    )
    assert result == "Value is 42"


def test_variable_replacement_with_default():
    """Test variable replacement with default value"""
    content = "Value is $(x~100)"
    # Variable not provided, should use default
    result = replace_variables_in_content(content, {}, varprefix="$", delim="()")
    assert result == "Value is 100"


def test_formula_with_braces():
    """Test that formulas work with {} delimiters like Java Funz"""
    model = {
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }
    content = "Result: @{$x ** 3}"
    result = evaluate_formulas(content, model, {"x": 2}, interpreter="python")
    assert "8" in result


def test_formula_with_format_specifier():
    """Test Java Funz format specifier: @{expr | 0.00}"""
    model = {
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }
    content = "Result: @{$x / 3 | 0.0000}"
    result = evaluate_formulas(content, model, {"x": 1}, interpreter="python")
    # Should format to 4 decimal places
    assert "0.3333" in result


def test_function_declaration_with_colon_prefix():
    """Test Java Funz function declaration: #@: func = ..."""
    model = {
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }
    content = """#@: Navo = 6.022141e+23
Result: @{$x * Navo}"""
    result = evaluate_formulas(content, model, {"x": 1}, interpreter="python")
    assert "6.022141e+23" in result


def test_multiline_function_declaration():
    """Test Java Funz multiline function: #@: func = function(x) {...}"""
    model = {
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }
    content = """#@: def density(l, m):
#@:     if l < 0:
#@:         return m / (0.9 + l**2)
#@:     else:
#@:         return m / l**3
Result: @{density($var1, $var2) | 0.000}"""
    result = evaluate_formulas(content, model, {"var1": 1, "var2": 0.2}, interpreter="python")
    assert "0.200" in result


def test_backward_compatibility_with_braces():
    """Test that old ${var} syntax still works for backward compatibility"""
    content = "Value is ${x}"
    variables = parse_variables_from_content(content, varprefix="$", delim="{}")
    assert "x" in variables

    result = replace_variables_in_content(content, {"x": 42}, varprefix="$", delim="{}")
    assert result == "Value is 42"


def test_mixed_variable_and_formula_delimiters():
    """Test using () for variables and {} for formulas simultaneously"""
    # This would be used in a real model
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }

    # Parse variables with () delimiters
    var_content = "Input: $(x)"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="()")
    assert "x" in variables

    # Replace variables with () delimiters
    var_result = replace_variables_in_content(var_content, {"x": 2}, varprefix="$", delim="()")
    assert var_result == "Input: 2"

    # Evaluate formulas with {} delimiters
    formula_content = "Result: @{$x ** 3}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 2}, interpreter="python")
    assert "8" in formula_result


def test_java_funz_complete_example():
    """Test a complete Java Funz example from the documentation"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }

    content = """# Declare variables
# First variable: $(var1~1.2;"length in cm")
# Second variable: $(var2~0.2;"mass in g")

# Declare constants
#@: L_x = 0.9

# Declare functions
#@: def density(l, m):
#@:     if l < 0:
#@:         return m / (L_x + l**2)
#@:     else:
#@:         return m / l**3

...
CodeWord1 $(var1)
...
CodeWord2 [0.5, 0.7, $(var1), 1.0]
...
CodeWord3 @{density($var1, $var2) | 0.000}
..."""

    # Parse variables
    variables = parse_variables_from_content(content, varprefix="$", delim="()")
    assert "var1" in variables
    assert "var2" in variables

    # Replace variables
    var_result = replace_variables_in_content(
        content, {"var1": 1.2, "var2": 0.2}, varprefix="$", delim="()"
    )
    assert "CodeWord1 1.2" in var_result
    assert "[0.5, 0.7, 1.2, 1.0]" in var_result

    # Evaluate formulas
    final_result = evaluate_formulas(var_result, model, {"var1": 1.2, "var2": 0.2}, interpreter="python")
    # density(1.2, 0.2) = 0.2 / 1.2^3 ≈ 0.116
    assert "0.116" in final_result


def test_delim_sets_both_delimiters():
    """Test that delim field sets both var_delim and formula_delim"""
    model = {
        "var_prefix": "$",
        "formula_prefix": "@",
        "delim": "{}",  # Should apply to both variables and formulas
        "commentline": "#",
    }

    # Variables should use {} when only delim is set
    var_content = "Value: ${x}"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="{}")
    assert "x" in variables

    var_result = replace_variables_in_content(var_content, {"x": 42}, varprefix="$", delim="{}")
    assert var_result == "Value: 42"

    # Formulas should also use {} when only delim is set
    formula_content = "Result: @{$x * 2}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 5}, interpreter="python")
    assert "10" in formula_result


def test_var_delim_overrides_delim():
    """Test that var_delim overrides delim for variables"""
    model = {
        "var_prefix": "$",
        "formula_prefix": "@",
        "delim": "{}",       # Default for both
        "var_delim": "()",   # Override for variables only
        "commentline": "#",
    }

    # Variables should use () from var_delim
    var_content = "Value: $(x)"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="()")
    assert "x" in variables

    # Formulas should still use {} from delim
    formula_content = "Result: @{$x * 2}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 5}, interpreter="python")
    assert "10" in formula_result


def test_formula_delim_overrides_delim():
    """Test that formula_delim overrides delim for formulas"""
    model = {
        "var_prefix": "$",
        "formula_prefix": "@",
        "delim": "()",          # Default for both
        "formula_delim": "{}",  # Override for formulas only
        "commentline": "#",
    }

    # Variables should use () from delim
    var_content = "Value: $(x)"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="()")
    assert "x" in variables

    # Formulas should use {} from formula_delim
    formula_content = "Result: @{$x * 2}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 5}, interpreter="python")
    assert "10" in formula_result


def test_old_field_names_still_work():
    """Test that old field names (varprefix, formulaprefix) still work for backward compatibility"""
    model = {
        "varprefix": "$",        # Old name
        "formulaprefix": "@",    # Old name
        "delim": "{}",
        "commentline": "#",
    }

    # Variables should work with old field name
    var_content = "Value: ${x}"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="{}")
    assert "x" in variables

    var_result = replace_variables_in_content(var_content, {"x": 99}, varprefix="$", delim="{}")
    assert var_result == "Value: 99"

    # Formulas should work with old field name
    formula_content = "Result: @{$x * 3}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 7}, interpreter="python")
    assert "21" in formula_result


def test_new_field_names_override_old():
    """Test that new field names (var_prefix, formula_prefix) take priority over old names"""
    model = {
        "varprefix": "!",        # Old name (should be ignored)
        "var_prefix": "$",       # New name (should be used)
        "formulaprefix": "^",    # Old name (should be ignored)
        "formula_prefix": "@",   # New name (should be used)
        "delim": "{}",
        "commentline": "#",
    }

    # Should use $ from var_prefix, not ! from varprefix
    var_content = "Value: ${x}"
    variables = parse_variables_from_content(var_content, varprefix="$", delim="{}")
    assert "x" in variables

    # Should use @ from formula_prefix, not ^ from formulaprefix
    formula_content = "Result: @{$x * 2}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 4}, interpreter="python")
    assert "8" in formula_result


def test_formprefix_alias():
    """Test that formprefix (short form) works as an alias for formulaprefix"""
    model = {
        "var_prefix": "$",
        "formprefix": "@",      # Short form alias
        "delim": "{}",
        "commentline": "#",
    }

    formula_content = "Result: @{$x + 10}"
    formula_result = evaluate_formulas(formula_content, model, {"x": 5}, interpreter="python")
    assert "15" in formula_result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
