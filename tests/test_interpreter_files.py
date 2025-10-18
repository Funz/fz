"""
Test interpreters (Python and R) with actual input files
Tests variable substitution and formula evaluation with both interpreters
"""
import os
import pytest
from pathlib import Path
from fz.interpreter import (
    evaluate_formulas,
    replace_variables_in_content,
    parse_variables_from_file
)


# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "interpreter_test_files"


def _check_rpy2_available():
    """Helper function to check if rpy2 is installed"""
    try:
        import rpy2
        return True
    except ImportError:
        return False


class TestPythonInterpreterWithFiles:
    """Test Python interpreter with file inputs"""

    def test_python_simple_file(self):
        """Test Python interpreter with simple formulas file"""
        input_file = TEST_DATA_DIR / "python_simple.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        # Test variable parsing
        variables = parse_variables_from_file(input_file, varprefix="$", delim="{}")
        assert "radius" in variables
        assert "height" in variables

        # Replace variables
        input_variables = {"radius": 5, "height": 10}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        # Evaluate formulas
        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="python")

        # Check results
        assert "Radius: 5" in result
        assert "Height: 10" in result
        assert "Diameter: 10" in result  # 2 * 5
        assert "31.4159" in result  # Circumference
        assert "78.5" in result or "78.6" in result  # Area
        assert "785" in result  # Volume (approximately)

    def test_python_with_context_file(self):
        """Test Python interpreter with context (function definitions)"""
        input_file = TEST_DATA_DIR / "python_with_context.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        input_variables = {"radius": 3, "height": 7}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="python")

        # Check that functions were defined and used
        assert "Radius: 3" in result
        assert "Height: 7" in result
        # Volume = pi * r^2 * h = 3.14159 * 9 * 7 ≈ 197.92
        assert "197.9" in result or "198.0" in result
        # Should have surface area calculated
        assert "Surface Area:" in result

    def test_python_complex_file(self):
        """Test Python interpreter with complex formulas"""
        input_file = TEST_DATA_DIR / "python_complex.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        # Test quadratic equation: x^2 - 5x + 6 = 0 (solutions: 2 and 3)
        input_variables = {"a": 1, "b": -5, "c": 6}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="python")

        # Check coefficients
        assert "a = 1" in result
        assert "b = -5" in result
        assert "c = 6" in result

        # Discriminant = b^2 - 4ac = 25 - 24 = 1
        assert "Discriminant: 1" in result

        # Solutions should be 3.0 and 2.0
        assert "3.0" in result and "2.0" in result

    def test_python_multiple_variables(self):
        """Test Python interpreter with multiple variables in one file"""
        content = """
Parameters: $x, $y, $z

Arithmetic:
- Sum: @{$x + $y + $z}
- Product: @{$x * $y * $z}
- Average: @{($x + $y + $z) / 3}

Comparisons:
- Max: @{max([$x, $y, $z])}
- Min: @{min([$x, $y, $z])}
"""

        input_variables = {"x": 10, "y": 20, "z": 5}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="python")

        assert "Parameters: 10, 20, 5" in result
        assert "Sum: 35" in result
        assert "Product: 1000" in result
        assert "Average: 11.666" in result or "Average: 11.67" in result
        assert "Max: 20" in result
        assert "Min: 5" in result


