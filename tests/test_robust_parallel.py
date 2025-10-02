#!/usr/bin/env python3
"""
Test robust parallel execution with file synchronization
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

def setup_robust_test():
    """Setup test with robust file handling"""
    # Create input.txt
    input_content = """T_celsius=$T_celsius
V_L=$V_L
n_mol=$n_mol
"""
    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create a very robust calculator script with explicit file synchronization
    script_content = """#!/bin/bash
set -e  # Exit on any error

# read input file
source "$1"

echo "Calculator PID $$ starting for T_celsius=$T_celsius at $(date +%H:%M:%S.%3N)" >> calc.log

# Simulate calculation time
sleep 2

# Calculate pressure using ideal gas law
pressure=$(echo "scale=4; $n_mol * 8.314 * ($T_celsius + 273.15) / ($V_L / 1000)" | bc -l)

# Write output with explicit file operations and sync
echo "pressure = $pressure" > output.txt
sync  # Force write to disk

# Write additional debugging info
echo "Calculator PID $$ finished for T_celsius=$T_celsius at $(date +%H:%M:%S.%3N)" >> calc.log
echo "SUCCESS" > status.txt
sync  # Force write to disk

echo 'Done'
"""
    with open("RobustCalc.py", "w") as f:
        f.write(script_content)
    os.chmod("RobustCalc.py", 0o755)

def test_robust_parallel():
    """Test robust parallel execution"""
    setup_robust_test()

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
        "python ./RobustCalc.py",
        "python ./RobustCalc.py"
    ]

    try:
        print("🧪 Testing Robust Parallel Execution:")
        print("   - 2 calculators with explicit file sync")
        print("   - 2 cases (T_celsius=[20,25])")
        print("   - Requirement: ALL cases must succeed")
        print()

        start_time = time.time()

        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators=calculators,
                       resultsdir="results")

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Execution completed in {total_time:.2f} seconds")

        # Check calculation log
        if os.path.exists("calc.log"):
            print(f"\n📝 Calculator Log:")
            with open("calc.log", "r") as f:
                for line in f:
                    print(f"   {line.strip()}")

        # Analyze results
        if result and "pressure" in result:
            pressure_values = result["pressure"]
            successful_cases = len([p for p in pressure_values if p is not None])

            print(f"\n📊 Results:")
            print(f"   Total cases: {len(variables['T_celsius'])}")
            print(f"   Successful cases: {successful_cases}")
            print(f"   Failed cases: {len(variables['T_celsius']) - successful_cases}")

            for i, temp in enumerate(result["T_celsius"]):
                pressure = pressure_values[i] if i < len(pressure_values) else None
                status = "✅" if pressure is not None else "❌"
                print(f"     Case {i}: T_celsius={temp} → pressure={pressure} {status}")

            # Check result directories for debugging
            print(f"\n📁 Result Directories:")
            if os.path.exists("results"):
                for case_dir in os.listdir("results"):
                    case_path = Path("results") / case_dir
                    if case_path.is_dir():
                        files = list(case_path.iterdir())
                        file_names = [f.name for f in files]
                        print(f"   {case_dir}: {file_names}")

                        # Check if output.txt exists and its content
                        output_file = case_path / "output.txt"
                        if output_file.exists():
                            content = output_file.read_text().strip()
                            print(f"     output.txt: '{content}'")
                        else:
                            print(f"     output.txt: MISSING")

            # Timing check
            if total_time <= 3.0:
                print(f"\n⏱️ Timing: ✅ Parallel execution confirmed ({total_time:.2f}s ≤ 3s)")
                timing_ok = True
            else:
                print(f"\n⏱️ Timing: ⚠️ Slow execution ({total_time:.2f}s > 3s)")
                timing_ok = False

            # Success criteria
            all_successful = (successful_cases == len(variables['T_celsius']))

            print(f"\n🎯 Final Result:")
            print(f"   All cases successful: {'✅' if all_successful else '❌'}")
            print(f"   Parallel timing: {'✅' if timing_ok else '❌'}")

            return all_successful and timing_ok
        else:
            print("❌ No results returned")
            return False

    except Exception as e:
        print(f"❌ Robust parallel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        for f in ["input.txt", "RobustCalc.py", "calc.log"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working in: {temp_dir}\n")
        success = test_robust_parallel()
        print(f"\n{'🎉 SUCCESS' if success else '💥 FAILED'}: Robust parallel execution test!")