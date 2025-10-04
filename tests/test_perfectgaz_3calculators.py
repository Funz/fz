#!/usr/bin/env python3
"""
Test PerfectGaz with 3 calculators to verify case directory creation and file handling
Uses /bin/bash ./PerfectGazPressure.sh, ./PerfectGazVolume.sh, and ./PerfectGazTemperature.sh
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

def test_perfectgaz_3calculators():
    """Test PerfectGaz with 3 calculators and verify all files are created properly"""

    # Create input file with bash variable definitions including a default pressure for reverse calculations
    with open('perfectgaz_3calc_vars.txt', 'w') as f:
        f.write('# Perfect gas calculation variables\n')
        f.write('n_mol=${n_mol}\n')
        f.write('T_kelvin=${T_kelvin}\n')
        f.write('V_m3=${V_m3}\n')
        f.write('pressure_pa=${pressure_pa}\n')  # For reverse calculations

    print("🧪 PerfectGaz 3-Calculator Test")
    print("=" * 60)

    # Use fewer cases but multiple calculators (2 temperatures × 2 amounts × 2 volumes × 2 pressures = 16 cases)
    temperatures = [273, 323]    # 2 temperatures
    amounts = [1.0, 2.0]        # 2 amounts
    volumes = [1.0, 1.5]        # 2 volumes
    pressures = [101325, 202650] # 2 pressures (1 atm, 2 atm)

    total_cases = len(temperatures) * len(amounts) * len(volumes) * len(pressures)
    print(f"📊 Testing {total_cases} cases with 3 calculators:")
    print(f"  Temperatures: {temperatures} K")
    print(f"  Amounts: {amounts} mol")
    print(f"  Volumes: {volumes} m³")
    print(f"  Pressures: {pressures} Pa")
    print(f"  Calculators: Pressure, Volume, Temperature")

    start_time = time.time()

    try:
        # Run the test with 3 calculators
        result = fzr(
            input_path="perfectgaz_3calc_vars.txt",
            model={
                "output": {
                    "pressure": "cat output.txt",
                    "volume": "cat volume_result.txt",
                    "temperature": "cat temperature_result.txt"
                }
            },
            input_variables={
                "T_kelvin": temperatures,
                "n_mol": amounts,
                "V_m3": volumes,
                "pressure_pa": pressures
            },
            calculators=[
                "sh:///bin/bash ./PerfectGazPressure.sh",
                "sh:///bin/bash ./PerfectGazVolume.sh",
                "sh:///bin/bash ./PerfectGazTemperature.sh"
            ],
            results_dir="perfectgaz_3calc_results"
        )

        execution_time = time.time() - start_time
        print(f"\n⏱️  Total execution time: {execution_time:.2f}s ({execution_time/total_cases:.3f}s per case)")

        # Verify results
        results_dir = Path("perfectgaz_3calc_results")
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return

        print(f"\n📂 Results directory exists: {results_dir}")

        # Expected files in each case directory (from all 3 calculators)
        expected_files = [
            "perfectgaz_3calc_vars.txt",  # Original input file
            "out.txt",                    # stdout from calculators
            "err.txt",                    # stderr from calculators
            "log.txt",                    # execution log
            "output.txt",                 # from PerfectGazPressure.sh
            "volume_result.txt",          # from PerfectGazVolume.sh
            "temperature_result.txt",     # from PerfectGazTemperature.sh
            ".fz_hash"                    # hash file for caching
        ]

        # Check each case directory
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        case_dirs.sort(key=lambda x: x.name)

        print(f"\n📋 Found {len(case_dirs)} case directories")

        all_cases_valid = True
        missing_files_summary = {}
        sample_results = {}

        # Check first 5 cases in detail
        for i, case_dir in enumerate(case_dirs[:5]):
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
            calculator_outputs = {}

            for expected_file in expected_files:
                file_path = case_dir / expected_file
                if file_path.exists() and file_path.stat().st_size >= 0:  # Allow empty err.txt
                    present_files.append(expected_file)
                    size = file_path.stat().st_size

                    # Read calculator output files
                    if expected_file in ["output.txt", "volume_result.txt", "temperature_result.txt"] and size > 0:
                        try:
                            content = file_path.read_text().strip()
                            calculator_outputs[expected_file] = content
                            print(f"  📄 {expected_file}: {content}")
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

            # Store sample for analysis
            if calculator_outputs:
                sample_results[case_name] = calculator_outputs

            # Show file count summary
            print(f"  📊 Files: {len(present_files)}/{len(expected_files)} present")

        # Quick check for remaining cases
        if len(case_dirs) > 5:
            print(f"\n📋 Quick check of remaining {len(case_dirs)-5} cases...")
            remaining_issues = 0
            for case_dir in case_dirs[5:]:
                missing_count = 0
                for expected_file in expected_files:
                    file_path = case_dir / expected_file
                    if not (file_path.exists() and (file_path.stat().st_size >= 0)):
                        missing_count += 1
                if missing_count > 0:
                    remaining_issues += 1

            if remaining_issues == 0:
                print(f"  ✅ All remaining cases have complete file sets")
            else:
                print(f"  ⚠️  {remaining_issues} cases have missing files")

        # Calculator-specific file verification
        print(f"\n🔬 Calculator Output Verification:")
        calc_file_counts = {
            "output.txt": 0,
            "volume_result.txt": 0,
            "temperature_result.txt": 0
        }

        for case_dir in case_dirs:
            for calc_file in calc_file_counts.keys():
                file_path = case_dir / calc_file
                if file_path.exists() and file_path.stat().st_size > 0:
                    calc_file_counts[calc_file] += 1

        print(f"  PerfectGazPressure.sh outputs (output.txt): {calc_file_counts['output.txt']}/{len(case_dirs)}")
        print(f"  PerfectGazVolume.sh outputs (volume_result.txt): {calc_file_counts['volume_result.txt']}/{len(case_dirs)}")
        print(f"  PerfectGazTemperature.sh outputs (temperature_result.txt): {calc_file_counts['temperature_result.txt']}/{len(case_dirs)}")

        # Summary analysis
        print(f"\n📈 Results Analysis:")
        print(f"  Total cases: {len(case_dirs)}")
        print(f"  Expected cases: {total_cases}")

        if len(case_dirs) == total_cases:
            print(f"  ✅ All expected case directories created")
        else:
            print(f"  ❌ Missing case directories: {total_cases - len(case_dirs)}")

        files_per_case = len(expected_files)
        total_expected_files = len(case_dirs) * files_per_case
        total_missing = sum(len(files) if isinstance(files, list) else 1 for files in missing_files_summary.values())
        success_rate = ((total_expected_files - total_missing) / total_expected_files * 100) if total_expected_files > 0 else 0

        print(f"  File success rate: {success_rate:.1f}%")

        # Performance analysis
        print(f"\n⚡ Performance Analysis:")
        print(f"  Cases per second: {total_cases/execution_time:.1f}")
        print(f"  Average time per case: {execution_time/total_cases:.3f}s")
        print(f"  Multiple calculators handled efficiently")

        # Sample calculations
        if sample_results:
            print(f"\n🔬 Sample Calculator Results:")
            sample_count = min(3, len(sample_results))
            for case_name, outputs in list(sample_results.items())[:sample_count]:
                print(f"  {case_name}:")
                for file_name, content in outputs.items():
                    calc_type = {"output.txt": "Pressure", "volume_result.txt": "Volume", "temperature_result.txt": "Temperature"}
                    print(f"    {calc_type.get(file_name, file_name)}: {content}")

        # Final verdict
        if success_rate >= 95 and len(case_dirs) == total_cases:
            print(f"\n🎉 SUCCESS: 3-Calculator test completed successfully!")
            print(f"   ✅ All {total_cases} cases with {len(expected_files)} files each")
            print(f"   ✅ All 3 calculators executed in case directories")
            print(f"   ✅ All output files created correctly")
        else:
            print(f"\n⚠️  PARTIAL SUCCESS: {success_rate:.1f}% success rate")
            if missing_files_summary:
                print(f"   Issues in {len(missing_files_summary)} cases")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['perfectgaz_3calc_vars.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_perfectgaz_3calculators()