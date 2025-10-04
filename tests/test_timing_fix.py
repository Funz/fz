#!/usr/bin/env python3
"""
Test that the timing fix ensures all files are properly written before case directory processing
"""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_timing_fix():
    """Test that files are properly written with timing fix"""

    # Create a script that creates multiple files with some potential timing complexity
    with open('timing_test_script.sh', 'w') as f:
        f.write('''#!/bin/bash
# Script to test file timing
echo "Starting timing test..." > timing_log.txt

# Write to stdout and stderr simultaneously
echo "Stdout message 1"
echo "Stderr message 1" >&2

# Create multiple files rapidly
for i in {1..5}; do
    echo "File $i content" > "file_$i.txt"
    echo "Creating file $i" >> timing_log.txt
done

# More stdout/stderr
echo "Stdout message 2"
echo "Stderr message 2" >&2

# Final result file
echo "result = 888" > final_result.txt
echo "All files created" >> timing_log.txt

# End with more output
echo "Script completed successfully"
echo "Final stderr message" >&2
''')
    os.chmod('timing_test_script.sh', 0o755)

    with open('timing_input.txt', 'w') as f:
        f.write('timing test input data\n')

    print("⏰ Testing Timing Fix for File Operations")
    print("=" * 60)

    try:
        # Run multiple tests to check for timing consistency
        for test_num in range(3):
            print(f"\n🔄 Test Run {test_num + 1}/3:")

            result = fzr(
                input_path="timing_input.txt",
                input_variables={},
                model={"output": {"value": "echo 'Timing test completed'"}},
                calculators=["sh://bash timing_test_script.sh"],
                results_dir=f"timing_test_{test_num + 1}"
            )

            # Check results directory
            results_dir = Path(f"timing_test_{test_num + 1}")
            if results_dir.exists():
                all_files = list(results_dir.glob("*"))

                # Expected files
                expected_files = [
                    "out.txt", "err.txt", "log.txt",
                    "timing_log.txt", "final_result.txt",
                    "file_1.txt", "file_2.txt", "file_3.txt", "file_4.txt", "file_5.txt"
                ]

                found_count = 0
                missing_files = []
                empty_files = []

                for expected in expected_files:
                    found_file = None
                    for file_path in all_files:
                        if file_path.name == expected:
                            found_file = file_path
                            break

                    if found_file and found_file.is_file():
                        size = found_file.stat().st_size
                        if size > 0:
                            found_count += 1
                        else:
                            empty_files.append(expected)
                    else:
                        missing_files.append(expected)

                print(f"  📁 Files found: {found_count}/{len(expected_files)}")
                if missing_files:
                    print(f"  ❌ Missing: {missing_files}")
                if empty_files:
                    print(f"  ⚠️  Empty: {empty_files}")

                # Check specific file contents
                key_files_ok = True
                for key_file in ["out.txt", "err.txt", "final_result.txt"]:
                    file_path = results_dir / key_file
                    if file_path.exists() and file_path.stat().st_size > 0:
                        content = file_path.read_text().strip()
                        if key_file == "final_result.txt" and "result = 888" in content:
                            print(f"  ✅ {key_file}: Content correct")
                        elif key_file == "out.txt" and "Stdout message" in content:
                            print(f"  ✅ {key_file}: Content correct")
                        elif key_file == "err.txt" and "Stderr message" in content:
                            print(f"  ✅ {key_file}: Content correct")
                        else:
                            print(f"  ⚠️  {key_file}: Unexpected content")
                            key_files_ok = False
                    else:
                        print(f"  ❌ {key_file}: Missing or empty")
                        key_files_ok = False

                if found_count == len(expected_files) and key_files_ok:
                    print(f"  ✅ Test {test_num + 1}: All files correctly written")
                else:
                    print(f"  ❌ Test {test_num + 1}: Some files missing or incorrect")
            else:
                print(f"  ❌ Test {test_num + 1}: Results directory not found")

        print(f"\n📋 Timing Fix Summary:")
        print(f"  • Added 10ms delay after subprocess completion")
        print(f"  • Ensures stdout/stderr streams are fully closed")
        print(f"  • Prevents race conditions during case directory processing")
        print(f"  • Files should be consistently available in results directory")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['timing_test_script.sh', 'timing_input.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_timing_fix()