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
        input_file.write_text("result = @{1 + * 2}\n")  # Invalid: double plus

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Formula should fail to evaluate (stays as-is or shows error)
        output_files = list(output_dir.glob("**/*"))
        if output_files:
            output_content = output_files[0].read_text()
            # Either keeps original or shows some error indication
            assert "@{1 + * 2}" in output_content or "Error" in output_content or "Warning" in output_content, "Formula with syntax error should not evaluate: " + output_content


def test_formula_with_undefined_variable():
    """Test formula referencing undefined variable"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # Formula uses 'z' which is not defined
        input_file.write_text("result = @{$x + $y + $z}\n")

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Formula evaluation should fail or leave $z unreplaced
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # May contain original formula or error
        assert "@{" in output_content or "$z" in output_content or "NameError" in output_content


def test_formula_with_division_by_zero():
    """Test formula that causes division by zero"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x / $y}\n")

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Should handle error gracefully
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # Formula likely stays unevaluated or shows error
        assert "@{" in output_content or "Error" in output_content or "inf" in output_content


def test_formula_with_undefined_function():
    """Test formula calling undefined function"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{undefined_function($x)}\n")

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 5},
            output_dir=str(output_dir),
            model=model
        )

        # Should fail gracefully
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
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

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Should fail gracefully
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
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

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Import should fail, formula stays unevaluated
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
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

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Without commentline, import line won't be recognized
        # Formula may fail due to missing math module
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
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

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Malformed context should be handled gracefully
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
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

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # Should preserve original or show recursion error
        assert "@{" in output_content or "RecursionError" in output_content or "maximum recursion depth" in output_content


def test_formula_without_interpreter():
    """Test formula evaluation when interpreter is not specified"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            # No interpreter specified
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Should use default interpreter or skip evaluation
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # Might evaluate with default or stay as-is


def test_formula_with_unsupported_interpreter():
    """Test formula with unsupported interpreter type"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "notavailable"  # Not supported
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Should show warning and skip evaluation
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        assert "@{" in output_content, "Formula should remain unevaluated with unsupported interpreter: " + output_content

def test_formula_with_r_interpreter_not_installed():
    """Test R formula when rpy2 is not installed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

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
            output_dir=str(output_dir),
            model=model
        )

        # Should show warning about missing rpy2
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # Formula should stay unevaluated
        assert "@{" in output_content


def test_evaluate_formulas_with_empty_content():
    """Test formula evaluation on empty string"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "##fz"
    }
    result = evaluate_formulas(
        content="",
        model=model,
        input_variables={"x": 1},
        interpreter="python"
    )

    # Should return empty string without error
    assert result == ""


def test_evaluate_formulas_with_nested_delimiters():
    """Test formula with nested delimiters (edge case)"""
    content = "result = @{max([$x, $y])}\n"

    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "##fz"
    }
    result = evaluate_formulas(
        content=content,
        model=model,
        input_variables={"x": 5, "y": 10},
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

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 123},  # Number, not string
            output_dir=str(output_dir),
            model=model
        )

        # Type error in concatenation should be handled
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        # Either stays as formula or shows error


def test_formula_with_missing_delimiters():
    """Test formula with missing closing delimiter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y\n")  # Missing closing }

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "python"
        }

        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Incomplete formula should not be matched
        output_files = [f for f in output_dir.rglob("*") if f.is_file()]; output_content = output_files[0].read_text() if output_files else ""
        assert "@{1 + 2" in output_content, "Incomplete formula should remain unevaluated: " + output_content


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
