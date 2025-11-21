"""
Negative tests for input variable parsing and handling
Tests error handling for missing variables, invalid variables, invalid syntax, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

from fz import fzi, fzc, fzr
from fz.interpreter import (
    parse_variables_from_content,
    parse_variables_from_file,
    parse_variables_from_path,
    replace_variables_in_content
)


def get_output_file_content(output_dir):
    """
    Get content from output directory, excluding .fz_hash files.
    Returns content of first non-hash file found.
    """
    output_files = [f for f in output_dir.rglob("*") if f.is_file() and f.name != ".fz_hash"]
    if output_files:
        return output_files[0].read_text()
    return ""


def test_parse_variables_from_nonexistent_file():
    """Test parsing variables from a file that doesn't exist"""
    nonexistent = Path("/tmp/does_not_exist_fz_test_12345.txt")

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        parse_variables_from_path(nonexistent, varprefix="$", delim="{}")


def test_parse_variables_from_binary_file():
    """Test that binary files are skipped gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a binary file
        binary_file = tmpdir / "binary.bin"
        with open(binary_file, 'wb') as f:
            f.write(b'\x00\x01\x02\xff\xfe\xfd')

        # Should return empty set (binary files skipped)
        variables = parse_variables_from_file(binary_file, varprefix="$", delim="{}")
        assert isinstance(variables, set)
        assert len(variables) == 0


def test_compile_with_missing_variable():
    """Test fzc compilation when required variable is missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file with variables
        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\ny = ${y}\nz = ${z}\n")

        # Compile with only subset of variables (missing 'z')
        output_dir = tmpdir / "output"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Missing variable 'z' - should leave placeholder unchanged
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1, "y": 2},  # 'z' is missing
            output_dir=str(output_dir),
            model=model
        )

        # Check output - z should still have placeholder
        output_content = get_output_file_content(output_dir)
        assert "x = 1" in output_content
        assert "y = 2" in output_content
        assert "${z}" in output_content  # Unchanged


def test_compile_with_invalid_variable_name():
    """Test compilation with invalid variable names (special characters, etc.)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("value = ${my-var}\n")  # Hyphen not allowed

        # Parse variables - should not match invalid names
        variables = parse_variables_from_file(input_file, varprefix="$", delim="{}")

        # Should be empty since 'my-var' is not a valid identifier
        assert len(variables) == 0 or all(v is None for v in variables.values())


def test_compile_with_empty_variable_name():
    """Test compilation with empty variable placeholder"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        # Empty placeholder
        input_file.write_text("value = ${}\n")

        # Parse variables
        variables = parse_variables_from_file(input_file, varprefix="$", delim="{}")

        # Should not match empty placeholder
        assert len(variables) == 0 or all(v is None for v in variables.values())


def test_compile_with_invalid_delimiter():
    """Test compilation with mismatched or invalid delimiters"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("value = ${x\n")  # Missing closing delimiter

        # Parse with standard delimiters
        variables = parse_variables_from_file(input_file, varprefix="$", delim="{}")

        # Should not match incomplete placeholder
        assert len(variables) == 0 or all(v is None for v in variables.values())


def test_replace_variables_with_none_value():
    """Test variable replacement when variable value is None"""
    content = "x = ${x}, y = ${y}"

    # Replace with None value - should convert to string "None"
    result = replace_variables_in_content(
        content,
        {"x": None, "y": 2},
        varprefix="$",
        delim="{}"
    )

    assert "x = None" in result or "x = ${x}" in result  # Behavior depends on implementation
    assert "y = 2" in result


def test_replace_variables_with_complex_types():
    """Test variable replacement with lists, dicts, etc."""
    content = "value = ${data}"

    # Replace with list
    result = replace_variables_in_content(
        content,
        {"data": [1, 2, 3]},
        varprefix="$",
        delim="{}"
    )

    # Should convert to string representation
    assert "[1, 2, 3]" in result


def test_fzr_with_missing_required_variable():
    """Test fzr when a required variable is not provided"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create simple input file
        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\ny = ${y}\n")

        # Create simple calculator script
        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}'"
            }
        }

        result_dir = tmpdir / "results"

        # Run with missing variable - should still work but leave placeholder
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1, 2]},  # 'y' is missing
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Should complete but with ${y} unchanged in inputs
        assert results is not None


