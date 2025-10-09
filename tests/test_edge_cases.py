#!/usr/bin/env python3
"""
Test edge cases for path resolution in sh:// commands
"""

import sys
import os

from fz import fzr

def create_edge_case_scripts():
    """Create scripts for edge case testing"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("# Edge case test input\n")
        f.write("test = $(T)\n")

    # Script with spaces in path
    os.makedirs("folder with spaces", exist_ok=True)
    with open("folder with spaces/script with spaces.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Script with spaces in path'\n")
        f.write("echo 'result = 123' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("folder with spaces/script with spaces.sh", 0o755)

    # Script with multiple path arguments
    with open("multi_path_script.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Multi-path script executed'\n")
        f.write("echo 'Args:' \"$@\"\n")
        f.write("echo 'result = 456' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("multi_path_script.sh", 0o755)

    # Helper script
    with open("helper.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("echo 'Helper script'\n")
        f.write("exit 0\n")
    os.chmod("helper.sh", 0o755)

def test_edge_cases():
    """Test edge cases for path resolution"""

    test_cases = [
        {
            "name": "Multiple relative paths in command",
            "calculator": "sh:///bin/bash ./multi_path_script.sh ./helper.sh scripts/sub_script.sh",
            "expected_result": 456
        },
        {
            "name": "Path with spaces (quoted)",
            "calculator": "sh:///bin/bash \"folder with spaces/script with spaces.sh\"",
            "expected_result": 123
        },
        {
            "name": "Relative path with ../ parent directory",
            "calculator": f"sh:///bin/bash {os.path.join('.', 'multi_path_script.sh')}",
            "expected_result": 456
        },
        {
            "name": "Mixed absolute and relative paths",
            "calculator": f"sh:///bin/bash /bin/echo 'test' && ./multi_path_script.sh",
            "expected_result": 456
        }
    ]

    print("🧪 Testing Edge Cases for Path Resolution")
    print(f"Current working directory: {os.getcwd()}\n")

    results = []

    for i, test_case in enumerate(test_cases):
        print(f"{'='*60}")
        print(f"EDGE CASE {i+1}: {test_case['name']}")
        print(f"Calculator: {test_case['calculator']}")
        print(f"{'='*60}")

        try:
            result = fzr("input.txt",
            {
                "varprefix": "$",
                "delim": "()",
                "output": {"result": "grep 'result = ' output.txt | awk '{print $3}' || echo 'none'"}
            },
            {
                "T": [f"edge_{i+1}"]
            },
            
            calculators=[test_case['calculator']],
            results_dir=f"edge_test_{i+1}")

            test_result = {
                "test_name": test_case['name'],
                "status": result['status'][0],
                "result_value": result['result'][0],
                "expected": test_case['expected_result'],
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

    # Summary
    print(f"\n{'='*60}")
    print("EDGE CASE TEST SUMMARY")
    print(f"{'='*60}")

    successful = sum(1 for r in results if r['status'] == 'done')
    total = len(results)

    for i, result in enumerate(results, 1):
        status_icon = "✅" if result['status'] == 'done' else "❌"
        print(f"  {i}. {status_icon} {result['test_name']}")
        if result['status'] != 'done':
            print(f"     Error: {result.get('error', 'Unknown error')}")

    print(f"\nResults: {successful}/{total} edge cases passed")

    return results

if __name__ == "__main__":
    create_edge_case_scripts()
    test_edge_cases()