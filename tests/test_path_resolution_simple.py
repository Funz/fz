#!/usr/bin/env python3
"""
Simple test for sh:// path resolution with random failures
"""

import os
import sys
import random
import tempfile
from pathlib import Path

# Add parent directory to Python path for importing fz
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr


def test_path_resolution_with_failures():
    """Test path resolution handles random failures correctly"""

    # Create test files in current directory
    test_files = {
        'test_input.txt': 'line1\nline2\nline3\n',
        'simple_script.sh': '''#!/bin/bash
echo "Simple script executed"
echo "result = 42" > output.txt
''',
        'random_script.sh': '''#!/bin/bash
# Random failure script
if [ $((RANDOM % 3)) -eq 0 ]; then
    echo "Random failure!" >&2
    exit 1
else
    echo "Random success"
    echo "result = 100" > output.txt
fi
''',
        'path_script.sh': '''#!/bin/bash
# Script that uses relative paths
if [ -f test_input.txt ]; then
    wc -l test_input.txt > count.txt
    echo "result = $(cat count.txt | awk '{print $1}')" > output.txt
else
    echo "result = 0" > output.txt
fi
'''
    }

    # Write test files
    for filename, content in test_files.items():
        with open(filename, 'w') as f:
            f.write(content)
        if filename.endswith('.sh'):
            os.chmod(filename, 0o755)

    print("🧪 Testing sh:// Path Resolution with Random Failures")
    print("=" * 60)

    # Test cases with mix of expected successes and random failures
    test_cases = [
        {
            "name": "simple_success",
            "calculator": "sh://bash simple_script.sh",
            "should_succeed": True
        },
        {
            "name": "path_dependent",
            "calculator": "sh://bash path_script.sh",
            "should_succeed": True
        },
        {
            "name": "random_failure_1",
            "calculator": "sh://bash random_script.sh",
            "should_succeed": "random"
        },
        {
            "name": "file_operations",
            "calculator": "sh://cp test_input.txt copy.txt && echo 'result = 10' > output.txt",
            "should_succeed": True
        },
        {
            "name": "random_failure_2",
            "calculator": "sh://bash random_script.sh",
            "should_succeed": "random"
        }
    ]

    results = []

    for i, case in enumerate(test_cases):
        print(f"\n🎯 Test {i+1}: {case['name']}")

        try:
            # Clean previous results
            for f in ['output.txt', 'copy.txt', 'count.txt']:
                if os.path.exists(f):
                    os.remove(f)

            # Run test
            result = fzr(
                input_path="test_input.txt",  # Use a specific input file
                model={"output": {"result": "cat output.txt | grep 'result = ' | awk '{print $NF}' || echo 'failed'"}},
                var_values={},
                calculators=[case["calculator"]],
                results_dir=f"test_{case['name']}"
            )

            status = result.get('status', [None])[0]
            output_value = result.get('result', [None])[0]
            error = result.get('error', [None])[0]

            success = status == 'done' and output_value and output_value != 'failed'

            results.append({
                "name": case['name'],
                "success": success,
                "status": status,
                "output": output_value,
                "error": error,
                "expected": case['should_succeed']
            })

            if success:
                print(f"   ✅ SUCCESS: result = {output_value}")
            else:
                if case['should_succeed'] == "random":
                    print(f"   ⚠️  Expected random failure: {error}")
                else:
                    print(f"   ❌ UNEXPECTED FAILURE: {error}")

        except Exception as e:
            results.append({
                "name": case['name'],
                "success": False,
                "status": "exception",
                "output": None,
                "error": str(e),
                "expected": case['should_succeed']
            })
            print(f"   ❌ EXCEPTION: {e}")

    # Analyze results
    print(f"\n🏁 Summary")
    print("=" * 40)

    total_tests = len(results)
    successes = sum(1 for r in results if r['success'])
    expected_successes = sum(1 for r in results if r['expected'] is True)
    actual_expected_successes = sum(1 for r in results if r['success'] and r['expected'] is True)
    random_tests = sum(1 for r in results if r['expected'] == "random")

    print(f"Total tests: {total_tests}")
    print(f"Successes: {successes}")
    print(f"Expected to succeed: {expected_successes}")
    print(f"Actually succeeded (of expected): {actual_expected_successes}")
    print(f"Random failure tests: {random_tests}")

    # Check if path resolution is working
    path_dependent_success = any(r['success'] for r in results if r['name'] == 'path_dependent')
    file_ops_success = any(r['success'] for r in results if r['name'] == 'file_operations')

    print(f"\n📁 Path Resolution Check:")
    print(f"✅ Path-dependent script: {'PASSED' if path_dependent_success else 'FAILED'}")
    print(f"✅ File operations: {'PASSED' if file_ops_success else 'FAILED'}")

    # Test isolation check
    isolation_ok = actual_expected_successes == expected_successes
    print(f"\n🔒 Test Isolation Check:")
    print(f"✅ Expected tests unaffected by random failures: {'PASSED' if isolation_ok else 'FAILED'}")

    # Cleanup
    for filename in test_files.keys():
        if os.path.exists(filename):
            os.remove(filename)

    for f in ['output.txt', 'copy.txt', 'count.txt']:
        if os.path.exists(f):
            os.remove(f)

    return {
        "total": total_tests,
        "successes": successes,
        "path_resolution_working": path_dependent_success and file_ops_success,
        "isolation_working": isolation_ok
    }


if __name__ == "__main__":
    results = test_path_resolution_with_failures()

    print(f"\n🎯 Final Results:")
    print(f"Path resolution: {'✅ WORKING' if results['path_resolution_working'] else '❌ FAILED'}")
    print(f"Test isolation: {'✅ WORKING' if results['isolation_working'] else '❌ FAILED'}")

    if results['path_resolution_working'] and results['isolation_working']:
        print(f"\n✅ SUCCESS: Enhanced path resolution is working correctly!")
    else:
        print(f"\n❌ ISSUES DETECTED: Check implementation")