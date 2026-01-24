"""
Example demonstrating static object definitions (constants and functions) in fzi

This example shows how fzi now:
- Parses static object definitions using #@: syntax
- Evaluates constants and functions before formulas
- Includes them in the returned dictionary
- Makes them available for use in formulas
"""
import tempfile
from pathlib import Path
from fz import fzi
import json


def example_with_constants():
    """Demonstrate fzi with constant definitions"""

    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    input_template = """# Perfect Gas Law with Constants

# Static object definitions (constants)
#@: R = 8.314  # Gas constant (J/(mol*K))
#@: Navo = 6.022e23  # Avogadro's number

# Variables with default values
Temperature (Celsius): $(T_celsius~20)
Volume (Liters): $(V_L~1.0)
Moles: $(n_mol~0.041)

# Formulas using constants and variables
Temperature (Kelvin): @{$T_celsius + 273.15}
Volume (m³): @{$V_L / 1000}
Pressure (Pa): @{$n_mol * R * ($T_celsius + 273.15) / ($V_L / 1000)}
Molecules: @{$n_mol * Navo}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("=" * 70)
        print("FZI with Constant Definitions Example")
        print("=" * 70)

        result = fzi(str(input_file), model=model)

        print("\n1. Static Objects (Constants):")
        print("-" * 70)
        for key, value in result.items():
            if not key.startswith("$") and not key.startswith("@") and not key.startswith("T_") and not key.startswith("V_") and not key.startswith("n_"):
                print(f"   {key} = {value}")

        print("\n2. Variables:")
        print("-" * 70)
        for key, value in result.items():
            if key.startswith("T_") or key.startswith("V_") or key.startswith("n_"):
                print(f"   {key} = {value}")

        print("\n3. Formulas (evaluated with constants):")
        print("-" * 70)
        for key, value in result.items():
            if key.startswith("@"):
                print(f"   {key} = {value}")

        print("\n" + "=" * 70)


def example_with_functions():
    """Demonstrate fzi with function definitions"""

    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    input_template = """# Material Density Calculator

# Static objects: constants and functions
#@: L_x = 0.9  # Reference length
#@:
#@: def density(length, mass):
#@:     '''Calculate density based on length and mass'''
#@:     if length < 0:
#@:         return mass / (L_x + length**2)
#@:     else:
#@:         return mass / length**3
#@:
#@: def classify_density(d):
#@:     '''Classify material by density'''
#@:     if d < 1:
#@:         return "light"
#@:     elif d < 5:
#@:         return "medium"
#@:     else:
#@:         return "heavy"

# Variables with defaults
Length (m): $(length~1.2)
Mass (kg): $(mass~0.2)

# Formulas using functions
Density: @{density($length, $mass)}
Classification: @{classify_density(density($length, $mass))}
Negative Length Density: @{density(-1, $mass)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("\n" + "=" * 70)
        print("FZI with Function Definitions Example")
        print("=" * 70)

        result = fzi(str(input_file), model=model)

        print("\n1. Static Objects:")
        print("-" * 70)
        print(f"   L_x (constant) = {result.get('L_x')}")
        print(f"   density (function) = {result.get('density')}")
        print(f"   classify_density (function) = {result.get('classify_density')}")

        print("\n2. Variables:")
        print("-" * 70)
        print(f"   length = {result.get('length')}")
        print(f"   mass = {result.get('mass')}")

        print("\n3. Formulas (using functions):")
        print("-" * 70)
        for key, value in result.items():
            if key.startswith("@"):
                print(f"   {key} = {value}")

        print("\n" + "=" * 70)


def example_java_funz_compatibility():
    """Example matching Java Funz ParameterizingInputFiles.md"""

    model = {
        "var_prefix": "$",
        "var_delim": "()",
        "formula_prefix": "@",
        "formula_delim": "{}",
        "commentline": "#",
        "interpreter": "python",
    }

    input_template = """# Example from Java Funz documentation

# First variable: $(var1~1.2;"length in cm")
# Second variable: $(var2~0.2;"mass in g")

# Declare constants
#@: L_x = 0.9

# Declare functions
#@: def density(l, m):
#@:     if l < 0:
#@:         return m / (L_x + l**2)
#@:     else:
#@:         return m / l**3

# Unit tests (these are ignored by fzi)
#@? density(1, 1) == 1
#@? density(1, 0.2) == 0.2

# Use function in formulas
Result1: @{density($var1, $var2)}
Result2: @{density(-1, $var2)}
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        print("\n" + "=" * 70)
        print("Java Funz Compatibility Example")
        print("=" * 70)

        result = fzi(str(input_file), model=model)

        print("\nComplete result dictionary:")
        print("-" * 70)
        print(json.dumps({k: str(v) if callable(v) else v for k, v in result.items()}, indent=2))

        print("\n" + "=" * 70)
        print("Key Features:")
        print("=" * 70)
        print("✓ Constants defined with #@: syntax")
        print("✓ Functions defined with multi-line #@: blocks")
        print("✓ Unit tests #@? are properly ignored")
        print("✓ Functions and constants available in formulas")
        print("✓ All objects included in fzi result dictionary")
        print("=" * 70)


if __name__ == "__main__":
    example_with_constants()
    example_with_functions()
    example_java_funz_compatibility()
