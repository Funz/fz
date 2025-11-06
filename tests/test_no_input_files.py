"""
Negative tests for input files
Tests error handling for missing files, invalid files, corrupted files, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

from fz import fzi, fzc, fzr


def test_fzi_nonexistent_file():
    """Test fzi with a file that doesn't exist"""
    nonexistent = Path("/tmp/does_not_exist_fz_input_12345.txt")

    model = {
        "varprefix": "$",
        "delim": "{}",
    }

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        fzi(input_path=str(nonexistent), model=model)


def test_fzi_nonexistent_directory():
    """Test fzi with a directory that doesn't exist"""
    nonexistent_dir = Path("/tmp/does_not_exist_fz_dir_12345")

    model = {
        "varprefix": "$",
        "delim": "{}",
    }

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        fzi(input_path=str(nonexistent_dir), model=model)


def test_fzc_nonexistent_input_file():
    """Test fzc with non-existent input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        nonexistent_input = tmpdir / "does_not_exist.txt"
        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            fzc(
                input_path=str(nonexistent_input),
                input_variables={"x": 1},
                output_path=str(output_file),
                model=model
            )


def test_fzc_readonly_input_file():
    """Test fzc with read-only input file (should work)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create read-only input file
        input_file = tmpdir / "readonly.txt"
        input_file.write_text("x = ${x}\n")

        if os.name != 'nt':  # Skip on Windows
            os.chmod(input_file, 0o444)

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Should work fine (only reading input)
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_path=str(output_file),
            model=model
        )

        # Restore permissions for cleanup
        if os.name != 'nt':
            os.chmod(input_file, 0o644)

        # Check output was created
        assert output_file.exists()


def test_fzc_binary_input_file():
    """Test fzc with binary input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create binary file
        binary_file = tmpdir / "binary.bin"
        with open(binary_file, 'wb') as f:
            f.write(b'\x00\x01\x02\xff\xfe\xfd')

        output_file = tmpdir / "output.bin"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # May raise UnicodeDecodeError or handle gracefully
        try:
            result = fzc(
                input_path=str(binary_file),
                input_variables={"x": 1},
                output_path=str(output_file),
                model=model
            )
            # Some implementations may handle binary files by skipping them
        except UnicodeDecodeError:
            # Expected for binary files
            pass


def test_fzc_empty_input_file():
    """Test fzc with empty input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create empty file
        input_file = tmpdir / "empty.txt"
        input_file.write_text("")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Should work, just produce empty output
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_path=str(output_file),
            model=model
        )

        # Output should exist and be empty
        assert output_file.exists()
        assert output_file.read_text() == ""


def test_fzc_very_large_input_file():
    """Test fzc with very large input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create large file (10MB)
        input_file = tmpdir / "large.txt"
        with open(input_file, 'w') as f:
            for i in range(100000):
                f.write(f"line {i}: value = ${{x}}\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Should handle large files
        result = fzc(
            input_path=str(input_file),
            input_variables={"x": 1},
            output_path=str(output_file),
            model=model
        )

        # Output should exist
        assert output_file.exists()


def test_fzc_input_file_with_invalid_encoding():
    """Test fzc with file in non-UTF8 encoding"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create file with Latin-1 encoding
        input_file = tmpdir / "latin1.txt"
        with open(input_file, 'wb') as f:
            f.write("value = ${x} \xe9\xe0\xe8".encode('latin-1'))  # Special chars

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # May raise UnicodeDecodeError or handle gracefully
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_path=str(output_file),
                model=model
            )
            # Some implementations may handle encoding errors
        except UnicodeDecodeError:
            # Expected for incompatible encoding
            pass


def test_fzr_nonexistent_input_file():
    """Test fzr with non-existent input file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        nonexistent_input = tmpdir / "does_not_exist.txt"

        # Create calculator
        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "cat output.txt"}
        }

        result_dir = tmpdir / "results"

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            fzr(
                input_path=str(nonexistent_input),
                input_variables={"x": [1]},
                calculator=f"sh://{calc_script}",
                output_path=str(result_dir),
                model=model
            )


def test_fzr_with_directory_as_input():
    """Test fzr with directory containing multiple input files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input directory with multiple files
        input_dir = tmpdir / "inputs"
        input_dir.mkdir()

        (input_dir / "file1.txt").write_text("x = ${x}\n")
        (input_dir / "file2.txt").write_text("y = ${y}\n")

        # Create calculator
        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "cat output.txt"}
        }

        result_dir = tmpdir / "results"

        # Should handle directory input
        results = fzr(
            input_path=str(input_dir),
            input_variables={"x": [1], "y": [2]},
            calculator=f"sh://{calc_script}",
            output_path=str(result_dir),
            model=model
        )

        # Should process all files in directory


