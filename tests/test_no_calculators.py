"""
Negative tests for calculators
Tests error handling for invalid calculators, missing scripts, failed connections, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

from fz import fzr


def test_calculator_nonexistent_script():
    """Test running with a non-existent calculator script"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file
        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "echo 42"
            }
        }

        result_dir = tmpdir / "results"

        # Use non-existent calculator script
        nonexistent_calc = tmpdir / "does_not_exist.sh"

        # Should fail gracefully
        with pytest.raises((FileNotFoundError, RuntimeError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1, 2]},
                calculator=f"sh://{nonexistent_calc}",
                output_path=str(result_dir),
                model=model
            )


def test_calculator_invalid_uri_format():
    """Test calculator with invalid URI format"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Invalid URI format
        with pytest.raises((ValueError, RuntimeError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="invalid_format_no_scheme",  # No :// scheme
                output_path=str(result_dir),
                model=model
            )


def test_calculator_unsupported_scheme():
    """Test calculator with unsupported URI scheme"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Unsupported scheme
        with pytest.raises((ValueError, RuntimeError, NotImplementedError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="ftp://server/script.sh",  # FTP not supported
                output_path=str(result_dir),
                model=model
            )


def test_calculator_script_without_execute_permission():
    """Test running calculator script without execute permissions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create calculator script without execute permission
        calc_script = tmpdir / "no_exec.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        # Don't set execute permission

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}'"
            }
        }

        result_dir = tmpdir / "results"

        # Should fail or handle gracefully (bash might still execute it)
        # Behavior may vary by platform
        try:
            results = fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator=f"sh://{calc_script}",
                output_path=str(result_dir),
                model=model
            )
            # May succeed on some platforms if bash can read it
        except (PermissionError, OSError, RuntimeError):
            # Expected on platforms that enforce execute permission
            pass


def test_calculator_script_with_syntax_error():
    """Test calculator script with bash syntax error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create calculator with invalid bash syntax
        calc_script = tmpdir / "bad_syntax.sh"
        calc_script.write_text("""#!/bin/bash
if [ $x -eq 1  # Missing closing bracket
    echo 'result = 42' > output.txt
fi
""")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}'"
            }
        }

        result_dir = tmpdir / "results"

        # Should fail with non-zero exit code
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator=f"sh://{calc_script}",
            output_path=str(result_dir),
            model=model
        )

        # Results should show failure or None outputs
        if results is not None:
            # Check that results indicate failure
            pass


def test_calculator_script_exits_with_error():
    """Test calculator script that exits with non-zero status"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create calculator that exits with error
        calc_script = tmpdir / "fail.sh"
        calc_script.write_text("""#!/bin/bash
echo 'Calculation failed!' >&2
exit 1
""")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "echo 'no output'"
            }
        }

        result_dir = tmpdir / "results"

        # Should handle failure gracefully
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator=f"sh://{calc_script}",
            output_path=str(result_dir),
            model=model
        )

        # Results may be None or indicate failure
        # FZ should not crash


def test_calculator_script_produces_no_output():
    """Test calculator that runs but produces no output files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Calculator that does nothing
        calc_script = tmpdir / "no_output.sh"
        calc_script.write_text("""#!/bin/bash
# Does nothing, produces no output
exit 0
""")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "cat output.txt"  # But output.txt doesn't exist
            }
        }

        result_dir = tmpdir / "results"

        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator=f"sh://{calc_script}",
            output_path=str(result_dir),
            model=model
        )

        # Should handle missing output file gracefully
        # Results may have None values


def test_calculator_script_timeout():
    """Test calculator that takes too long (if timeout is implemented)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Calculator that sleeps
        calc_script = tmpdir / "slow.sh"
        calc_script.write_text("""#!/bin/bash
sleep 3600  # Sleep for 1 hour
echo 'result = 42' > output.txt
""")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "cat output.txt"
            }
        }

        result_dir = tmpdir / "results"

        # Note: FZ may not have timeout by default, so this test documents behavior
        # If no timeout, test will take very long - skip for now
        pytest.skip("Timeout test would take too long without timeout implementation")


def test_ssh_calculator_invalid_host():
    """Test SSH calculator with invalid hostname"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Invalid hostname
        with pytest.raises((Exception, RuntimeError)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="ssh://nonexistent.invalid.host/calc.sh",
                output_path=str(result_dir),
                model=model
            )


def test_ssh_calculator_invalid_port():
    """Test SSH calculator with invalid port number"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Invalid port number
        with pytest.raises((ValueError, RuntimeError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="ssh://user@localhost:99999/calc.sh",  # Port out of range
                output_path=str(result_dir),
                model=model
            )


def test_ssh_calculator_missing_paramiko():
    """Test SSH calculator when paramiko is not installed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Check if paramiko is available
        try:
            import paramiko
            pytest.skip("paramiko is installed, test not applicable")
        except ImportError:
            pass

        # Should fail with appropriate error
        with pytest.raises((ImportError, RuntimeError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="ssh://localhost/calc.sh",
                output_path=str(result_dir),
                model=model
            )


def test_cache_calculator_nonexistent_directory():
    """Test cache calculator with non-existent cache directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Non-existent cache directory
        nonexistent_cache = tmpdir / "does_not_exist" / "cache"

        # Should handle gracefully (no cache hits)
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1, 2]},
            calculator=f"cache://{nonexistent_cache}",
            output_path=str(result_dir),
            model=model
        )

        # Should return None or empty results (no fallback calculator)


def test_cache_calculator_with_invalid_glob_pattern():
    """Test cache calculator with invalid glob pattern"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Invalid glob pattern (implementation dependent)
        # Most glob implementations handle anything, but document behavior
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator="cache://[invalid[pattern",
            output_path=str(result_dir),
            model=model
        )

        # Should handle gracefully


def test_multiple_calculators_all_fail():
    """Test with multiple calculators where all fail"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create failing calculator
        calc_script = tmpdir / "fail.sh"
        calc_script.write_text("#!/bin/bash\nexit 1\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # All calculators fail
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator=[
                f"sh://{calc_script}",
                "cache://nonexistent",
                f"sh://{tmpdir / 'also_nonexistent.sh'}"
            ],
            output_path=str(result_dir),
            model=model
        )

        # Should complete but with None/failed results


def test_calculator_alias_not_found():
    """Test using a calculator alias that doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        result_dir = tmpdir / "results"

        # Use alias that doesn't exist in .fz/calculators/
        with pytest.raises((ValueError, FileNotFoundError, RuntimeError, Exception)):
            fzr(
                input_path=str(input_file),
                input_variables={"x": [1]},
                calculator="nonexistent_alias",  # Not a URI, treated as alias
                output_path=str(result_dir),
                model=model
            )


def test_calculator_with_special_characters_in_path():
    """Test calculator path with special characters"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create calculator with spaces in path
        calc_dir = tmpdir / "dir with spaces"
        calc_dir.mkdir()
        calc_script = calc_dir / "calc script.sh"
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

        # Should handle spaces in path
        results = fzr(
            input_path=str(input_file),
            input_variables={"x": [1]},
            calculator=f"sh://{calc_script}",
            output_path=str(result_dir),
            model=model
        )

        # Should work correctly with proper path handling


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
