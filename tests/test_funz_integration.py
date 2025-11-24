"""
Integration tests for Funz calculator

Tests real Funz calculator servers running on localhost.
This test requires Funz calculator servers to be running (they announce via UDP).
"""
import pytest
import tempfile
import time
from pathlib import Path
import fz


def test_funz_sequential_simple_calculation():
    """
    Test sequential execution with a single Funz calculator

    Uses a simple shell-based calculation that doesn't require R or Python
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Create a simple input template with variables
        input_file = working_dir / "input.txt"
        input_file.write_text("""# Simple calculation input
a=$a
b=$b
""")

        # Create a simple calculation script
        calc_script = working_dir / "calc.sh"
        calc_script.write_text("""#!/bin/bash
# Read input
source input.txt

# Calculate result (a + b)
result=$(echo "$a + $b" | bc)

# Write output
echo "result = $result" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "result": "grep 'result = ' output.txt | awk '{print $3}'"
            }
        }

        # Define input variables for 3 simple cases
        input_variables = {
            "a": [1, 2, 3],
            "b": [10, 20, 30]
        }

        # Run calculation with Funz calculator (sequential - single calculator)
        print("\n=== Running sequential Funz calculation ===")
        results = fz.fzr(
            input_file,
            input_variables,
            model,
            calculators="funz://:5555/shell",  # Single calculator
            results_dir=working_dir / "results_seq"
        )

        print(f"\nResults: {results}")

        # Verify results
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        # Check that all calculations completed successfully
        for i, row in enumerate(results if hasattr(results, 'iterrows') else [results]):
            if hasattr(results, 'iterrows'):
                _, row = list(results.iterrows())[i]

            assert row.get('status') == 'done', f"Case {i} failed: {row.get('error')}"

            # Verify calculation results (a + b)
            a_val = row['a']
            b_val = row['b']
            expected_result = a_val + b_val
            actual_result = float(row['result'])

            assert actual_result == expected_result, \
                f"Case {i}: Expected {expected_result}, got {actual_result}"

        print("✓ Sequential Funz calculation test passed")


def test_funz_parallel_calculation():
    """
    Test parallel execution with multiple Funz calculators

    Uses 3 calculators in parallel to run 9 cases
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Create input template
        input_file = working_dir / "input.txt"
        input_file.write_text("""# Parallel calculation input
x=$x
y=$y
""")

        # Create calculation script with a small delay to simulate work
        calc_script = working_dir / "calc.sh"
        calc_script.write_text("""#!/bin/bash
# Read input
source input.txt

# Simulate some work
sleep 1

# Calculate result (x * y)
result=$(echo "$x * $y" | bc)

# Write output
echo "product = $result" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "product": "grep 'product = ' output.txt | awk '{print $3}'"
            }
        }

        # Define input variables for 9 cases (3x3)
        input_variables = {
            "x": [1, 2, 3],
            "y": [10, 100, 1000]
        }

        # Run calculation with 3 Funz calculators in parallel
        print("\n=== Running parallel Funz calculation (3 calculators) ===")
        start_time = time.time()

        results = fz.fzr(
            input_file,
            input_variables,
            model,
            calculators=[
                "funz://:5555/shell",
                "funz://:5556/shell",
                "funz://:5557/shell"
            ],
            results_dir=working_dir / "results_parallel"
        )

        elapsed_time = time.time() - start_time

        print(f"\nResults: {results}")
        print(f"Elapsed time: {elapsed_time:.2f}s")

        # Verify results
        assert len(results) == 9, f"Expected 9 results, got {len(results)}"

        # Check that all calculations completed successfully
        for i, row in enumerate(results if hasattr(results, 'iterrows') else [results]):
            if hasattr(results, 'iterrows'):
                _, row = list(results.iterrows())[i]

            assert row.get('status') == 'done', f"Case {i} failed: {row.get('error')}"

            # Verify calculation results (x * y)
            x_val = row['x']
            y_val = row['y']
            expected_result = x_val * y_val
            actual_result = float(row['product'])

            assert actual_result == expected_result, \
                f"Case {i}: Expected {expected_result}, got {actual_result}"

        # Verify parallel execution was faster than sequential would be
        # With 9 cases taking ~1s each, sequential would take ~9s
        # With 3 parallel calculators, should take ~3s (9 cases / 3 calculators)
        # Allow some overhead, so max 6s
        assert elapsed_time < 6, \
            f"Parallel execution took {elapsed_time:.2f}s, expected < 6s"

        print(f"✓ Parallel Funz calculation test passed ({elapsed_time:.2f}s for 9 cases)")


def test_funz_error_handling():
    """
    Test that Funz calculator handles errors gracefully
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Create input template
        input_file = working_dir / "input.txt"
        input_file.write_text("value=$value\n")

        # Create a script that will fail
        calc_script = working_dir / "calc.sh"
        calc_script.write_text("""#!/bin/bash
# This script always fails
exit 1
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "result": "grep 'result' output.txt | awk '{print $3}'"
            }
        }

        # Define input variables
        input_variables = {
            "value": [1]
        }

        # Run calculation - should fail gracefully
        print("\n=== Testing Funz error handling ===")
        results = fz.fzr(
            input_file,
            input_variables,
            model,
            calculators="funz://:5555/shell",
            results_dir=working_dir / "results_error"
        )

        print(f"\nResults: {results}")

        # Verify that error was captured
        if hasattr(results, 'iloc'):
            result_row = results.iloc[0]
        else:
            result_row = results

        # Should have failed status
        assert result_row.get('status') in ['failed', 'error'], \
            f"Expected failed/error status, got {result_row.get('status')}"

        print("✓ Funz error handling test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