def test_fzc_symlink_to_nonexistent_file():
    """Test fzc with symlink pointing to non-existent file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create symlink to non-existent file
        nonexistent = tmpdir / "nonexistent.txt"
        symlink = tmpdir / "broken_link.txt"

        if os.name != 'nt':  # Symlinks work differently on Windows
            os.symlink(nonexistent, symlink)

            output_file = tmpdir / "output.txt"

            model = {
                "varprefix": "$",
                "delim": "{}",
            }

            # Should raise FileNotFoundError when trying to read
            with pytest.raises(FileNotFoundError):
                fzc(
                    input_path=str(symlink),
                    input_variables={"x": 1},
                    output_path=str(output_file),
                    model=model
                )


def test_fzc_circular_symlink():
    """Test fzc with circular symlink"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create circular symlink
        link1 = tmpdir / "link1.txt"
        link2 = tmpdir / "link2.txt"

        if os.name != 'nt':  # Symlinks work differently on Windows
            os.symlink(link2, link1)
            os.symlink(link1, link2)

            output_file = tmpdir / "output.txt"

            model = {
                "varprefix": "$",
                "delim": "{}",
            }

            # Should raise error when trying to read circular symlink
            with pytest.raises((OSError, RuntimeError)):
                fzc(
                    input_path=str(link1),
                    input_variables={"x": 1},
                    output_path=str(output_file),
                    model=model
                )


def test_fzc_input_is_directory_not_file():
    """Test fzc when input path is a directory expecting a file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create directory
        input_dir = tmpdir / "input_dir"
        input_dir.mkdir()

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Behavior depends on implementation - may process directory or raise error
        # Document actual behavior
        try:
            result = fzc(
                input_path=str(input_dir),
                input_variables={"x": 1},
                output_path=str(output_file),
                model=model
            )
            # May process all files in directory
        except (IsADirectoryError, ValueError):
            # Or may raise error expecting a file
            pass


def test_fzi_with_permission_denied():
    """Test fzi when input file has no read permissions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create file with no read permissions
        input_file = tmpdir / "no_read.txt"
        input_file.write_text("x = ${x}\n")

        if os.name != 'nt':  # Skip on Windows
            os.chmod(input_file, 0o000)  # No permissions

            model = {
                "varprefix": "$",
                "delim": "{}",
            }

            # Should raise PermissionError
            with pytest.raises(PermissionError):
                fzi(input_path=str(input_file), model=model)

            # Restore permissions for cleanup
            os.chmod(input_file, 0o644)


def test_fzc_output_to_readonly_file():
    """Test fzc when output file exists and is read-only"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create read-only output file
        output_file = tmpdir / "readonly_output.txt"
        output_file.write_text("old content\n")

        if os.name != 'nt':  # Skip on Windows
            os.chmod(output_file, 0o444)

            model = {
                "varprefix": "$",
                "delim": "{}",
            }

            # Should raise PermissionError when trying to write
            with pytest.raises((PermissionError, OSError)):
                fzc(
                    input_path=str(input_file),
                    input_variables={"x": 1},
                    output_path=str(output_file),
                    model=model
                )

            # Restore permissions for cleanup
            os.chmod(output_file, 0o644)


def test_fzc_input_with_null_bytes():
    """Test fzc with input file containing null bytes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create file with null bytes
        input_file = tmpdir / "null_bytes.txt"
        with open(input_file, 'wb') as f:
            f.write(b"value = ${x}\x00\x00more text\n")

        output_file = tmpdir / "output.txt"

        model = {
            "varprefix": "$",
            "delim": "{}",
        }

        # Should handle or reject null bytes
        try:
            result = fzc(
                input_path=str(input_file),
                input_variables={"x": 1},
                output_path=str(output_file),
                model=model
            )
            # May process successfully treating null bytes as characters
        except (ValueError, UnicodeDecodeError):
            # Or may reject them
            pass


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