@pytest.mark.skipif(
    not _check_rpy2_available(),
    reason="rpy2 not installed"
)
class TestRInterpreterWithFiles:
    """Test R interpreter with file inputs"""

    def test_r_simple_file(self):
        """Test R interpreter with simple formulas file"""
        input_file = TEST_DATA_DIR / "r_simple.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        # Test variable parsing
        variables = parse_variables_from_file(input_file, varprefix="$", delim="{}")
        assert "radius" in variables
        assert "height" in variables

        # Replace variables
        input_variables = {"radius": 5, "height": 10}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        # Evaluate formulas
        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="R")

        # Check results
        assert "Radius: 5" in result
        assert "Height: 10" in result
        assert "Diameter: 10" in result  # 2 * 5
        assert "31.4159" in result  # Circumference
        assert "78.5" in result or "78.6" in result  # Area
        assert "785" in result  # Volume (approximately)

    def test_r_with_context_file(self):
        """Test R interpreter with context (function definitions)"""
        input_file = TEST_DATA_DIR / "r_with_context.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        input_variables = {"radius": 3, "height": 7}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="R")

        # Check that functions were defined and used
        assert "Radius: 3" in result
        assert "Height: 7" in result
        # Volume = pi * r^2 * h = 3.14159 * 9 * 7 ≈ 197.92
        assert "197.9" in result or "198.0" in result
        # Should have surface area calculated
        assert "Surface Area:" in result

    def test_r_statistical_file(self):
        """Test R interpreter with statistical functions"""
        input_file = TEST_DATA_DIR / "r_statistical.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        # Use fixed seed for reproducibility
        input_variables = {"n": 100, "mean": 50, "sd": 10, "seed": 42}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="R")

        # Check configuration displayed
        assert "Sample size (n): 100" in result
        assert "Mean: 50" in result
        assert "Standard deviation: 10" in result

        # Statistical calculations should be present
        assert "Mean:" in result
        assert "Median:" in result
        assert "Standard Deviation:" in result
        assert "Variance:" in result

    def test_r_vectors_file(self):
        """Test R interpreter with vector operations"""
        input_file = TEST_DATA_DIR / "r_vectors.txt"
        assert input_file.exists(), f"Test file not found: {input_file}"

        with open(input_file, 'r') as f:
            content = f.read()

        input_variables = {"max_val": 10, "start": 0, "end": 100, "n_points": 11}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="R")

        # Check input values
        assert "Input range: 1 to 10" in result

        # Sum of 1:10 = 55
        assert "Sum: 55" in result
        # Length of 1:10 = 10
        assert "Length: 10" in result
        # Mean of 1:10 = 5.5
        assert "Mean: 5.5" in result

    def test_r_multiple_variables(self):
        """Test R interpreter with multiple variables"""
        content = """
#@sum_func <- function(a, b, c) { a + b + c }
#@prod_func <- function(a, b, c) { a * b * c }

Variables: $x, $y, $z

Results:
- Sum: @{sum_func(x, y, z)}
- Product: @{prod_func(x, y, z)}
- Mean: @{mean(c(x, y, z))}
"""

        input_variables = {"x": 2, "y": 4, "z": 6}
        content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }
        result = evaluate_formulas(content, model, input_variables, interpreter="R")

        assert "Variables: 2, 4, 6" in result
        assert "Sum: 12" in result
        assert "Product: 48" in result
        assert "Mean: 4" in result


class TestInterpreterComparison:
    """Compare Python and R interpreters with same inputs"""

    def test_same_calculation_both_interpreters(self):
        """Test that both interpreters produce same results for simple math"""
        content = """
Radius: $radius
Circumference: @{2 * 3.14159 * $radius}
Area: @{3.14159 * $radius * $radius}
"""

        input_variables = {"radius": 7}
        content_processed = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }

        # Python result
        result_python = evaluate_formulas(content_processed, model, input_variables, interpreter="python")

        # R result (if available)
        if _check_rpy2_available():
            result_r = evaluate_formulas(content_processed, model, input_variables, interpreter="R")

            # Both should have the same numeric results
            assert "Radius: 7" in result_python
            assert "Radius: 7" in result_r

            # Extract circumference (should be approximately 43.98)
            assert "43.98" in result_python or "43.99" in result_python
            assert "43.98" in result_r or "43.99" in result_r

    def test_python_vs_r_constants(self):
        """Test that Python and R handle constants differently"""
        # Python needs math.pi, R has built-in pi
        python_content = """
#@import math
Circle area: @{math.pi * $r ** 2}
"""

        r_content = """
Circle area: @{pi * r^2}
"""

        input_variables = {"r": 5}
        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }

        # Python
        python_processed = replace_variables_in_content(python_content, input_variables, varprefix="$", delim="{}")
        result_python = evaluate_formulas(python_processed, model, input_variables, interpreter="python")

        # Both should calculate pi * 25 ≈ 78.54
        assert "78.5" in result_python

        # R (if available)
        if _check_rpy2_available():
            r_processed = replace_variables_in_content(r_content, input_variables, varprefix="$", delim="{}")
            result_r = evaluate_formulas(r_processed, model, input_variables, interpreter="R")
            assert "78.5" in result_r


