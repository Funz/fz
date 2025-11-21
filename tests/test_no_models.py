"""
Negative tests for models
Tests error handling for invalid models, missing model fields, failed calculations, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

from fz import fzi, fzc, fzr
from fz.config import get_config, set_interpreter


def get_output_file_content(output_dir):
    """
    Get content from output directory, excluding .fz_hash files.
    Returns content of first non-hash file found.
    """
    output_files = [f for f in output_dir.rglob("*") if f.is_file() and f.name != ".fz_hash"]
    if output_files:
        return output_files[0].read_text()
    return ""


def test_model_missing_varprefix():
    """Test model without varprefix field (should use default or fail)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Model without varprefix
        model = {
            # Missing varprefix
            "delim": "{}",
        }

        # Should use default or fail
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model=model
            )
            # May use default varprefix
        except (KeyError, ValueError):
            # Or may fail
            pass


def test_model_invalid_varprefix_type():
    """Test model with invalid varprefix type"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Invalid varprefix type
        model = {
            "varprefix": 123,  # Should be string
            "delim": "{}",
        }

        # Should handle type error
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model=model
            )
        except (TypeError, ValueError, AttributeError):
            pass


def test_model_invalid_delim_length():
    """Test model with delim that's not 2 characters"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Invalid delim length
        model = {
            "varprefix": "$",
            "delim": "{{{",  # 3 characters instead of 2
        }

        # May raise ValueError for invalid delimiter
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model=model
            )
        except ValueError:
            pass


def test_model_empty_delim():
    """Test model with empty delimiter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = $x\n")  # No delimiters

        output_dir = tmpdir / "output"

        # Empty delimiter
        model = {
            "varprefix": "$",
            "delim": "",
        }

        # Should work with empty delimiter (matches $x pattern)
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_dir=str(output_dir),
            model=model
        )

        # Should substitute $x with 1
        output_content = get_output_file_content(output_dir)
        assert "1" in output_content, "Variable substitution failed with empty delimiter: " + output_content


def test_model_with_invalid_output_dict():
    """Test model with invalid output dictionary structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Invalid output dict type
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": "not a dict"  # Should be dict
        }

        result_dir = tmpdir / "results"

        # Should handle type error
        try:
            results = fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculators=f"sh://{calc_script}",
                results_dir=str(result_dir),
                model=model
            )
        except (TypeError, ValueError, AttributeError):
            pass


def test_model_output_with_failing_command():
    """Test model where output extraction command fails"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Output command that will fail
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "cat nonexistent_file.txt"  # File doesn't exist
            }
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Should complete but result extraction fails (None value)
        # Check that results are not None but may have None values


def test_model_output_with_invalid_shell_command():
    """Test model with malformed shell command in output"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Invalid shell command syntax
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep | | | invalid"  # Malformed pipe syntax
            }
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Command fails but should not crash entire process


def test_model_with_missing_interpreter_for_formula():
    """Test model using formulas without specifying interpreter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

        # Model with formula but no interpreter
        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            # Missing interpreter field
        }

        # Should use default interpreter or fail
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Check behavior - may use default


def test_model_with_invalid_interpreter():
    """Test model with invalid interpreter value"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

        # Invalid interpreter
        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "interpreter": "invalid_language"
        }

        # Should handle gracefully (skip formula evaluation)
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Formula likely stays unevaluated
        output_content = get_output_file_content(output_dir)
        assert "@{" in output_content


def test_model_alias_not_found():
    """Test using a model alias that doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Try to use non-existent model alias
        with pytest.raises((ValueError, FileNotFoundError, Exception)):
            fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model="nonexistent_model_alias"  # String alias that doesn't exist
            )


def test_fzr_with_none_model():
    """Test fzr when model is None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        result_dir = tmpdir / "results"

        # Model is None
        with pytest.raises((TypeError, ValueError, AttributeError)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculators=f"sh://{calc_script}",
                results_dir=str(result_dir),
                model=None
            )


def test_model_with_empty_output_dict():
    """Test model with empty output dictionary"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Empty output dict
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {}  # No outputs defined
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Should run but extract no outputs (empty results)


def test_model_output_command_with_special_characters():
    """Test model output command with special characters that might break shell"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Command with potentially problematic characters
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}' | sed 's/\"//g'"
            }
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Should handle special characters correctly


def test_model_with_non_dict_type():
    """Test passing non-dict type as model"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Model is a list instead of dict
        with pytest.raises((TypeError, ValueError, AttributeError)):
            fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model=["not", "a", "dict"]
            )


def test_model_with_circular_reference():
    """Test model where output command references itself"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # This isn't really circular in implementation, but documents edge case
        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "cat output.txt",
                "result2": "echo ${result}"  # References another output
            }
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Second output won't substitute ${result} - it's not an input variable


def test_set_invalid_interpreter():
    """Test setting invalid interpreter via config"""
    # Try to set invalid interpreter
    with pytest.raises(ValueError):
        set_interpreter("invalid_interpreter_xyz")


def test_model_with_null_values():
    """Test model with None/null values in fields"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        output_dir = tmpdir / "output"

        # Model with None values
        model = {
            "varprefix": "$",
            "delim": None,  # None instead of string
        }

        # Should handle None gracefully or raise error
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_dir=str(output_dir),
                model=model
            )
        except (TypeError, ValueError, AttributeError):
            pass


def test_model_with_very_long_output_command():
    """Test model with extremely long output extraction command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Very long command
        long_command = "cat output.txt" + " | grep result" * 1000

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": long_command
            }
        }

        result_dir = tmpdir / "results"

        # Should handle long commands (may hit system limits)
        try:
            results = fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculators=f"sh://{calc_script}",
                results_dir=str(result_dir),
                model=model
            )
        except (OSError, Exception):
            # May fail due to command length limits
            pass


def test_model_commentline_not_found_in_file():
    """Test when model specifies commentline but it's not in input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # File has no ##fz lines
        input_file.write_text("result = @{$x + $y}\n")

        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "##fz",  # But no such lines in file
            "interpreter": "python"
        }

        # Should work fine, just no context to execute
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},
            output_dir=str(output_dir),
            model=model
        )

        # Formula may or may not evaluate depending on default env


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
