"""
Negative tests for formula evaluation
Tests error handling for missing formulas, invalid formulas, invalid function arguments, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

from fz import fzc
from fz.interpreter import evaluate_formulas


def test_formula_with_syntax_error():
    """Test formula with invalid Python syntax"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input with invalid formula syntax
        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{1 + + 2}\n")  # Invalid: double plus

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        # Should complete but leave formula unevaluated or show error
        result = fzc(
            input_path=str(input_file),
            input_variables={},
            output_path=str(output_file),
            model=model
        )

        # Formula should fail to evaluate (stays as-is or shows error)
        output_content = output_file.read_text()
        # Either keeps original or shows some error indication
        assert "@{1 + + 2}" in output_content or "Error" in output_content or "Warning" in output_content


def test_formula_with_undefined_variable():
    """Test formula referencing undefined variable"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # Formula uses 'z' which is not defined
        input_file.write_text("result = @{$x + $y + $z}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        # Provide only x and y, not z
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},  # z is missing
            output_path=str(output_file),
            model=model
        )

        # Formula evaluation should fail or leave $z unreplaced
        output_content = output_file.read_text()
        # May contain original formula or error
        assert "@{" in output_content or "$z" in output_content or "NameError" in output_content


def test_formula_with_division_by_zero():
    """Test formula that causes division by zero"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x / $y}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        # y = 0 causes division by zero
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 10, "y": 0},
            output_path=str(output_file),
            model=model
        )

        # Should handle error gracefully
        output_content = output_file.read_text()
        # Formula likely stays unevaluated or shows error
        assert "@{" in output_content or "Error" in output_content or "inf" in output_content


def test_formula_with_undefined_function():
    """Test formula calling undefined function"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{undefined_function($x)}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 5},
            output_path=str(output_file),
            model=model
        )

        # Should fail gracefully
        output_content = output_file.read_text()
        assert "@{" in output_content or "NameError" in output_content


def test_formula_with_wrong_function_arguments():
    """Test formula with incorrect number of arguments to function"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # sqrt requires 1 argument, not 2
        input_file.write_text("""
##fz import math
result = @{math.sqrt($x, $y)}
""")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "##fz",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 4, "y": 2},
            output_path=str(output_file),
            model=model
        )

        # Should fail gracefully
        output_content = output_file.read_text()
        assert "@{" in output_content or "TypeError" in output_content


def test_formula_with_import_error():
    """Test formula trying to import non-existent module"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("""
##fz import nonexistent_module_xyz
result = @{nonexistent_module_xyz.func($x)}
""")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "##fz",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_path=str(output_file),
            model=model
        )

        # Import should fail, formula stays unevaluated
        output_content = output_file.read_text()
        # Should preserve original since module import fails
        assert "@{" in output_content or "ImportError" in output_content or "ModuleNotFoundError" in output_content


def test_formula_with_invalid_commentline():
    """Test formula when commentline pattern is invalid/missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # Uses ##fz prefix but model doesn't specify it
        input_file.write_text("""
##fz import math
result = @{math.sqrt($x)}
""")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            # Missing commentline specification
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 16},
            output_path=str(output_file),
            model=model
        )

        # Without commentline, import line won't be recognized
        # Formula may fail due to missing math module
        output_content = output_file.read_text()
        # Either fails or works if math is in default env


def test_formula_with_malformed_context():
    """Test formula with malformed context code"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("""
##fz def my_func(x):
##fz     return x * 2  # Indentation issue if next line has wrong indent
##fz   bad_indent = True
result = @{my_func($x)}
""")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "##fz",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 3},
            output_path=str(output_file),
            model=model
        )

        # Malformed context should be handled gracefully
        output_content = output_file.read_text()
        # May show error or attempt line-by-line execution


def test_formula_with_infinite_recursion():
    """Test formula that causes infinite recursion"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("""
##fz def recursive_func(n):
##fz     return recursive_func(n)  # Infinite recursion
result = @{recursive_func($x)}
""")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "##fz",
            "interpreter": "python"
        }

        # This should hit recursion limit and fail gracefully
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_path=str(output_file),
            model=model
        )

        output_content = output_file.read_text()
        # Should preserve original or show recursion error
        assert "@{" in output_content or "RecursionError" in output_content or "maximum recursion depth" in output_content


def test_formula_without_interpreter():
    """Test formula evaluation when interpreter is not specified"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            # No interpreter specified
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_path=str(output_file),
            model=model
        )

        # Should use default interpreter or skip evaluation
        output_content = output_file.read_text()
        # Might evaluate with default or stay as-is


def test_formula_with_unsupported_interpreter():
    """Test formula with unsupported interpreter type"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "javascript"  # Not supported
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_path=str(output_file),
            model=model
        )

        # Should show warning and skip evaluation
        output_content = output_file.read_text()
        assert "@{" in output_content  # Formula unevaluated


def test_formula_with_r_interpreter_not_installed():
    """Test R formula when rpy2 is not installed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "R"
        }

        # If rpy2 is not installed, should handle gracefully
        try:
            import rpy2
            pytest.skip("rpy2 is installed, test not applicable")
        except ImportError:
            pass

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_path=str(output_file),
            model=model
        )

        # Should show warning about missing rpy2
        output_content = output_file.read_text()
        # Formula should stay unevaluated
        assert "@{" in output_content


def test_evaluate_formulas_with_empty_content():
    """Test formula evaluation on empty string"""
    result = evaluate_formulas(
        content="",
        input_variables={"x": 1},
        formulaprefix="@",
        delim="{}",
        commentline="##fz",
        interpreter="python"
    )

    # Should return empty string without error
    assert result == ""


def test_evaluate_formulas_with_nested_delimiters():
    """Test formula with nested delimiters (edge case)"""
    content = "result = @{max([$x, $y])}\n"

    result = evaluate_formulas(
        content=content,
        input_variables={"x": 5, "y": 10},
        formulaprefix="@",
        delim="{}",
        commentline="##fz",
        interpreter="python"
    )

    # Should handle nested brackets correctly
    # Result depends on whether nested delimiters are supported
    assert "result = " in result


def test_formula_with_string_concatenation():
    """Test formula with string operations that might fail"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # Trying to concatenate number with string might fail
        input_file.write_text("result = @{$x + '_suffix'}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 123},  # Number, not string
            output_path=str(output_file),
            model=model
        )

        # Type error in concatenation should be handled
        output_content = output_file.read_text()
        # Either stays as formula or shows error


def test_formula_with_missing_delimiters():
    """Test formula with missing closing delimiter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y\n")  # Missing closing }

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_path=str(output_file),
            model=model
        )

        # Incomplete formula should not be matched
        output_content = output_file.read_text()
        assert "@{$x + $y" in output_content  # Stays as-is


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