class TestMultiFileScenarios:
    """Test scenarios with multiple files and directories"""

    def test_parse_variables_from_multiple_files(self):
        """Test parsing variables from multiple files"""
        python_simple = TEST_DATA_DIR / "python_simple.txt"
        python_complex = TEST_DATA_DIR / "python_complex.txt"

        vars1 = parse_variables_from_file(python_simple, varprefix="$", delim="{}")
        vars2 = parse_variables_from_file(python_complex, varprefix="$", delim="{}")

        # python_simple should have radius, height
        assert "radius" in vars1
        assert "height" in vars1

        # python_complex should have a, b, c
        assert "a" in vars2
        assert "b" in vars2
        assert "c" in vars2

    def test_directory_with_mixed_files(self):
        """Test that directory contains both Python and R test files"""
        files = list(TEST_DATA_DIR.glob("*.txt"))
        assert len(files) > 0, "No test files found in directory"

        # Check we have both Python and R files
        python_files = [f for f in files if f.name.startswith("python_")]
        r_files = [f for f in files if f.name.startswith("r_")]

        assert len(python_files) >= 3, f"Expected at least 3 Python test files, found {len(python_files)}"
        assert len(r_files) >= 3, f"Expected at least 3 R test files, found {len(r_files)}"

    def test_same_variables_different_files(self):
        """Test using same variables with different file templates"""
        python_file = TEST_DATA_DIR / "python_simple.txt"
        r_file = TEST_DATA_DIR / "r_simple.txt"

        # Both files use radius and height
        input_variables = {"radius": 4, "height": 8}
        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#"
        }

        # Process Python file
        with open(python_file, 'r') as f:
            python_content = f.read()
        python_content = replace_variables_in_content(python_content, input_variables, varprefix="$", delim="{}")
        python_result = evaluate_formulas(python_content, model, input_variables, interpreter="python")

        # Both should have radius=4, height=8
        assert "Radius: 4" in python_result
        assert "Height: 8" in python_result

        # Process R file (if rpy2 available)
        if _check_rpy2_available():
            with open(r_file, 'r') as f:
                r_content = f.read()
            r_content = replace_variables_in_content(r_content, input_variables, varprefix="$", delim="{}")
            r_result = evaluate_formulas(r_content, model, input_variables, interpreter="R")

            assert "Radius: 4" in r_result
            assert "Height: 8" in r_result


if __name__ == "__main__":
    # Run tests directly
    import sys

    print("=" * 70)
    print("Testing Python Interpreter with Files")
    print("=" * 70)

    test_python = TestPythonInterpreterWithFiles()

    print("\n1. Testing simple Python file...")
    test_python.test_python_simple_file()
    print("✓ Passed")

    print("\n2. Testing Python file with context...")
    test_python.test_python_with_context_file()
    print("✓ Passed")

    print("\n3. Testing complex Python file...")
    test_python.test_python_complex_file()
    print("✓ Passed")

    print("\n4. Testing Python with multiple variables...")
    test_python.test_python_multiple_variables()
    print("✓ Passed")

    if _check_rpy2_available():
        print("\n" + "=" * 70)
        print("Testing R Interpreter with Files")
        print("=" * 70)

        test_r = TestRInterpreterWithFiles()

        print("\n1. Testing simple R file...")
        test_r.test_r_simple_file()
        print("✓ Passed")

        print("\n2. Testing R file with context...")
        test_r.test_r_with_context_file()
        print("✓ Passed")

        print("\n3. Testing R statistical file...")
        test_r.test_r_statistical_file()
        print("✓ Passed")

        print("\n4. Testing R vectors file...")
        test_r.test_r_vectors_file()
        print("✓ Passed")

        print("\n5. Testing R with multiple variables...")
        test_r.test_r_multiple_variables()
        print("✓ Passed")

        print("\n" + "=" * 70)
        print("Testing Interpreter Comparison")
        print("=" * 70)

        test_compare = TestInterpreterComparison()

        print("\n1. Testing same calculation in both interpreters...")
        test_compare.test_same_calculation_both_interpreters()
        print("✓ Passed")

        print("\n2. Testing Python vs R constants...")
        test_compare.test_python_vs_r_constants()
        print("✓ Passed")

    print("\n" + "=" * 70)
    print("Testing Multi-File Scenarios")
    print("=" * 70)

    test_multi = TestMultiFileScenarios()

    print("\n1. Testing variable parsing from multiple files...")
    test_multi.test_parse_variables_from_multiple_files()
    print("✓ Passed")

    print("\n2. Testing directory with mixed files...")
    test_multi.test_directory_with_mixed_files()
    print("✓ Passed")

    print("\n3. Testing same variables in different files...")
    test_multi.test_same_variables_different_files()
    print("✓ Passed")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
