"""
Test all model key aliases for comment, var_prefix, and formula_prefix
"""
import tempfile
from pathlib import Path
from fz import fzi


def test_var_prefix_aliases():
    """Test that all var_prefix aliases work: var_prefix, varprefix, var_char, varchar"""
    
    aliases = [
        ("var_prefix", "$"),
        ("varprefix", "%"),
        ("var_char", "V"),
        ("varchar", "!"),
    ]
    
    for key, prefix in aliases:
        model = {
            key: prefix,
            "var_delim": "()",
            "formula_prefix": "@",
            "formula_delim": "{}",
            "commentline": "#",
            "interpreter": "python",
        }

        content = f"""
#@: CONST = 50

Variable: {prefix}(x~10)
Result: @{{CONST + {prefix}x}}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            with open(input_file, 'w') as f:
                f.write(content)

            result = fzi(str(input_file), model=model)

            # Check variable was parsed
            assert "x" in result, f"Failed for alias '{key}': variable 'x' not found"
            assert result["x"] == 10, f"Failed for alias '{key}': x != 10"

            # Check static constant
            assert "CONST" in result, f"Failed for alias '{key}': CONST not found"
            assert result["CONST"] == "50", f"Failed for alias '{key}': CONST != 50"

            # Check formula evaluated
            # Formula key is CONST + {prefix}x
            result_key = f"CONST + x"
            assert result[result_key] == 60, f"Failed for alias '{key}': formula didn't evaluate to 60"


def test_formula_prefix_aliases():
    """Test that all formula_prefix aliases work"""
    
    aliases = [
        ("formula_prefix", "@"),
        ("formulaprefix", "F"),
        ("form_prefix", "~"),
        ("formprefix", "&"),
        ("formula_char", "="),
        ("form_char", "+"),
    ]
    
    for key, prefix in aliases:
        model = {
            "var_prefix": "$",
            "var_delim": "()",
            key: prefix,
            "formula_delim": "{}",
            "commentline": "#",
            "interpreter": "python",
        }

        content = f"""
#{prefix}: PI = 3.14159

Radius: $(r~5)
Area: {prefix}{{PI * $r ** 2}}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            with open(input_file, 'w') as f:
                f.write(content)

            result = fzi(str(input_file), model=model)

            # Check static constant
            assert "PI" in result, f"Failed for alias '{key}': PI not found"
            assert result["PI"] == "3.14159", f"Failed for alias '{key}': PI value wrong"

            # Check variable
            assert "r" in result, f"Failed for alias '{key}': r not found"
            assert result["r"] == 5, f"Failed for alias '{key}': r != 5"

            # Check formula evaluated (formula expression is the same regardless of prefix)
            formula_key = "PI * r ** 2"
            expected = 3.14159 * 25  # PI * r^2
            assert abs(result[formula_key] - expected) < 0.001, f"Failed for alias '{key}': formula value wrong"


def test_comment_char_aliases():
    """Test that all comment char aliases work"""
    
    aliases = [
        ("commentline", "#"),
        ("comment_line", "*"),
        ("comment_char", "%"),
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
{char}@: VALUE = 100

Number: $(n~5)
Sum: @{{VALUE + $n}}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            with open(input_file, 'w') as f:
                f.write(content)

            result = fzi(str(input_file), model=model)

            # Check static constant
            assert "VALUE" in result, f"Failed for alias '{key}': VALUE not found"
            assert result["VALUE"] == "100", f"Failed for alias '{key}': VALUE != 100"

            # Check formula evaluated
            sum_key = "VALUE + n"
            assert result[sum_key] == 105, f"Failed for alias '{key}': formula didn't evaluate"


def test_combined_aliases():
    """Test using all three alias types together"""
    
    model = {
        "varchar": "V",  # Using varchar alias for var_prefix
        "var_delim": "()",
        "form_char": "F",  # Using form_char alias for formula_prefix
        "formula_delim": "{}",
        "comment": "*",  # Using comment alias
        "interpreter": "python",
    }

    content = """
*F: MULTIPLIER = 3

Input: V(val~7)
Output: F{V(val) * MULTIPLIER}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        with open(input_file, 'w') as f:
            f.write(content)

        result = fzi(str(input_file), model=model)

        # Check all parts work
        assert "MULTIPLIER" in result
        assert result["MULTIPLIER"] == "3"
        assert "val" in result
        assert result["val"] == 7
        
        # Check formula (formula expression, not with prefix)
        formula_key = "val * MULTIPLIER"
        assert result[formula_key] == 21  # 7 * 3


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
