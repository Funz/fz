"""
Example demonstrating Java Funz compatible syntax

This example shows how to use the original Java Funz syntax:
- Variables: $(var) with parentheses
- Formulas: @{expr} with braces
- Variable metadata: $(var~default;comment;bounds)
- Formula format: @{expr | 0.00}
- Function declarations: #@: func = ...
"""
import tempfile
from pathlib import Path
from fz import fzi, fzc, fzr


def example_java_funz_syntax():
    """Demonstrate Java Funz compatible syntax"""

    # Create a model with Java Funz syntax
    model = {
        "var_prefix": "$",
        "var_delim": "()",        # Variables use () like Java Funz
        "formula_prefix": "@",
        "formula_delim": "{}",    # Formulas use {} like Java Funz
        "commentline": "#",
        "interpreter": "python",
        "output": {
            "result": "grep 'result =' output.txt | cut -d'=' -f2"
        }
    }

    # Create input template using Java Funz syntax
    input_template = """# This is a Java Funz compatible input file

# Declare variables with default values and metadata
# Variable 1: $(x~1.2;"length in cm")
# Variable 2: $(y~0.5;"width in cm";{0.1,0.5,1.0})

# Declare constants
#@: PI = 3.14159
#@: conversion_factor = 10.0

# Declare functions
#@: def area(length, width):
#@:     return length * width * PI

# Unit tests (optional)
#@? area(1, 1) > 0
#@? conversion_factor == 10.0

# Use variables in input
length = $(x)
width = $(y)

# Use formulas with format specifiers
area_cm2 = @{area($x, $y) | 0.00}
area_mm2 = @{area($x, $y) * conversion_factor | 0.0000}

# Formula without format
perimeter = @{2 * ($x + $y)}
"""

    # Create calculator script
    calculator_script = """#!/bin/bash
# Simple calculator that processes the input
source input.txt 2>/dev/null || true

# Calculate result
result=$(echo "$length * $width" | python -c "import sys; print(eval(input()))")

# Write output
cat > output.txt << EOF
Input values:
  length = $length
  width = $width
  area_cm2 = $area_cm2
  area_mm2 = $area_mm2
  perimeter = $perimeter

Calculated:
  result = $result
EOF
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Write input template
        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_template)

        # Write calculator script
        calc_file = tmpdir / "calc.sh"
        with open(calc_file, 'w') as f:
            f.write(calculator_script)
        calc_file.chmod(0o755)

        print("=" * 60)
        print("Java Funz Syntax Compatibility Example")
        print("=" * 60)

        # Step 1: Parse variables
        print("\n1. Parsing variables from template...")
        variables = fzi(input_file, model=model)
        print(f"   Found variables: {list(variables.keys())}")

        # Step 2: Compile template
        print("\n2. Compiling template with values...")
        input_vars = {"x": 2.5, "y": 1.5}
        resultsdir = tmpdir / "results"
        fzc(input_file, model=model, input_variables=input_vars, output_dir=resultsdir)

        # Show compiled content
        # Find the actual compiled file (directory name varies)
        case_dirs = list(resultsdir.glob("*"))
        if case_dirs:
            compiled_file = case_dirs[0] / "input.txt"
            with open(compiled_file) as f:
                compiled = f.read()
            print(f"   Compiled to: {compiled_file}")
        print("\n   Key substitutions:")
        for line in compiled.split('\n'):
            if 'length =' in line or 'width =' in line or 'area_' in line or 'perimeter =' in line:
                print(f"     {line.strip()}")

        # Step 3: Run complete workflow
        print("\n3. Running complete workflow with fzr()...")
        calculator = f"sh://{calc_file}"
        results = fzr(
            input_file,
            model=model,
            input_variables=input_vars,
            calculators=calculator,
            results_dir=tmpdir / "fzr_results"
        )

        print(f"   Results: {results}")

        print("\n" + "=" * 60)
        print("Key Java Funz Syntax Features Demonstrated:")
        print("=" * 60)
        print("✓ Variables with (): $(x), $(y)")
        print("✓ Variable metadata: $(x~1.2;\"length in cm\")")
        print("✓ Formulas with {}: @{expression}")
        print("✓ Format specifiers: @{expr | 0.00}")
        print("✓ Function declarations: #@: def func()...")
        print("✓ Constants: #@: PI = 3.14159")
        print("✓ Unit tests: #@? assertion")
        print("=" * 60)


def example_backward_compatibility():
    """Show that old ${var} syntax still works"""

    # Old-style model
    model = {
        "varprefix": "$",
        "delim": "{}",  # Old default
        "formulaprefix": "@",
        "commentline": "#",
    }

    input_content = "Value: ${x}\nFormula: @{$x * 2}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.txt"
        with open(input_file, 'w') as f:
            f.write(input_content)

        print("\n" + "=" * 60)
        print("Backward Compatibility Example")
        print("=" * 60)
        print(f"Input: {input_content}")

        variables = fzi(input_file, model=model)
        print(f"Variables: {list(variables.keys())}")

        resultsdir = tmpdir / "results"
        fzc(input_file, model=model, input_variables={"x": 5}, output_dir=resultsdir)

        case_dirs = list(resultsdir.glob("*"))
        if case_dirs:
            compiled_file = case_dirs[0] / "input.txt"
            with open(compiled_file) as f:
                compiled = f.read()
            print(f"Compiled: {compiled}")
        print("✓ Old ${var} syntax still works!")
        print("=" * 60)


if __name__ == "__main__":
    example_java_funz_syntax()
    example_backward_compatibility()