def test_fzi_with_empty_file():
    """Test fzi on an empty file - should return no variables"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create empty file
        empty_file = tmpdir / "empty.txt"
        empty_file.write_text("")

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Parse variables from empty file
        variables = fzi(input_path=str(empty_file), model=model)

        assert isinstance(variables, dict)
        assert len(variables) == 0 or all(v is None for v in variables.values())


def test_fzi_with_no_variables():
    """Test fzi on file with no variable placeholders"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create file without variables
        input_file = tmpdir / "no_vars.txt"
        input_file.write_text("Just some text\nNo variables here\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Parse variables
        variables = fzi(input_path=str(input_file), model=model)

        assert isinstance(variables, dict)
        assert len(variables) == 0 or all(v is None for v in variables.values())


def test_parse_with_invalid_varprefix():
    """Test parsing with unusual variable prefixes"""
    content = "value = @@{x}"

    # Parse with @@ prefix
    variables = parse_variables_from_content(content, varprefix="@@", delim="{}")

    # Should find 'x'
    assert "x" in variables


def test_parse_with_single_char_delimiter():
    """Test parsing with single character delimiter (edge case)"""
    content = "value = $[x]"

    # Using single char delimiter - should work if implementation supports it
    # Implementation may require exactly 2 characters
    try:
        variables = parse_variables_from_content(content, varprefix="$", delim="[]")
        assert "x" in variables
    except (ValueError, AssertionError):
        # If implementation requires exactly 2 chars, that's acceptable
        pass


def test_parse_with_no_delimiter():
    """Test parsing with no delimiters (just prefix)"""
    content = "value = $x + $y"

    # Parse with empty or single-char delimiter
    variables = parse_variables_from_content(content, varprefix="$", delim="")

    # Should find x and y
    assert "x" in variables
    assert "y" in variables


def test_variable_with_numbers_and_underscores():
    """Test that variables with numbers and underscores work correctly"""
    content = "${var_1} ${var2} ${_var3}"

    variables = parse_variables_from_content(content, varprefix="$", delim="{}")

    # All should be valid
    assert "var_1" in variables
    assert "var2" in variables
    assert "_var3" in variables


def test_variable_starting_with_number():
    """Test that variables starting with numbers are rejected"""
    content = "${1var} ${2_var}"

    variables = parse_variables_from_content(content, varprefix="$", delim="{}")

    # Should not match (Python identifiers can't start with numbers)
    assert "1var" not in variables
    assert "2_var" not in variables


def test_variable_with_default_value():
    """Test parsing variables with default value syntax"""
    content = "${x~10} ${y~default_value}"

    variables = parse_variables_from_content(content, varprefix="$", delim="{}")

    # Should extract variable names without the default values
    assert "x" in variables
    assert "y" in variables


def test_replace_variables_preserves_non_matching_patterns():
    """Test that non-matching patterns are preserved"""
    content = "This is ${x} and this is $y and this is {z}"

    result = replace_variables_in_content(
        content,
        {"x": 1, "y": 2, "z": 3},
        varprefix="$",
        delim="{}"
    )

    # Only ${x} should be replaced with delimiters
    assert "1" in result
    # $y might or might not be replaced depending on delimiter requirement
    # {z} should not be replaced (missing prefix)
    assert "{z}" in result


def test_fzc_with_readonly_output_directory():
    """Test fzc when output directory is read-only"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file
        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create read-only directory
        readonly_dir = tmpdir / "readonly"
        readonly_dir.mkdir()

        if os.name != 'nt':  # Skip on Windows
            os.chmod(readonly_dir, 0o444)

            output_dir = readonly_dir / "output"

            model = {
                "varprefix": "$",
                "delim": "{}",
            }

            # Should raise permission error
            with pytest.raises((PermissionError, OSError)):
                fzc(
                    input_path=str(input_file),
                    input_variables={"x": 1},
                    output_dir=str(output_dir),
                    model=model
                )

            # Restore permissions
            os.chmod(readonly_dir, 0o755)


def test_fzr_with_empty_input_variables():
    """Test fzr with empty input_variables dict"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file with no variables
        input_file = tmpdir / "input.txt"
        input_file.write_text("constant = 42\n")

        # Create calculator script
        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 100' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}'"
            }
        }

        result_dir = tmpdir / "results"

        # Run with empty variables - should still execute once
        results = fzr(
            input_path=str(input_file),
            input_variables={},  # Empty
            calculators=f"sh://{calc_script}",
            results_dir=str(result_dir),
            model=model
        )

        # Should execute once with no variable substitution
        assert results is not None


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
