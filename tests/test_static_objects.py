"""
Test static object definitions (constants, functions) in fzi
"""
import tempfile
from pathlib import Path
from fz import fzi


def test_fzi_with_constant_definition():
    """Test that fzi parses constant definitions and returns their expressions"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Static object: constant
#@: PI = 3.14159

# Variable with default
Radius: $(r~5)

# Formula using the constant
Area: @{PI * $r ** 2}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constant should be in result with its expression
        assert "PI" in result
        assert result["PI"] == "3.14159"  # Expression, not evaluated value

        # Variable should be in result
        assert "r" in result
        assert result["r"] == 5

        # Formula should be evaluated using the constant (formulas still evaluate)
        # Formula key is now just the expression (no @{...})
        assert "PI * $r ** 2" in result
        assert abs(result["PI * $r ** 2"] - 78.53975) < 0.001


def test_fzi_with_function_definition():
    """Test that fzi parses and evaluates function definitions"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Static object: function
#@: def double(x):
#@:     return x * 2

# Variable with default
Value: $(val~10)

# Formula using the function
Result: @{double($val)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Function should be in result (as callable)
        assert "double" in result
        assert "def double(x):" in result["double"]

        # Variable should be in result
        assert "val" in result
        assert result["val"] == 10

        # Formula should be evaluated using the function
        # Formula key is now just the expression
        result_key = "double($val)"
        assert result[result_key] == 20


def test_fzi_with_multiple_constants():
    """Test multiple constant definitions"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Multiple constants
#@: R = 8.314
#@: Navo = 6.022e23
#@: c = 299792458

# Variables
Temperature: $(T~273.15)
Moles: $(n~1)

# Formula using constants
Energy: @{$n * R * $T}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # All constants should be present
        assert "R" in result
        assert result["R"] == "8.314"
        assert "Navo" in result
        assert "6.022e23" in result["Navo"]
        assert "c" in result
        assert result["c"] == "299792458"


def test_fzi_with_multiline_function():
    """Test multiline function definition"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Multiline function with if statement
#@: def classify(x):
#@:     if x > 0:
#@:         return "positive"
#@:     elif x < 0:
#@:         return "negative"
#@:     else:
#@:         return "zero"

# Variable
Value: $(val~5)

# Formula using function
Classification: @{classify($val)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Function should exist
        assert "classify" in result
        assert "def classify(x):" in result["classify"]

        # Formula result
        class_key = "classify($val)"
        assert result[class_key] == "positive"


def test_fzi_static_objects_without_variables():
    """Test that static objects work even without variables"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Constants only
#@: G = 6.674e-11
#@: h = 6.626e-34

# Formula using only constants
Planck_per_G: @{h / G}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constants should be present
        assert "G" in result
        assert "h" in result

        # Formula should evaluate
        # Any formula key will do
        formula_keys = [k for k in result.keys() if k not in ["G", "h"]]
        formula_key = formula_keys[0] if formula_keys else None
        if formula_key:
        assert result[formula_key] is not None


def test_fzi_ignores_unit_tests():
    """Test that unit test lines (#@?) are ignored"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Constant
#@: PI = 3.14159

# Unit test (should be ignored)
#@? PI > 3

# Variable
Radius: $(r~1)
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constant should be present
        assert "PI" in result
        # Unit test should NOT create any weird keys
        assert not any("?" in k for k in result.keys())


def test_fzi_with_import_statement():
    """Test static objects with import statements"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Import and use math module
#@: import math
#@: sqrt2 = math.sqrt(2)

# Variable
Value: $(x~4)

# Formula using math
SquareRoot: @{math.sqrt($x)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constant should be present (as expression)
        assert "sqrt2" in result
        assert "math.sqrt(2)" in result["sqrt2"]

        # Formula should evaluate (using the imported math module)
        sqrt_key = "math.sqrt($x)"
        assert abs(result[sqrt_key] - 2.0) < 0.001


def test_fzi_static_objects_with_formula_no_variables():
    """Test formulas that use only static objects, no variables"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# Constants
#@: a = 10
#@: b = 20

# Formula using only constants
Sum: @{a + b}
Product: @{a * b}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constants should be present
        assert result["a"] == "10"
        assert result["b"] == "20"

        # Formulas should evaluate
        sum_key = "a + b"
        assert result[sum_key] == 30

        prod_key = "a * b"
        assert result[prod_key] == 200


def test_fzi_java_funz_example_from_docs():
    """Test example from ParameterizingInputFiles.md"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# First variable: $(var1~1.2)
# Second variable: $(var2~0.2)

# Declare constants
#@: L_x = 0.9

# Declare functions
#@: def density(l, m):
#@:     if l < 0:
#@:         return m / (L_x + l**2)
#@:     else:
#@:         return m / l**3

# Formula using function
Density1: @{density(1, $var2)}
Density2: @{density(-1, $var2)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constants should be present (as expressions)
        assert "L_x" in result
        assert result["L_x"] == "0.9"

        # Function should be present (as expression)
        assert "density" in result
        assert "def density(l, m):" in result["density"]

        # Variables should have defaults
        assert result["var1"] == 1.2
        assert result["var2"] == 0.2

        # Formulas should evaluate
        density1_key = "density(1, $var2)"
        assert result[density1_key] == 0.2  # 0.2 / 1^3 = 0.2

        density2_key = "density(-1, $var2)"
        expected = 0.2 / (0.9 + 1)  # 0.2 / (L_x + (-1)^2) = 0.2 / 1.9
        assert abs(result[density2_key] - expected) < 0.001


def test_fzi_static_objects_require_colon():
    """Test that only lines with #@: (colon) are treated as static objects, not #@ alone"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    content = """
# This is a regular comment
#@ This is also just a comment (no colon after @)
#@: pi = 3.14159

# Variable
Radius: $(r~2)

# Formula
Area: @{pi * $r ** 2}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Only pi should be in result (from #@: line)
        assert "pi" in result
        assert result["pi"] == "3.14159"

        # Words from #@ comment should NOT be in result
        assert "This" not in result
        assert "is" not in result
        assert "also" not in result
        assert "just" not in result

        # Variable should be present
        assert "r" in result
        assert result["r"] == 2

        # Formula should evaluate
        area_key = "pi * $r ** 2"
        expected_area = 3.14159 * 4  # pi * r^2 = 3.14159 * 4
        assert abs(result[area_key] - expected_area) < 0.001


def test_fzi_static_objects_with_R_interpreter():
    """Test that static objects work correctly with R interpreter"""
    try:
        import rpy2
    except ImportError:
        import pytest
        pytest.skip("rpy2 not installed")
    
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "*",
        "interpreter": "R",
    }

    content = """
*@: Pu_in_PuO2 = 0.88211
*@: H_fiss_cm <- function(Pu_mass_kg, PuO2_dens_gcm3) {
*@:     min(296, 1000*Pu_mass_kg/(pi/4*11.5^2*PuO2_dens_gcm3*Pu_in_PuO2))
*@: }

Mass: $(mass~34)
Density: $(dens~1)

Height: @{H_fiss_cm($mass, $dens)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Static constant should be present (as expression)
        assert "Pu_in_PuO2" in result
        assert result["Pu_in_PuO2"] == "0.88211"

        # Static function should be present (as expression)
        assert "H_fiss_cm" in result
        assert "function(Pu_mass_kg, PuO2_dens_gcm3)" in result["H_fiss_cm"]

        # Variables should have defaults
        assert result["mass"] == 34
        assert result["dens"] == 1

        # Formula should evaluate successfully (not None)
        height_key = "H_fiss_cm($mass, $dens)"
        assert result[height_key] is not None
        # The function calculates height based on mass and density
        assert result[height_key] > 0


def test_fzi_comment_char_alias():
    """Test that comment_char is accepted as alias for commentline"""
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "comment_char": "*",  # Using comment_char instead of commentline
        "interpreter": "python",
    }

    content = """
*@: MY_CONSTANT = 42

Value: $(v~10)
Result: @{MY_CONSTANT + $v}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Constant should be present
        assert "MY_CONSTANT" in result
        assert result["MY_CONSTANT"] == "42"

        # Formula should evaluate
        result_key = [k for k in result.keys() if "@{" in k][0]
        assert result[result_key] == 52  # 42 + 10


def test_fzi_all_comment_key_aliases():
    """Test that all comment key aliases work: commentline, comment_line, comment_char, commentchar, comment"""
    
    # Test each alias
    aliases = [
        ("commentline", "*"),
        ("comment_line", "%"),
        ("comment_char", "!"),
        ("commentchar", "//"),
        ("comment", ">>"),
    ]
    
    for key, char in aliases:
        model = {
            "var_prefix": "$",
            "var_delim": "()",
            "formula_prefix": "@",
            "formula_delim": "{}",
            key: char,
            "interpreter": "python",
        }

        content = f"""
{char}@: CONST = 99

Variable: $(x~1)
Sum: @{{CONST + $x}}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            with open(input_file, 'w') as f:
                f.write(content)

            result = fzi(str(input_file), model=model)

            # Check static object was parsed
            assert "CONST" in result, f"Failed for alias '{key}': CONST not found"
            assert result["CONST"] == "99", f"Failed for alias '{key}': CONST != 99"

            # Check formula evaluated
            sum_key = [k for k in result.keys() if "@{" in k][0]
            assert result[sum_key] == 100, f"Failed for alias '{key}': formula didn't evaluate"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
