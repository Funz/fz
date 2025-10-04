#!/usr/bin/env python3
"""
Test script to reproduce random case failures using the user's example
"""

import sys
import os
sys.path.insert(0, '/home/richet/Sync/Open/Funz/fz')

from fz import fzr
import time

def test_user_example():
    """Test the exact example provided by the user"""

    print("=" * 60)
    print("Testing user's example:")
    print('fz.fzr("input.txt",')
    print('{')
    print('    "varprefix": "$",')
    print('    "formulaprefix": "@",')
    print('    "delim": "()",')
    print('    "commentline": "#",')
    print('    "output": {"pressure": "grep \'pressure = \' output.txt | awk \'{print $3}\'"}')
    print('},')
    print('{')
    print('    "T_celsius": [20,30,40],')
    print('    "V_L": 1,')
    print('    "n_mol": 1')
    print('}, calculators=["sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results")')
    print("=" * 60)

    # Check if required files exist
    input_file = "input.txt"
    script_file = "./PerfectGazPressure.sh"

    if not os.path.exists(input_file):
        print(f"Creating dummy {input_file}")
        with open(input_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Test input file\n")
            f.write("# Temperature: $(T_celsius) celsius\n")
            f.write("# Volume: $(V_L) L\n")
            f.write("# Moles: $(n_mol) mol\n")
            f.write("echo 'Running calculation...'\n")

    if not os.path.exists(script_file):
        print(f"Creating dummy {script_file}")
        with open(script_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Perfect gas pressure calculation\n")
            f.write("# P = nRT/V\n")
            f.write("# R = 8.314 J/(mol·K)\n")
            f.write("echo 'Starting calculation...'\n")
            f.write("# Get temperature from input file if possible, or use default\n")
            f.write("T_K=293  # Default to 20°C = 293K\n")
            f.write("V=1      # 1 L\n")
            f.write("n=1      # 1 mol\n")
            f.write("R=8314   # 8.314 J/(mol·K) * 1000 for L·Pa units\n")
            f.write("P=$((n * R * T_K / V))\n")
            f.write("echo \"pressure = $P Pa\" > output.txt\n")
            f.write("echo 'Calculation completed'\n")
        os.chmod(script_file, 0o755)  # Make executable

    try:
        start_time = time.time()
        result = fzr("input.txt",
        {
            "T_celsius": [20,30,40],
            "V_L": 1,
            "n_mol": 1
        },
        {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "()",
            "commentline": "#",
            "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
        },
        calculators=["sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results")

        elapsed = time.time() - start_time
        print(f"\n🏁 Test completed in {elapsed:.2f}s")
        print(f"📊 Results summary:")
        print(f"   - Cases: {len(result['T_celsius'])}")
        print(f"   - Statuses: {result['status']}")
        print(f"   - Calculators: {result['calculator']}")
        print(f"   - Pressures: {result['pressure']}")

        # Check for failures
        failed_cases = [i for i, status in enumerate(result['status']) if status != 'done']
        if failed_cases:
            print(f"❌ {len(failed_cases)} cases failed: {failed_cases}")
            return False
        else:
            print(f"✅ All {len(result['status'])} cases succeeded")
            return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_multiple_tests(num_tests=5):
    """Run the test multiple times to catch intermittent failures"""
    print(f"🔄 Running {num_tests} iterations to check for random failures...")

    success_count = 0
    failure_count = 0

    for i in range(num_tests):
        print(f"\n{'='*60}")
        print(f"TEST ITERATION {i+1}/{num_tests}")
        print(f"{'='*60}")

        success = test_user_example()
        if success:
            success_count += 1
        else:
            failure_count += 1

        # Small delay between tests
        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"FINAL RESULTS AFTER {num_tests} TESTS")
    print(f"{'='*60}")
    print(f"✅ Successes: {success_count}/{num_tests} ({success_count/num_tests*100:.1f}%)")
    print(f"❌ Failures: {failure_count}/{num_tests} ({failure_count/num_tests*100:.1f}%)")

    if failure_count > 0:
        print(f"\n⚠️  RELIABILITY ISSUE DETECTED!")
        print(f"   {failure_count} out of {num_tests} tests failed randomly")
        print(f"   This confirms the user's report of intermittent failures")
    else:
        print(f"\n✅ NO RELIABILITY ISSUES DETECTED")
        print(f"   All {num_tests} tests passed consistently")

if __name__ == "__main__":
    run_multiple_tests(10)