#!/usr/bin/env python3
"""
Final test: 2 calculators, 2 cases, so should run in 5 seconds instead of 10 seconds if run sequentially
All cases should run well and return a result
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

def setup_final_test():
    """Setup the final specification test"""
    # Create input.txt exactly as in examples.md
    input_content = """T_celsius=$T_celsius
V_L=$V_L
n_mol=$n_mol
"""
    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create PerfectGazPressure.sh that takes exactly 5 seconds per calculation
    script_content = """#!/usr/bin/env python3
# read input file
source $1
sleep 5  # Exactly 5 seconds per calculation
echo 'pressure = '`echo "scale=4;$n_mol*8.314*($T_celsius+273.15)/($V_L/1000)" | bc` > output.txt
echo 'Done'
"""
    with open("PerfectGazPressure.py", "w") as f:
        f.write(script_content)
    os.chmod("PerfectGazPressure.py", 0o755)

def test_final_specification():
    """Test the final specification: 2 calculators, 2 cases, ~5s parallel vs ~10s sequential"""
    setup_final_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    # Exact specification: 2 calculators, 2 cases
    variables = {
        "T_celsius": [20, 25],
        "V_L": 1,
        "n_mol": 1
    }

    calculators = [
        "python ./PerfectGazPressure.py",
        "python ./PerfectGazPressure.py"
    ]

    try:
        print("🎯 FINAL SPECIFICATION TEST")
        print("=" * 50)
        print("📋 Requirements:")
        print("   ✓ 2 calculators (duplicate URIs)")
        print("   ✓ 2 cases (T_celsius=[20,25])")
        print("   ✓ Should run in ~5 seconds (parallel)")
        print("   ✓ Would run in ~10 seconds (sequential)")
        print("   ✓ ALL cases should succeed with results")
        print()

        start_time = time.time()

        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators=calculators,
                       resultsdir="results")

        end_time = time.time()
        total_time = end_time - start_time

        print(f"⏱️ EXECUTION TIME: {total_time:.2f} seconds")

        # Verify results
        success_count = 0
        all_results_valid = True

        if result and "pressure" in result:
            pressure_values = result["pressure"]
            print(f"\n📊 RESULTS:")

            for i, temp in enumerate(result["T_celsius"]):
                pressure = pressure_values[i] if i < len(pressure_values) else None
                if pressure is not None:
                    try:
                        pressure_float = float(pressure)
                        print(f"   ✅ Case {i}: T_celsius={temp}°C → pressure={pressure_float:.1f} Pa")
                        success_count += 1
                    except (ValueError, TypeError):
                        print(f"   ❌ Case {i}: T_celsius={temp}°C → pressure=INVALID ({pressure})")
                        all_results_valid = False
                else:
                    print(f"   ❌ Case {i}: T_celsius={temp}°C → pressure=FAILED")
                    all_results_valid = False

            print(f"\n📈 PERFORMANCE ANALYSIS:")
            print(f"   Execution time: {total_time:.2f}s")
            print(f"   Expected parallel: ~5.0s")
            print(f"   Expected sequential: ~10.0s")

            # Performance criteria
            timing_success = total_time <= 7.0  # Allow 2s variance for parallel
            if timing_success:
                speedup = 10.0 / total_time
                print(f"   ✅ PARALLEL execution confirmed")
                print(f"   🚀 Speedup: {speedup:.1f}x")
            else:
                print(f"   ❌ SEQUENTIAL execution detected")

            # Final assessment
            all_cases_successful = (success_count == len(variables['T_celsius']))

            print(f"\n🎯 FINAL ASSESSMENT:")
            print(f"   Cases successful: {success_count}/{len(variables['T_celsius'])} {'✅' if all_cases_successful else '❌'}")
            print(f"   Results valid: {'✅' if all_results_valid else '❌'}")
            print(f"   Timing correct: {'✅' if timing_success else '❌'}")

            overall_success = all_cases_successful and all_results_valid and timing_success

            if overall_success:
                print(f"\n🎉 SPECIFICATION FULLY SATISFIED!")
                print(f"   ✓ 2 calculators with duplicate URIs working independently")
                print(f"   ✓ 2 cases running in parallel")
                print(f"   ✓ ~{total_time:.1f}s execution (parallel) vs ~10s (sequential)")
                print(f"   ✓ All cases return valid pressure results")
            else:
                print(f"\n💥 SPECIFICATION NOT MET")

            return overall_success

        else:
            print("❌ No results returned at all")
            return False

    except Exception as e:
        print(f"❌ Final test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.py"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working directory: {temp_dir}\n")
        success = test_final_specification()
        print(f"\n{'🏆 SUCCESS' if success else '💥 FAILURE'}: Final specification test!")