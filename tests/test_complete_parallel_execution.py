#!/usr/bin/env python3
"""
Test complete parallel execution with all cases returning results
Diagnose and fix any post-processing issues
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

def setup_complete_test():
    """Setup test for complete parallel execution"""
    # Create input.txt
    input_content = """T_celsius=$T_celsius
V_L=$V_L
n_mol=$n_mol
"""
    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create a more robust calculator script
    script_content = """#!/bin/bash
set -e  # Exit on any error

# read input file
source $1

echo "Calculator starting for T_celsius=$T_celsius at $(date +%H:%M:%S.%3N)"

# Simulate calculation time
sleep 2

# Calculate pressure using ideal gas law: P = nRT/V
# R = 8.314 J/(mol·K), T in Kelvin, V in m³, P in Pa
pressure=$(echo "scale=4; $n_mol * 8.314 * ($T_celsius + 273.15) / ($V_L / 1000)" | bc)

# Write output
echo "pressure = $pressure" > output.txt

# Write additional output files for debugging
echo "Calculation completed successfully" > status.txt
echo "T_celsius=$T_celsius" > debug.txt
echo "V_L=$V_L" >> debug.txt
echo "n_mol=$n_mol" >> debug.txt
echo "pressure=$pressure" >> debug.txt

echo "Calculator finished for T_celsius=$T_celsius at $(date +%H:%M:%S.%3N)"
echo 'Done'
"""
    with open("PerfectGazPressure.sh", "w") as f:
        f.write(script_content)
    os.chmod("PerfectGazPressure.sh", 0o755)

def test_complete_parallel_execution():
    """Test that all cases complete successfully with results"""
    setup_complete_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    # 2 calculators, 2 cases - should run in ~2s parallel vs ~4s sequential
    variables = {
        "T_celsius": [20, 25],
        "V_L": 1,
        "n_mol": 1
    }

    calculators = [
        "sh://bash ./PerfectGazPressure.sh",
        "sh://bash ./PerfectGazPressure.sh"
    ]

    try:
        print("🧪 Testing Complete Parallel Execution:")
        print("   - 2 calculators (duplicate URIs)")
        print("   - 2 cases (T_celsius=[20,25])")
        print("   - Each calculation takes ~2 seconds")
        print("   - Expected: ~2s parallel vs ~4s sequential")
        print("   - Requirement: ALL cases must succeed with results")
        print()

        start_time = time.time()

        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators=calculators,
                       resultsdir="results")

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Execution completed in {total_time:.2f} seconds")

        # Detailed result analysis
        if result:
            print(f"\n📊 Results Analysis:")
            print(f"   Result keys: {list(result.keys())}")

            if "pressure" in result:
                pressure_values = result["pressure"]
                print(f"   Pressure values: {pressure_values}")

                successful_cases = len([p for p in pressure_values if p is not None])
                failed_cases = len([p for p in pressure_values if p is None])

                print(f"   Successful cases: {successful_cases}/{len(variables['T_celsius'])}")
                print(f"   Failed cases: {failed_cases}")

                # Check individual case details
                if "T_celsius" in result:
                    for i, temp in enumerate(result["T_celsius"]):
                        pressure = pressure_values[i] if i < len(pressure_values) else None
                        status = "✅ SUCCESS" if pressure is not None else "❌ FAILED"
                        print(f"     Case {i}: T_celsius={temp} → pressure={pressure} {status}")

                # Verify timing
                print(f"\n⏱️ Timing Analysis:")
                print(f"   Actual time: {total_time:.2f}s")
                print(f"   Expected parallel: ~2s")
                print(f"   Expected sequential: ~4s")

                if total_time <= 3.0:
                    print(f"   ✅ PARALLEL execution confirmed ({total_time:.2f}s ≤ 3s)")
                    timing_success = True
                else:
                    print(f"   ⚠️ Possible sequential execution ({total_time:.2f}s > 3s)")
                    timing_success = False

                # Check result directories
                print(f"\n📁 Result Directory Analysis:")
                if os.path.exists("results"):
                    for item in os.listdir("results"):
                        item_path = os.path.join("results", item)
                        if os.path.isdir(item_path):
                            files = os.listdir(item_path)
                            print(f"   {item}/: {files}")

                # Overall success criteria
                all_cases_successful = (successful_cases == len(variables['T_celsius']))

                print(f"\n🎯 Success Criteria:")
                print(f"   All cases successful: {'✅' if all_cases_successful else '❌'}")
                print(f"   Parallel timing: {'✅' if timing_success else '❌'}")

                return all_cases_successful and timing_success

            else:
                print("   ❌ No pressure results found")
                return False
        else:
            print("   ❌ No results returned")
            return False

    except Exception as e:
        print(f"❌ Complete parallel execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working in: {temp_dir}\n")
        success = test_complete_parallel_execution()
        print(f"\n{'🎉 SUCCESS' if success else '💥 FAILED'}: Complete parallel execution test!")