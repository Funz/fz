#!/usr/bin/env python3
"""
Example: Using fzd for iterative design of experiments

This example demonstrates how to use fzd with different algorithms
to optimize a simple mathematical function.
"""

import fz
import tempfile
import shutil
from pathlib import Path


def create_simple_model():
    """
    Create a simple test model that computes x^2 + y^2

    This represents minimizing the distance from the origin.
    The minimum is at (0, 0) with value 0.
    """
    # Create temporary directory for inputs
    tmpdir = Path(tempfile.mkdtemp())

    # Create input directory
    input_dir = tmpdir / "input"
    input_dir.mkdir()

    # Create input file with variables
    input_file = input_dir / "input.txt"
    input_file.write_text("x = $x\ny = $y\n")

    # Define model (computes x^2 + y^2)
    model = {
        "varprefix": "$",
        "delim": "()",
        "run": "bash -c 'source input.txt && result=$(echo \"scale=6; $x * $x + $y * $y\" | bc) && echo \"result = $result\" > output.txt'",
        "output": {
            "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
        }
    }

    return tmpdir, input_dir, model


def example_randomsampling():
    """Example using random sampling"""
    print("="*60)
    print("Example 1: Random Sampling")
    print("="*60)

    tmpdir, input_dir, model = create_simple_model()

    try:
        # Path to randomsampling algorithm
        algo_path = str(Path(__file__).parent / "algorithms" / "randomsampling.py")

        # Run fzd with random sampling
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[-2;2]", "y": "[-2;2]"},
            model=model,
            output_expression="result",
            algorithm=algo_path,
            algorithm_options={"nvalues": 10, "seed": 42}
        )

        print(f"\nAlgorithm: {result['algorithm']}")
        print(f"Total evaluations: {result['total_evaluations']}")
        print(f"\n{result['summary']}")

        # Find best result
        valid_results = [
            (inp, out) for inp, out in zip(result['input_vars'], result['output_values'])
            if out is not None
        ]

        if valid_results:
            best_input, best_output = min(valid_results, key=lambda x: x[1])
            print(f"\nBest result found:")
            print(f"  Input: {best_input}")
            print(f"  Output: {best_output:.6f}")

    finally:
        shutil.rmtree(tmpdir)


def example_brent():
    """Example using Brent's method (1D optimization)"""
    print("\n" + "="*60)
    print("Example 2: Brent's Method (1D)")
    print("="*60)

    tmpdir, input_dir, model = create_simple_model()

    try:
        # Modify model to only use x (for 1D optimization)
        model["run"] = "bash -c 'source input.txt && result=$(echo \"scale=6; ($x - 0.7) * ($x - 0.7)\" | bc) && echo \"result = $result\" > output.txt'"

        # Path to brent algorithm
        algo_path = str(Path(__file__).parent / "algorithms" / "brent.py")

        # Run fzd with Brent's method
        # This will find the minimum of (x - 0.7)^2, which is at x = 0.7
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[0;2]"},
            model=model,
            output_expression="result",
            algorithm=algo_path,
            algorithm_options={"max_iter": 20, "tol": 1e-3}
        )

        print(f"\nAlgorithm: {result['algorithm']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Total evaluations: {result['total_evaluations']}")

        # Find best result
        valid_results = [
            (inp, out) for inp, out in zip(result['input_vars'], result['output_values'])
            if out is not None
        ]

        if valid_results:
            best_input, best_output = min(valid_results, key=lambda x: x[1])
            print(f"\nOptimal result:")
            print(f"  Input: x = {best_input['x']:.6f} (expected: 0.7)")
            print(f"  Output: {best_output:.6f} (expected: ~0.0)")

    finally:
        shutil.rmtree(tmpdir)


def example_bfgs():
    """Example using BFGS (multi-dimensional optimization)"""
    print("\n" + "="*60)
    print("Example 3: BFGS (Multi-dimensional)")
    print("="*60)

    tmpdir, input_dir, model = create_simple_model()

    try:
        # Path to bfgs algorithm
        algo_path = str(Path(__file__).parent / "algorithms" / "bfgs.py")

        # Run fzd with BFGS
        # This will find the minimum of x^2 + y^2, which is at (0, 0)
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[-2;2]", "y": "[-2;2]"},
            model=model,
            output_expression="result",
            algorithm=algo_path,
            algorithm_options={"max_iter": 20, "tol": 1e-4}
        )

        print(f"\nAlgorithm: {result['algorithm']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Total evaluations: {result['total_evaluations']}")

        # Find best result
        valid_results = [
            (inp, out) for inp, out in zip(result['input_vars'], result['output_values'])
            if out is not None
        ]

        if valid_results:
            best_input, best_output = min(valid_results, key=lambda x: x[1])
            print(f"\nOptimal result:")
            print(f"  Input: x = {best_input['x']:.6f}, y = {best_input['y']:.6f} (expected: 0.0, 0.0)")
            print(f"  Output: {best_output:.6f} (expected: ~0.0)")

    finally:
        shutil.rmtree(tmpdir)


def example_custom_expression():
    """Example with custom output expression"""
    print("\n" + "="*60)
    print("Example 4: Custom Output Expression")
    print("="*60)

    tmpdir, input_dir, model = create_simple_model()

    try:
        # Modify model to output two values
        model["run"] = "bash -c 'source input.txt && r1=$(echo \"scale=6; $x * $x\" | bc) && r2=$(echo \"scale=6; $y * $y\" | bc) && echo \"r1 = $r1\" > output.txt && echo \"r2 = $r2\" >> output.txt'"
        model["output"] = {
            "r1": "grep 'r1 = ' output.txt | cut -d '=' -f2 | tr -d ' '",
            "r2": "grep 'r2 = ' output.txt | cut -d '=' -f2 | tr -d ' '"
        }

        # Path to randomsampling algorithm
        algo_path = str(Path(__file__).parent / "algorithms" / "randomsampling.py")

        # Run fzd with custom expression that combines outputs
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[-2;2]", "y": "[-2;2]"},
            model=model,
            output_expression="r1 + r2 * 2",
            algorithm=algo_path,
            algorithm_options={"nvalues": 10, "seed": 42}
        )

        print(f"\nOutput expression: r1 + r2 * 2")
        print(f"Total evaluations: {result['total_evaluations']}")

        # Find best result
        valid_results = [
            (inp, out) for inp, out in zip(result['input_vars'], result['output_values'])
            if out is not None
        ]

        if valid_results:
            best_input, best_output = min(valid_results, key=lambda x: x[1])
            print(f"\nBest result:")
            print(f"  Input: {best_input}")
            print(f"  Output: {best_output:.6f}")

    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    # Check if bc is available
    import shutil as sh
    if sh.which("bc") is None:
        print("Error: 'bc' command not found. Please install bc to run these examples.")
        print("  On Debian/Ubuntu: sudo apt install bc")
        print("  On macOS: brew install bc")
        exit(1)

    print("\nfzd - Iterative Design of Experiments Examples")
    print("="*60)

    example_randomsampling()
    example_brent()
    example_bfgs()
    example_custom_expression()

    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
