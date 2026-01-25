"""
Test fzi formula parsing and evaluation functionality
"""
import tempfile
from pathlib import Path
from fz import fzi


def test_fzi_returns_variables_and_formulas():
    """Test that fzi returns both variables and formulas"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }

    content = """
# Variables
Length: $(x)
Width: $(y)

# Formulas
Area: @{$x * $y}
Perimeter: @{2 * ($x + $y)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Should return flat dict
        assert isinstance(result, dict)

        # Variables should be found
        assert "x" in result
        assert "y" in result

        # Formulas should be found (without @{} syntax now)
        assert "x * y" in result
        assert "2 * (x + y)" in result


def test_fzi_extracts_variable_defaults():
    """Test that fzi extracts default values from variables"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
    }

    content = """
# Variables with defaults
Length: $(x~10)
Width: $(y~5.5)
Name: $(name~"test")
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Variables should have their default values
        assert result["x"] == 10
        assert result["y"] == 5.5
        assert result["name"] == "test"


def test_fzi_evaluates_formulas_with_defaults():
    """Test that fzi evaluates formulas when all variables have defaults"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Variables with defaults
Length: $(x~10)
Width: $(y~5)

# Formulas
Area: @{$x * $y}
Perimeter: @{2 * ($x + $y)}
Sum: @{$x + $y}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Formulas should be evaluated
        # Find the area formula
        area_formula = "x * y"
        assert result[area_formula] == 50

        # Find the sum formula
        sum_formula = "x + y"
        assert result[sum_formula] == 15

        # Find the perimeter formula
        perim_formula = "2 * (x + y)"
        assert result[perim_formula] == 30


def test_fzi_formulas_without_defaults():
    """Test that formulas without defaults return None"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Variables without defaults
Length: $(x)
Width: $(y)

# Formulas (cannot be evaluated without variable values)
Area: @{$x * $y}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Variables should be None
        assert result["x"] is None
        assert result["y"] is None

        # Formulas should be None (cannot evaluate without values)
        area_formula = "x * y"
        assert result[area_formula] is None


def test_fzi_formulas_with_format_specifier():
    """Test that fzi handles formula format specifiers"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Variables with defaults
Value: $(x~1)

# Formula with format specifier
Result: @{$x / 3 | 0.0000}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Formula should be evaluated with formatting
        formula_key = "x / 3"
        # Should be formatted to 4 decimal places: 1/3 = 0.3333
        assert abs(result[formula_key] - 0.3333) < 0.0001


def test_fzi_mixed_defaults_and_no_defaults():
    """Test formulas when some variables have defaults and some don't"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Variables - some with defaults, some without
Length: $(x~10)
Width: $(y)

# Formulas
Area: @{$x * $y}
Double: @{$x * 2}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Formula using only x (which has default) should evaluate
        double_formula = "x * 2"
        assert result[double_formula] == 20

        # Formula using both x and y (y has no default) should be None
        area_formula = "x * y"
        assert result[area_formula] is None


def test_fzi_with_math_functions():
    """Test formulas with math functions"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Variables with defaults
Radius: $(r~5)

# Formulas with math functions
import math
Area: @{3.14159 * $r ** 2}
Sqrt: @{sqrt($r)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Area formula (no @{} in keys anymore)
        area_formula = "3.14159 * r ** 2"
        assert abs(result[area_formula] - 78.53975) < 0.001

        # Sqrt formula
        sqrt_formula = "sqrt(r)"
        assert abs(result[sqrt_formula] - 2.236) < 0.001


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
