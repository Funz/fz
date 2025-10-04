#!/usr/bin/env python3
"""
Test script to verify comprehensive path resolution in sh:// commands
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fz import fzr
import tempfile
import subprocess

def create_test_environment():
    """Create test scripts and subdirectories with various path scenarios"""

    # Create subdirectory with scripts
    os.makedirs("scripts", exist_ok=True)
    os.makedirs("tools/bin", exist_ok=True)

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("# Test input\n")
        f.write("value = $(X)\n")

    # Script 1: In current directory (relative path)
    with open("local_script.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Local script executed'\n")
        f.write("echo 'result = 100' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("local_script.sh", 0o755)

    # Script 2: In subdirectory (relative path)
    with open("scripts/sub_script.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Sub script executed'\n")
        f.write("echo 'result = 200' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("scripts/sub_script.sh", 0o755)

    # Script 3: With arguments and relative paths
    with open("tools/bin/complex_script.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Complex script executed with args:' \"$@\"\n")
        f.write("echo 'result = 300' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("tools/bin/complex_script.sh", 0o755)

    # Script 4: That uses relative paths internally
    with open("path_dependent.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Working directory:' $(pwd)\n")
        f.write("ls -la > dir_listing.txt\n")
        f.write("echo 'result = 400' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("path_dependent.sh", 0o755)

def test_various_path_formats():
    """Test different sh:// command formats with paths"""

    test_cases = [
        {
            "name": "Relative script in current directory",
            "calculator": "sh:///bin/bash ./local_script.sh",
            "expected_result": 100
        },
        {
            "name": "Relative script in subdirectory",
            "calculator": "sh:///bin/bash scripts/sub_script.sh",
            "expected_result": 200
        },
        {
            "name": "Relative script with complex path",
            "calculator": "sh:///bin/bash tools/bin/complex_script.sh arg1 arg2",
            "expected_result": 300
        },
        {
            "name": "Script with working directory dependency",
            "calculator": "sh:///bin/bash ./path_dependent.sh",
            "expected_result": 400
        },
        {
            "name": "Already absolute path (should not change)",
            "calculator": f"sh:///bin/bash {os.path.abspath('local_script.sh')}",
            "expected_result": 100
        },
        {
            "name": "Command with just program name (no paths)",
            "calculator": "sh://echo '500' > output.txt && echo 'result = 500' > output.txt",
            "expected_result": None  # This might not work as expected, but should not fail path resolution
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"TEST {i+1}: {test_case['name']}")
        print(f"Calculator: {test_case['calculator']}")
        print(f"{'='*60}")

        try:
            result = fzr("input.txt",
            {
                "X": [f"test_{i+1}"]
            },
            {
                "varprefix": "$",
                "delim": "()",
                "output": {"result": "grep 'result = ' output.txt | awk '{print $3}' || echo 'none'"}
            },

            calculators=[test_case['calculator']],
            results_dir=f"path_test_{i+1}")

            test_result = {
                "test_name": test_case['name'],
                "status": result['status'][0],
                "result_value": result['result'][0],
                "expected": test_case['expected_result'],
                "calculator": result['calculator'][0],
                "error": result.get('error', [None])[0]
            }

            if test_result['status'] == 'done':
                print(f"✅ SUCCESS: Status={test_result['status']}, Result={test_result['result_value']}")
            else:
                print(f"❌ FAILED: Status={test_result['status']}, Error={test_result['error']}")

            results.append(test_result)

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append({
                "test_name": test_case['name'],
                "status": "exception",
                "error": str(e),
                "expected": test_case['expected_result']
            })

    return results

def print_summary(results):
    """Print test summary"""
    print(f"\n{'='*60}")
    print("SUMMARY OF PATH RESOLUTION TESTS")
    print(f"{'='*60}")

    successful = sum(1 for r in results if r['status'] == 'done')
    total = len(results)

    print(f"Total tests: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")

    print(f"\nDetailed Results:")
    for i, result in enumerate(results, 1):
        status_icon = "✅" if result['status'] == 'done' else "❌"
        print(f"  {i}. {status_icon} {result['test_name']}")
        if result['status'] != 'done':
            print(f"     Error: {result.get('error', 'Unknown error')}")

    if successful == total:
        print(f"\n🎉 All path resolution tests passed!")
    else:
        print(f"\n⚠️  {total - successful} tests failed - path resolution needs improvement")

if __name__ == "__main__":
    print("🧪 Testing Comprehensive Path Resolution in sh:// Commands")
    print("This test verifies that all relative paths are properly converted to absolute paths")

    # Get current working directory for reference
    print(f"Current working directory: {os.getcwd()}")

    create_test_environment()
    results = test_various_path_formats()
    print_summary(results)