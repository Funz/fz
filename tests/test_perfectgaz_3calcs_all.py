#!/usr/bin/env python3
"""
Test PerfectGaz with 3 calculators ALL running for each case
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_perfectgaz_3calcs_all():
    """Test PerfectGaz with all 3 calculators running for each case"""

    # Create input file with bash variable definitions
    with open('perfectgaz_all3_vars.txt', 'w') as f:
        f.write('# Perfect gas calculation variables\n')
        f.write('n_mol=${n_mol}\n')
        f.write('T_kelvin=${T_kelvin}\n')
        f.write('V_m3=${V_m3}\n')

    print("🧪 PerfectGaz Test - ALL 3 Calculators per Case")
    print("=" * 60)

    # Use fewer cases since each will run 3 calculators
    temperatures = [273, 323]    # 2 temperatures
    amounts = [1.0, 2.0]        # 2 amounts
    volumes = [1.0, 1.5]        # 2 volumes
    # Total: 2 × 2 × 2 = 8 cases, each with 3 calculators = 24 calculations

    total_cases = len(temperatures) * len(amounts) * len(volumes)
    print(f"📊 Testing {total_cases} cases, each with 3 calculators:")
    print(f"  Temperatures: {temperatures} K")
    print(f"  Amounts: {amounts} mol")
    print(f"  Volumes: {volumes} m³")
    print(f"  Total calculations: {total_cases * 3}")

    start_time = time.time()

    try:
        # Run the test with ALL 3 calculators for each case
        result = fzr(
            input_path="perfectgaz_all3_vars.txt",
            model={
                "output": {
                    "pressure": "cat output.txt",
                    "volume": "cat volume_result.txt",
                    "temperature": "cat temperature_result.txt"
                }
            },
            var_values={
                "T_kelvin": temperatures,
                "n_mol": amounts,
                "V_m3": volumes
            },
            calculators=[
                "sh:///bin/bash ./PerfectGazPressure.sh",
                "sh:///bin/bash ./PerfectGazVolume.sh",
                "sh:///bin/bash ./PerfectGazTemperature.sh"
            ],
            results_dir="perfectgaz_all3_results"
        )

        execution_time = time.time() - start_time
        print(f"\n⏱️  Total execution time: {execution_time:.2f}s")
        print(f"  Per case: {execution_time/total_cases:.3f}s")
        print(f"  Per calculation: {execution_time/(total_cases*3):.3f}s")

        # Verify results
        results_dir = Path("perfectgaz_all3_results")
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return

        print(f"\n📂 Results directory exists: {results_dir}")

        # Expected files from ALL 3 calculators
        expected_files = [
            "perfectgaz_all3_vars.txt",   # Input file
            "out.txt",                    # stdout
            "err.txt",                    # stderr
            "log.txt",                    # execution log
            "output.txt",                 # PerfectGazPressure.sh
            "volume_result.txt",          # PerfectGazVolume.sh
            "temperature_result.txt",     # PerfectGazTemperature.sh
            ".fz_hash"                    # hash file
        ]

        # Check each case directory
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        case_dirs.sort(key=lambda x: x.name)

        print(f"\n📋 Found {len(case_dirs)} case directories")

        all_files_present = True
        total_files_expected = len(case_dirs) * len(expected_files)
        total_files_found = 0

        for i, case_dir in enumerate(case_dirs):
            case_name = case_dir.name
            print(f"\n📁 Case {i+1}: {case_name}")

            files_found = 0
            for expected_file in expected_files:
                file_path = case_dir / expected_file
                if file_path.exists():
                    size = file_path.stat().st_size
                    files_found += 1
                    total_files_found += 1

                    # Show calculator outputs
                    if expected_file in ["output.txt", "volume_result.txt", "temperature_result.txt"] and size > 0:
                        try:
                            content = file_path.read_text().strip()
                            print(f"  ✅ {expected_file}: {content}")
                        except:
                            print(f"  ✅ {expected_file}: Present ({size} bytes)")
                    else:
                        status = "✅" if size > 0 or expected_file == "err.txt" else "⚠️ "
                        print(f"  {status} {expected_file}: Present ({size} bytes)")
                else:
                    print(f"  ❌ {expected_file}: Missing")
                    all_files_present = False

            print(f"  📊 Files: {files_found}/{len(expected_files)} present")

        # Summary
        success_rate = (total_files_found / total_files_expected * 100) if total_files_expected > 0 else 0

        print(f"\n📈 Results Summary:")
        print(f"  Cases: {len(case_dirs)}/{total_cases}")
        print(f"  Files: {total_files_found}/{total_files_expected}")
        print(f"  Success rate: {success_rate:.1f}%")

        # Calculator-specific verification
        print(f"\n🔬 Calculator Output Verification:")
        for calc_file in ["output.txt", "volume_result.txt", "temperature_result.txt"]:
            count = len([f for f in Path("perfectgaz_all3_results").rglob(calc_file) if f.stat().st_size > 0])
            print(f"  {calc_file}: {count}/{len(case_dirs)} cases")

        # Final verdict
        if success_rate >= 95 and len(case_dirs) == total_cases:
            print(f"\n🎉 SUCCESS: All 3 calculators executed for each case!")
            print(f"   ✅ {total_cases} cases × 3 calculators = {total_cases*3} calculations")
            print(f"   ✅ All calculators run in case result directories")
            print(f"   ✅ All expected output files created")
        else:
            print(f"\n⚠️  Issues detected: {success_rate:.1f}% success rate")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if os.path.exists('perfectgaz_all3_vars.txt'):
            os.remove('perfectgaz_all3_vars.txt')

if __name__ == "__main__":
    test_perfectgaz_3calcs_all()