#!/usr/bin/env python
"""
Demonstration of interrupt handling (Ctrl+C) in fz

This script shows how fz gracefully handles user interrupts during
long-running calculations. Press Ctrl+C during execution to see the
graceful shutdown in action.

The script will:
1. Create a test calculation with multiple slow cases
2. Start execution
3. Allow you to interrupt with Ctrl+C
4. Show partial results and proper cleanup
"""

import tempfile
from pathlib import Path
from fz import fzr

def main():
    print("=" * 70)
    print("FZ INTERRUPT HANDLING DEMONSTRATION")
    print("=" * 70)
    print()
    print("This demo shows graceful handling of Ctrl+C interrupts.")
    print("The calculation will run 10 cases, each taking ~3 seconds.")
    print()
    print("Try pressing Ctrl+C during execution to see graceful shutdown!")
    print("(Press Ctrl+C twice to force quit)")
    print()
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create input directory and script
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create a script that takes a few seconds to run
        script = input_dir / "slow_calc.sh"
        script.write_text("""#!/bin/bash
# Simulate a slow calculation
echo "Starting calculation for case x=$x..."
sleep 3
echo "Result: $(($x * $x))" > output.txt
echo "Calculation complete for x=$x"
""")
        script.chmod(0o755)

        # Define the model
        model = {
            "varprefix": "$",
            "delim": "()",
            "output": {
                "result": "cat output.txt"
            }
        }

        # Define variable values (10 cases)
        var_values = {
            "x": list(range(1, 11))  # [1, 2, 3, ..., 10]
        }

        results_dir = tmp_path / "results"

        print("Starting calculations...")
        print(f"Cases to run: {len(var_values['x'])}")
        print(f"Estimated time: ~{len(var_values['x']) * 3} seconds")
        print()
        print("Press Ctrl+C at any time to gracefully stop...")
        print()

        # Run the calculation
        try:
            results = fzr(
                str(input_dir),
                model,
                var_values,
                results_dir=str(results_dir),
                calculators=["sh://"]
            )

            print()
            print("=" * 70)
            print("EXECUTION COMPLETED")
            print("=" * 70)
            print()
            print(f"Total cases completed: {len(results)}")
            print()
            print("Results:")
            for i, row in results.iterrows():
                status = row.get('status', 'unknown')
                x = row.get('x', '?')
                result = row.get('result', 'N/A')
                print(f"  Case x={x}: status={status}, result={result}")

        except KeyboardInterrupt:
            print()
            print("=" * 70)
            print("FORCE QUIT - Resources may not be cleaned up properly!")
            print("=" * 70)
            raise

        print()
        print(f"Results saved to: {results_dir}")
        print()

if __name__ == "__main__":
    main()
