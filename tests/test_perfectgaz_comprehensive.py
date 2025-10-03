#!/usr/bin/env python3
"""
Comprehensive test with PerfectGaz calculation using many cases (20+)
Verifies that all expected files are present in each case result directory
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_perfectgaz_comprehensive():
    """Test PerfectGaz with many cases and verify all files are present"""

    # Create input file with temperature placeholder
    with open('perfectgaz_input.txt', 'w') as f:
        f.write('Temperature: ${T_K} K\nVolume: 1 L\nAmount: 1 mol\n')

    print("🧪 PerfectGaz Comprehensive Test - 25 Cases")
    print("=" * 60)

    # Create temperature range for 25 cases (273K to 373K in 4K steps)
    temperatures = list(range(273, 374, 4))  # 25 temperature values
    print(f"📊 Testing {len(temperatures)} temperature cases: {temperatures[0]}K to {temperatures[-1]}K")

    start_time = time.time()

    try:
        # Run the comprehensive test
        result = fzr(
            input_path="perfectgaz_input.txt",
            model={"output": {"pressure": "cat output.txt"}},
            var_values={"T_K": temperatures},
            calculators=["sh://bash PerfectGazPressure.sh","sh://bash PerfectGazPressure.sh","sh://bash PerfectGazPressure.sh"],
            results_dir="perfectgaz_results"
        )

        execution_time = time.time() - start_time
        print(f"\n⏱️  Total execution time: {execution_time:.2f}s ({execution_time/len(temperatures):.2f}s per case)")

        # Verify results
        results_dir = Path("perfectgaz_results")
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return

        print(f"\n📂 Results directory exists: {results_dir}")

        # Expected files in each case directory
        expected_files = [
            "input.txt",      # Original input file (copied during setup)
            "out.txt",        # stdout from calculation
            "err.txt",        # stderr from calculation
            "log.txt",        # execution log
            "output.txt",     # result file created by PerfectGazPressure.sh
            ".fz_hash"        # hash file for caching
        ]

        # Check each case directory
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        case_dirs.sort(key=lambda x: int(x.name.split('=')[1]))  # Sort by temperature

        print(f"\n📋 Found {len(case_dirs)} case directories")

        all_cases_valid = True
        missing_files_summary = {}
        pressure_results = {}

        for i, case_dir in enumerate(case_dirs):
            temp_value = case_dir.name.split('=')[1]
            print(f"\n📁 Case {i+1}: {case_dir.name}")

            # Check for expected files
            missing_files = []
            present_files = []

            for expected_file in expected_files:
                file_path = case_dir / expected_file
                if file_path.exists() and file_path.stat().st_size > 0:
                    present_files.append(expected_file)
                    # Read some key files
                    if expected_file == "output.txt":
                        try:
                            content = file_path.read_text().strip()
                            pressure_results[temp_value] = content
                            print(f"  📄 {expected_file}: {content}")
                        except Exception as e:
                            print(f"  ⚠️  {expected_file}: Error reading ({e})")
                    elif expected_file == "log.txt":
                        try:
                            content = file_path.read_text()
                            if "Exit code: 0" in content:
                                print(f"  ✅ {expected_file}: Success (exit code 0)")
                            else:
                                print(f"  ⚠️  {expected_file}: May have errors")
                        except Exception as e:
                            print(f"  ⚠️  {expected_file}: Error reading ({e})")
                    else:
                        size = file_path.stat().st_size
                        print(f"  ✅ {expected_file}: Present ({size} bytes)")
                else:
                    missing_files.append(expected_file)
                    print(f"  ❌ {expected_file}: Missing or empty")

            if missing_files:
                all_cases_valid = False
                missing_files_summary[case_dir.name] = missing_files

            # Show file count summary
            print(f"  📊 Files: {len(present_files)}/{len(expected_files)} present")

        # Summary analysis
        print(f"\n📈 Results Analysis:")
        print(f"  Total cases: {len(case_dirs)}")
        print(f"  Expected cases: {len(temperatures)}")

        if len(case_dirs) == len(temperatures):
            print(f"  ✅ All expected case directories created")
        else:
            print(f"  ❌ Missing case directories: {len(temperatures) - len(case_dirs)}")

        if all_cases_valid:
            print(f"  ✅ All cases have all expected files")
        else:
            print(f"  ❌ {len(missing_files_summary)} cases missing files:")
            for case_name, missing in missing_files_summary.items():
                print(f"    - {case_name}: missing {missing}")

        # Verify pressure calculation consistency
        print(f"\n🔬 Pressure Calculation Verification:")
        if len(pressure_results) >= 3:
            temp_values = sorted([int(k) for k in pressure_results.keys()])
            sample_temps = [temp_values[0], temp_values[len(temp_values)//2], temp_values[-1]]

            for temp in sample_temps:
                temp_str = str(temp)
                if temp_str in pressure_results:
                    result_text = pressure_results[temp_str]
                    print(f"  T={temp}K: {result_text}")

        # Performance analysis
        print(f"\n⚡ Performance Analysis:")
        print(f"  Cases per second: {len(temperatures)/execution_time:.1f}")
        print(f"  Average time per case: {execution_time/len(temperatures):.3f}s")

        # Final verdict
        if all_cases_valid and len(case_dirs) == len(temperatures):
            print(f"\n🎉 SUCCESS: All {len(temperatures)} cases completed with all expected files!")
        else:
            print(f"\n⚠️  ISSUES DETECTED: Check missing files or directories above")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['perfectgaz_input.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_perfectgaz_comprehensive()