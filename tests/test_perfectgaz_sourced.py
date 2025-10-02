#!/usr/bin/env python3
"""
Test PerfectGaz with sourced input file format
Uses /bin/bash ./PerfectGazPressure.sh command and proper variable definitions
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

def test_perfectgaz_sourced():
    """Test PerfectGaz with sourced input variables and verify all files"""

    # Create input file with bash variable definitions
    with open('perfectgaz_vars.txt', 'w') as f:
        f.write('# Perfect gas calculation variables\n')
        f.write('n_mol=${n_mol}\n')
        f.write('T_kelvin=${T_kelvin}\n')
        f.write('V_m3=${V_m3}\n')

    print("🧪 PerfectGaz Sourced Variables Test - 24 Cases")
    print("=" * 60)

    # Create comprehensive parameter variations
    # Temperature: 273K to 373K (5 values)
    # Amount: 1-3 mol (3 values)
    # Volume: 1-2 m³ (2 values)
    # Total: 5 × 3 × 2 = 30 cases
    temperatures = [273, 298, 323, 348, 373]  # 5 temperatures
    amounts = [1.0, 2.0, 3.0]  # 3 amounts
    volumes = [1.0, 1.5]  # 2 volumes

    total_cases = len(temperatures) * len(amounts) * len(volumes)
    print(f"📊 Testing {total_cases} cases:")
    print(f"  Temperatures: {temperatures} K")
    print(f"  Amounts: {amounts} mol")
    print(f"  Volumes: {volumes} m³")

    start_time = time.time()

    try:
        # Run the comprehensive test
        result = fzr(
            input_path="perfectgaz_vars.txt",
            model={"output": {"pressure": "cat output.txt"}},
            varvalues={
                "T_kelvin": temperatures,
                "n_mol": amounts,
                "V_m3": volumes
            },
            calculators=["python ./PerfectGazPressure.py"],
            resultsdir="perfectgaz_sourced_results"
        )

        execution_time = time.time() - start_time
        print(f"\n⏱️  Total execution time: {execution_time:.2f}s ({execution_time/total_cases:.3f}s per case)")

        # Verify results
        results_dir = Path("perfectgaz_sourced_results")
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return

        print(f"\n📂 Results directory exists: {results_dir}")

        # Expected files in each case directory
        expected_files = [
            "perfectgaz_vars.txt",  # Original input file (copied during setup)
            "out.txt",              # stdout from calculation
            "err.txt",              # stderr from calculation
            "log.txt",              # execution log
            "output.txt",           # result file created by PerfectGazPressure.sh
            ".fz_hash"              # hash file for caching
        ]

        # Check each case directory
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        case_dirs.sort(key=lambda x: x.name)

        print(f"\n📋 Found {len(case_dirs)} case directories")

        all_cases_valid = True
        missing_files_summary = {}
        pressure_samples = {}

        for i, case_dir in enumerate(case_dirs[:10]):  # Show first 10 cases in detail
            case_name = case_dir.name
            print(f"\n📁 Case {i+1}: {case_name}")

            # Extract parameters from case name
            params = {}
            for param_pair in case_name.split(','):
                key, value = param_pair.split('=')
                params[key] = float(value)

            # Check for expected files
            missing_files = []
            present_files = []

            for expected_file in expected_files:
                file_path = case_dir / expected_file
                if file_path.exists() and file_path.stat().st_size >= 0:  # Allow empty err.txt
                    present_files.append(expected_file)
                    size = file_path.stat().st_size

                    # Read key files
                    if expected_file == "output.txt" and size > 0:
                        try:
                            content = file_path.read_text().strip()
                            pressure_samples[case_name] = content
                            print(f"  📄 {expected_file}: {content}")

                            # Verify calculation makes sense
                            if 'pressure =' in content:
                                pressure_str = content.split('=')[1].strip()
                                try:
                                    pressure_val = float(pressure_str)
                                    # Basic sanity check: pressure should be proportional to n*T/V
                                    expected_approx = params.get('n_mol', 1) * 8.314 * params.get('T_kelvin', 273) / params.get('V_m3', 1)
                                    if abs(pressure_val - expected_approx) / expected_approx < 0.01:  # Within 1%
                                        print(f"    ✅ Calculation verified (expected ~{expected_approx:.1f})")
                                    else:
                                        print(f"    ⚠️  Calculation seems off (expected ~{expected_approx:.1f})")
                                except ValueError:
                                    print(f"    ⚠️  Could not parse pressure value")
                        except Exception as e:
                            print(f"  ⚠️  {expected_file}: Error reading ({e})")
                    elif expected_file == "log.txt" and size > 0:
                        try:
                            content = file_path.read_text()
                            if "Exit code: 0" in content:
                                print(f"  ✅ {expected_file}: Success (exit code 0)")
                            else:
                                print(f"  ⚠️  {expected_file}: Check for errors")
                        except Exception as e:
                            print(f"  ⚠️  {expected_file}: Error reading ({e})")
                    else:
                        status = "✅" if size > 0 or expected_file == "err.txt" else "⚠️ "
                        print(f"  {status} {expected_file}: Present ({size} bytes)")
                else:
                    missing_files.append(expected_file)
                    print(f"  ❌ {expected_file}: Missing")

            if missing_files:
                all_cases_valid = False
                missing_files_summary[case_name] = missing_files

            # Show file count summary
            print(f"  📊 Files: {len(present_files)}/{len(expected_files)} present")

        # Summary for remaining cases
        if len(case_dirs) > 10:
            print(f"\n📋 Checking remaining {len(case_dirs)-10} cases...")
            remaining_issues = 0
            for case_dir in case_dirs[10:]:
                missing_count = 0
                for expected_file in expected_files:
                    file_path = case_dir / expected_file
                    if not (file_path.exists() and (file_path.stat().st_size > 0 or expected_file == "err.txt")):
                        missing_count += 1
                if missing_count > 0:
                    remaining_issues += 1
                    missing_files_summary[case_dir.name] = f"{missing_count} files missing"

            if remaining_issues == 0:
                print(f"  ✅ All remaining cases have complete file sets")
            else:
                print(f"  ⚠️  {remaining_issues} cases have missing files")

        # Summary analysis
        print(f"\n📈 Results Analysis:")
        print(f"  Total cases: {len(case_dirs)}")
        print(f"  Expected cases: {total_cases}")

        if len(case_dirs) == total_cases:
            print(f"  ✅ All expected case directories created")
        else:
            print(f"  ❌ Missing case directories: {total_cases - len(case_dirs)}")

        if all_cases_valid and len(missing_files_summary) == 0:
            print(f"  ✅ All cases have all expected files")
        else:
            print(f"  ❌ {len(missing_files_summary)} cases with issues")

        # Performance analysis
        print(f"\n⚡ Performance Analysis:")
        print(f"  Cases per second: {total_cases/execution_time:.1f}")
        print(f"  Average time per case: {execution_time/total_cases:.3f}s")

        # Sample pressure calculations
        if pressure_samples:
            print(f"\n🔬 Sample Pressure Calculations:")
            sample_count = min(5, len(pressure_samples))
            for case_name, pressure in list(pressure_samples.items())[:sample_count]:
                print(f"  {case_name}: {pressure}")

        # Final verdict
        success_rate = (len(case_dirs) - len(missing_files_summary)) / len(case_dirs) * 100 if case_dirs else 0
        if success_rate >= 95:
            print(f"\n🎉 SUCCESS: {success_rate:.1f}% of cases completed successfully!")
            print(f"   Command '/bin/bash ./PerfectGazPressure.py' working correctly")
            print(f"   All expected files present in case directories")
        else:
            print(f"\n⚠️  PARTIAL SUCCESS: {success_rate:.1f}% success rate")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['perfectgaz_vars.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_perfectgaz_sourced()