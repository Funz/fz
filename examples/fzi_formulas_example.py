"""
Example demonstrating fzi formula parsing and evaluation

This example shows how fzi now:
- Parses both variables and formulas
- Extracts default values from variables
- Computes formula values when all variables have defaults
"""
import tempfile
from pathlib import Path
from fz import fzi
import json


def example_fzi_with_formulas():
    """Demonstrate fzi with formulas and default values"""

    # Create a model
    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    # Create input template with variables and formulas
    input_template = """# Perfect Gas Law Example

# Variables with default values
Temperature (Celsius): $(T_celsius~20)
Volume (Liters): $(V_L~1.0)
Moles: $(n_mol~0.041)

# Constants
#@: R = 8.314  # Gas constant (J/(mol*K))

# Formulas with format specifiers
Temperature (Kelvin): @{$T_celsius + 273.15}
Volume (m³): @{$V_L / 1000 | 0.0000}
Pressure (Pa): @{$n_mol * R * ($T_celsius + 273.15) / ($V_L / 1000) | 0.00}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Write input file
        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("=" * 60)
        print("FZI Formula Parsing and Evaluation Example")
        print("=" * 60)

        # Parse variables and formulas
        result = fzi(str(input_file), model=model)

        print("\n1. Variables Found:")
        print("-" * 60)
        for key, value in result.items():
            # Variables are keys without @{...} syntax
            if not key.startswith("@"):
                if value is not None:
                    print(f"   {key} = {value}")
                else:
                    print(f"   {key} = (no default)")

        print("\n2. Formulas Found:")
        print("-" * 60)
        for key, value in result.items():
            # Formulas are keys with @{...} syntax
            if key.startswith("@"):
                if value is not None:
                    print(f"   {key} = {value}")
                else:
                    print(f"   {key} = (cannot evaluate)")

        print("\n3. JSON Output:")
        print("-" * 60)
        print(json.dumps(result, indent=2))

        print("\n" + "=" * 60)
        print("Key Features Demonstrated:")
        print("=" * 60)
        print("✓ Variables parsed with default values")
        print("✓ Formulas parsed from @{...} syntax")
        print("✓ Default values automatically extracted")
        print("✓ Formulas evaluated when all variables have defaults")
        print("✓ Format specifiers applied (| 0.00, | 0.0000)")
        print("=" * 60)


def example_fzi_without_defaults():
    """Show what happens when variables don't have defaults"""

    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    input_template = """# Variables without defaults
Length: $(x)
Width: $(y)

# Formulas (cannot be evaluated without variable values)
Area: @{$x * $y}
Perimeter: @{2 * ($x + $y)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("\n" + "=" * 60)
        print("FZI Without Default Values")
        print("=" * 60)

        result = fzi(str(input_file), model=model)

        print("\nVariables:")
        for key, value in result.items():
            if not key.startswith("@"):
                print(f"   {key} = {value}")

        print("\nFormulas (cannot be evaluated):")
        for key, value in result.items():
            if key.startswith("@"):
                print(f"   {key} = {value}")

        print("\nNote: Formulas return None when variables lack defaults")
        print("=" * 60)


def example_fzi_partial_defaults():
    """Show formulas with partial defaults"""

    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    input_template = """# Mixed: some variables with defaults, some without
Length: $(x~10)
Width: $(y)
Height: $(z~5)

# Formulas
X doubled: @{$x * 2}
Z squared: @{$z ** 2}
Volume: @{$x * $y * $z}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("\n" + "=" * 60)
        print("FZI With Partial Defaults")
        print("=" * 60)

        result = fzi(str(input_file), model=model)

        print("\nVariables:")
        for key, value in result.items():
            if not key.startswith("@"):
                status = f"{value}" if value is not None else "(no default)"
                print(f"   {key} = {status}")

        print("\nFormulas:")
        for key, value in result.items():
            if key.startswith("@"):
                if value is not None:
                    print(f"   {key} = {value} ✓")
                else:
                    print(f"   {key} = None (missing variable defaults)")

        print("\nNote: Formulas evaluate only when ALL referenced variables have defaults")
        print("=" * 60)


if __name__ == "__main__":
    example_fzi_with_formulas()
    example_fzi_without_defaults()
    example_fzi_partial_defaults()
