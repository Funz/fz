#!/usr/bin/env python3
"""
Debug execution to understand why one case fails
"""

import os
import sys
import tempfile
import shutil
import time
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import fz

def setup_debug_test():
    """Setup test with detailed debugging"""
    # Create input.txt
    input_content = """T_celsius=$T_celsius
V_L=$V_L
n_mol=$n_mol
"""
    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create a calculator script with extensive debugging
    script_content = """#!/bin/bash
set -e  # Exit on any error

echo "=== DEBUG: Script starting ===" >&2
echo "PWD: $(pwd)" >&2
echo "Args: $@" >&2
echo "Input file: $1" >&2

# read input file
echo "=== DEBUG: Sourcing input file ===" >&2
source "$1"

echo "=== DEBUG: Variables loaded ===" >&2
echo "T_celsius=$T_celsius" >&2
echo "V_L=$V_L" >&2
echo "n_mol=$n_mol" >&2

echo "=== DEBUG: Starting calculation ===" >&2
sleep 1

echo "=== DEBUG: Calculating pressure ===" >&2
# Calculate pressure using ideal gas law
pressure=$(echo "scale=4; $n_mol * 8.314 * ($T_celsius + 273.15) / ($V_L / 1000)" | bc -l)
echo "Calculated pressure: $pressure" >&2

echo "=== DEBUG: Writing output ===" >&2
echo "pressure = $pressure" > output.txt

echo "=== DEBUG: Syncing files ===" >&2
sync

echo "=== DEBUG: Verifying output file ===" >&2
if [ -f output.txt ]; then
    echo "output.txt exists, content:" >&2
    cat output.txt >&2
else
    echo "ERROR: output.txt does not exist!" >&2
    exit 1
fi

echo "=== DEBUG: Script completed successfully ===" >&2
echo 'Done'
"""
    with open("DebugCalc.sh", "w") as f:
        f.write(script_content)
    os.chmod("DebugCalc.sh", 0o755)

def test_debug_execution():
    """Test with debugging to see what fails"""
    setup_debug_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | cut -d'=' -f2 | tr -d ' '"}
    }

    # 2 calculators, 2 cases
    variables = {
        "T_celsius": [20, 25],
        "V_L": 1,
        "n_mol": 1
    }

    calculators = [
        "sh://bash ./DebugCalc.sh",
        "sh://bash ./DebugCalc.sh"
    ]

    try:
        print("🧪 Debug Execution Test:")
        print("   - 2 calculators with extensive debugging")
        print("   - 2 cases (T_celsius=[20,25])")
        print()

        start_time = time.time()

        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators=calculators,
                       results_dir="results")

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Execution completed in {total_time:.2f} seconds")

        # Analyze results and debug info
        if result and "pressure" in result:
            pressure_values = result["pressure"]
            successful_cases = len([p for p in pressure_values if p is not None])

            print(f"\n📊 Results:")
            for i, temp in enumerate(result["T_celsius"]):
                pressure = pressure_values[i] if i < len(pressure_values) else None
                status = "✅" if pressure is not None else "❌"
                print(f"     Case {i}: T_celsius={temp} → pressure={pressure} {status}")

            # Check result directories and debug files
            print(f"\n📁 Debug Information:")
            if os.path.exists("results"):
                for case_dir in sorted(os.listdir("results")):
                    case_path = Path("results") / case_dir
                    if case_path.is_dir():
                        print(f"\n   📂 {case_dir}:")

                        # List all files
                        files = list(case_path.iterdir())
                        file_names = [f.name for f in files]
                        print(f"     Files: {file_names}")

                        # Check stderr (err.txt) for debug info
                        err_file = case_path / "err.txt"
                        if err_file.exists():
                            print(f"     🔍 stderr content:")
                            try:
                                content = err_file.read_text()
                                for line in content.split('\n'):
                                    if line.strip():
                                        print(f"       {line}")
                            except Exception as e:
                                print(f"       Error reading stderr: {e}")

                        # Check stdout (out.txt)
                        out_file = case_path / "out.txt"
                        if out_file.exists():
                            print(f"     📝 stdout content:")
                            try:
                                content = out_file.read_text()
                                if content.strip():
                                    for line in content.split('\n'):
                                        if line.strip():
                                            print(f"       {line}")
                                else:
                                    print(f"       (empty)")
                            except Exception as e:
                                print(f"       Error reading stdout: {e}")

                        # Check output.txt
                        output_file = case_path / "output.txt"
                        if output_file.exists():
                            content = output_file.read_text().strip()
                            print(f"     ✅ output.txt: '{content}'")
                        else:
                            print(f"     ❌ output.txt: MISSING")

            return successful_cases == len(variables['T_celsius'])
        else:
            print("❌ No results returned")
            return False

    except Exception as e:
        print(f"❌ Debug execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        for f in ["input.txt", "DebugCalc.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working in: {temp_dir}\n")
        success = test_debug_execution()
        print(f"\n{'🎉 SUCCESS' if success else '💥 FAILED'}: Debug execution test!")