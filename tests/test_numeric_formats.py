#!/usr/bin/env python3
"""
Test that various Python numeric formats are correctly parsed
"""
import pytest
import tempfile
from pathlib import Path
from fz import fzi
from fz.interpreter import cast_output


class TestCastOutput:
    """Test cast_output function handles various numeric formats"""

    def test_hexadecimal_numbers(self):
        """Test that hexadecimal numbers are correctly parsed"""
        assert cast_output("0x1F") == 31
        assert cast_output("0xFF") == 255
        assert cast_output("0x0") == 0

    def test_octal_numbers(self):
        """Test that octal numbers are correctly parsed"""
        assert cast_output("0o77") == 63
        assert cast_output("0o10") == 8
        assert cast_output("0o0") == 0

    def test_binary_numbers(self):
        """Test that binary numbers are correctly parsed"""
        assert cast_output("0b1010") == 10
        assert cast_output("0b1111") == 15
        assert cast_output("0b0") == 0

    def test_numbers_with_underscores(self):
        """Test that numbers with underscores are correctly parsed"""
        assert cast_output("1_000_000") == 1000000
        assert cast_output("1_234_567") == 1234567
        assert cast_output("3.14_15_93") == 3.141593

    def test_scientific_notation(self):
        """Test that scientific notation works"""
        assert cast_output("1e6") == 1000000.0
        assert cast_output("1.5e-3") == 0.0015
        assert cast_output("2.5E+2") == 250.0

    def test_regular_integers(self):
        """Test that regular integers still work"""
        assert cast_output("42") == 42
        assert cast_output("0") == 0
        assert cast_output("-10") == -10

    def test_regular_floats(self):
        """Test that regular floats still work"""
        assert cast_output("3.14") == 3.14
        assert cast_output("-2.5") == -2.5
        assert cast_output("0.0") == 0.0


class TestFziDefaultValues:
    """Test fzi function handles various numeric formats in default values"""

    def test_hexadecimal_default(self):
        """Test hexadecimal default values in variable declarations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text("x = ${x~0x1F}\n")

            model = {"delim": "{}"}
            result = fzi(str(input_file), model)

            assert 'x' in result
            # Should parse 0x1F as integer 31
            assert result['x'] == 31, \
                f"Expected 31, got {result['x']} (type: {type(result['x'])})"
            assert isinstance(result['x'], int), \
                f"Expected int type, got {type(result['x'])}"

    def test_octal_default(self):
        """Test octal default values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text("perms = ${perms~0o755}\n")

            model = {"delim": "{}"}
            result = fzi(str(input_file), model)

            assert 'perms' in result
            # Should parse 0o755 as integer 493
            assert result['perms'] == 493, \
                f"Expected 493, got {result['perms']} (type: {type(result['perms'])})"
            assert isinstance(result['perms'], int), \
                f"Expected int type, got {type(result['perms'])}"

    def test_binary_default(self):
        """Test binary default values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text("flags = ${flags~0b1010}\n")

            model = {"delim": "{}"}
            result = fzi(str(input_file), model)

            assert 'flags' in result
            # Should parse 0b1010 as integer 10
            assert result['flags'] == 10, \
                f"Expected 10, got {result['flags']} (type: {type(result['flags'])})"
            assert isinstance(result['flags'], int), \
                f"Expected int type, got {type(result['flags'])}"

    def test_underscore_default(self):
        """Test numbers with underscores in default values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text("count = ${count~1_000_000}\n")

            model = {"delim": "{}"}
            result = fzi(str(input_file), model)

            assert 'count' in result
            # Should parse 1_000_000 as integer 1000000
            assert result['count'] == 1000000, \
                f"Expected 1000000, got {result['count']} (type: {type(result['count'])})"
            assert isinstance(result['count'], int), \
                f"Expected int type, got {type(result['count'])}"

    def test_regular_numeric_defaults_still_work(self):
        """Test that regular numeric defaults still work after the fix"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text("""
x = ${x~42}
y = ${y~3.14}
z = ${z~1e6}
""")

            model = {"delim": "{}"}
            result = fzi(str(input_file), model)

            assert result['x'] == 42
            assert result['y'] == 3.14
            assert result['z'] == 1000000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
