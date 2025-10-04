#!/usr/bin/env python3
"""
Test that all output files (command outputs, out.txt, err.txt, log.txt)
are properly written to the case directory before it gets moved
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_output_files_location():
    """Test that all output files are in case directory and timing is correct"""

    # Create test script that generates multiple output files
    with open('test_multi_output.sh', 'w') as f:
        f.write('''#!/bin/bash
echo "Script starting..." > script_log.txt
echo "This goes to stdout"
echo "This goes to stderr" >&2
sleep 0.1  # Small delay to simulate real work
echo "Creating result file..." >> script_log.txt
echo "result = 555" > custom_result.txt
echo "Creating another file..." >> script_log.txt
echo "extra data" > extra_file.dat
echo "Script completed" >> script_log.txt
echo "Final stdout message"
''')
    os.chmod('test_multi_output.sh', 0o755)

    with open('test_input_files.txt', 'w') as f:
        f.write('test input data for file location test\n')

    print("📁 Testing Output Files Location and Timing")
    print("=" * 60)

    try:
        # Run the test
        result = fzr(
            input_path="test_input_files.txt",
            model={"output": {"value": "echo 'Model output'"}},
            input_variables={},
            calculators=["sh://bash test_multi_output.sh"],
            results_dir="file_location_test"
        )

        print(f"\n📊 Execution Results:")
        print(f"Status: {result.get('status', ['unknown'])[0]}")
        print(f"Command: {result.get('command', ['None'])[0]}")

        # Check if results directory exists
        results_dir = Path("file_location_test")
        if results_dir.exists():
            print(f"\n📂 Results directory exists: {results_dir}")

            # List all files in the results directory
            all_files = list(results_dir.glob("*"))
            print(f"\n📋 Files found in results directory ({len(all_files)} files):")

            expected_files = [
                "out.txt",      # stdout from command
                "err.txt",      # stderr from command
                "log.txt",      # execution log
                "custom_result.txt",  # file created by script
                "script_log.txt",     # log file created by script
                "extra_file.dat",     # extra file created by script
                "output"        # model output file
            ]

            found_files = {}
            for file_path in all_files:
                file_name = file_path.name
                found_files[file_name] = file_path
                file_size = file_path.stat().st_size if file_path.is_file() else 0
                print(f"  ✓ {file_name} ({file_size} bytes)")

                # Show content of key files
                if file_name in ["out.txt", "err.txt", "log.txt", "custom_result.txt", "script_log.txt"] and file_size > 0:
                    try:
                        content = file_path.read_text().strip()
                        if content:
                            print(f"    Content: {content[:100]}{'...' if len(content) > 100 else ''}")
                    except Exception as e:
                        print(f"    Error reading: {e}")

            # Check for expected files
            print(f"\n🔍 Expected Files Check:")
            all_found = True
            for expected_file in expected_files:
                if expected_file in found_files:
                    file_path = found_files[expected_file]
                    size = file_path.stat().st_size if file_path.is_file() else 0
                    print(f"  ✅ {expected_file} - Found ({size} bytes)")

                    # Check if file has content (except for potentially empty err.txt)
                    if size == 0 and expected_file not in ["err.txt"]:
                        print(f"    ⚠️  Warning: {expected_file} is empty")
                        all_found = False
                else:
                    print(f"  ❌ {expected_file} - Missing")
                    all_found = False

            # Check for timing issues by looking at file modification times
            print(f"\n⏰ File Timing Analysis:")
            if found_files:
                file_times = []
                for name, path in found_files.items():
                    if path.is_file():
                        mtime = path.stat().st_mtime
                        file_times.append((name, mtime))

                # Sort by modification time
                file_times.sort(key=lambda x: x[1])

                print("  Files by modification time (earliest to latest):")
                for i, (name, mtime) in enumerate(file_times):
                    time_str = time.strftime('%H:%M:%S.%f', time.localtime(mtime))[:12]
                    if i > 0:
                        time_diff = mtime - file_times[i-1][1]
                        print(f"    {name} at {time_str} (+{time_diff:.3f}s)")
                    else:
                        print(f"    {name} at {time_str}")

                # Check if there are very small time differences that might indicate timing issues
                max_time_diff = max(mtime for _, mtime in file_times) - min(mtime for _, mtime in file_times)
                print(f"  Total time span: {max_time_diff:.3f}s")

                if max_time_diff < 0.01:  # Less than 10ms
                    print("  ⚠️  Very short time span - might need delay to ensure all files are written")
                else:
                    print("  ✅ Reasonable time span for file operations")

            print(f"\n📋 Summary:")
            if all_found:
                print("  ✅ All expected files found in results directory")
            else:
                print("  ❌ Some expected files missing or empty")
                print("  💡 This might indicate timing issues - files not fully written before directory move")

        else:
            print(f"❌ Results directory not found: {results_dir}")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['test_multi_output.sh', 'test_input_files.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_output_files_location()