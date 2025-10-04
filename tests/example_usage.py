#!/usr/bin/env python3
"""
Example usage of the fz package demonstrating the full workflow
"""
import fz
import tempfile
import json
from pathlib import Path


def main():
    """Demonstrate fz package usage"""
    print("FZ Package Example Usage")
    print("=" * 40)

    # Define a simple model
    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {
            "result": "echo 'The result is: $calculated_value'"
        }
    }

    # Create a temporary directory for our example
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create an input file with variables and formulas
        input_file = temp_path / "input.txt"
        input_file.write_text("""
# Example input file for calculation
base_value = $base
multiplier = $mult
#@ def calculate(base, mult):
#@     return base * mult + 10
calculated_value = @(calculate($base, $mult))
""")

        print(f"1. Created input file: {input_file.name}")
        print(f"   Content: {input_file.read_text().strip()}")
        print()

        # Step 1: Parse variables
        print("2. Parsing variables with fzi...")
        variables = fz.fzi(str(input_file), model)
        print(f"   Found variables: {json.dumps(variables, indent=2)}")
        print()

        # Step 2: Compile for single values
        print("3. Compiling input with fzc (single values)...")
        single_values = {"base": 5, "mult": 3}
        output_dir = temp_path / "compiled_single"

        # Set the formula engine (uses python by default)
        fz.set_engine("python")
        fz.fzc(str(input_file), model, single_values,
               output_dir=str(output_dir))

        compiled_content = (output_dir / "input.txt").read_text()
        print(f"   Compiled content:")
        print(f"   {compiled_content.strip()}")
        print()

        # Step 3: Compile for multiple values (parametric study)
        print("4. Compiling input with fzc (multiple values)...")
        multi_values = {"base": [2, 4, 6], "mult": [1, 2]}
        output_multi_dir = temp_path / "compiled_multi"

        fz.fzc(str(input_file), model, multi_values,
               output_dir=str(output_multi_dir))

        print(f"   Created {len(list(output_multi_dir.iterdir()))} combinations:")
        for combo_dir in sorted(output_multi_dir.iterdir()):
            if combo_dir.is_dir():
                print(f"   - {combo_dir.name}")
        print()

        # Step 4: Parse output (mock)
        print("5. Parsing output with fzo...")
        mock_output = temp_path / "output.txt"
        mock_output.write_text("The result is: 25")

        results = fz.fzo(str(temp_path), model)
        print(f"   Parsed results: {json.dumps(results, indent=2)}")
        print()

        # Step 5: Full workflow with fzr
        print("6. Running full calculation with fzr...")
        try:
            # Create a simple mock calculator that just echoes
            results_all = fz.fzr(
                str(input_file), model, {"base": [1, 2], "mult": [3, 4]},
                results_dir=str(temp_path / "results"),
                calculators=["sh://echo 'The result is: calculated'"]
            )

            print(f"   Full results structure:")
            for key, values in results_all.items():
                print(f"   - {key}: {values}")
        except Exception as e:
            print(f"   Note: Full calculation failed (expected): {e}")
        print()

        print("Example completed successfully!")
        print("\nThe fz package provides four main functions:")
        print("- fzi: Parse input files to find variables")
        print("- fzc: Compile input files with variable values")
        print("- fzo: Parse output files according to model specification")
        print("- fzr: Run full parametric calculations with remote execution")
        print("\nSee claude.md for detailed specifications and more examples.")


if __name__ == "__main__":
    main()