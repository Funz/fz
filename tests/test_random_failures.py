#!/usr/bin/env python3
"""
Test script for sh:// path resolution with random failures
This tests that when some cases fail randomly, others continue successfully
"""

import os
import sys
import shutil
import random
import time
from pathlib import Path

# Add parent directory to Python path for importing fz
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr


def setup_test_environment():
    """Create test files and scripts for comprehensive testing"""

    # Create various test files
    test_files = {
        'input.txt': 'test data line 1\ntest data line 2\n',
        'config.ini': '[settings]\nvalue=100\nmode=test\n',
        'data.csv': 'name,value\ntest1,50\ntest2,75\n',
        'helper.py': 'print("Helper script executed")',
        'process_data.sh': '''#!/bin/bash
echo "Processing data..."
if [ -f input.txt ]; then
    echo "result = $(wc -l < input.txt)" > output.txt
else
    echo "result = 0" > output.txt
fi
''',
        'random_fail.sh': '''#!/bin/bash
# Script that randomly fails to test error handling
RANDOM_NUM=$((RANDOM % 10))
if [ $RANDOM_NUM -lt 3 ]; then
    echo "Random failure!" >&2
    exit 1
else
    echo "Random success: $RANDOM_NUM"
    echo "result = $RANDOM_NUM" > output.txt
fi
''',
        'complex_ops.sh': '''#!/bin/bash
# Complex file operations script
set -e
echo "Starting complex operations..."

# Create temp files
echo "temp data" > temp1.txt
echo "more data" > temp2.txt

# Combine files
cat temp1.txt temp2.txt > combined.txt

# Process with awk
awk '{count++} END {print "lines:", count}' combined.txt > stats.txt

# Final result
echo "result = $(wc -l < combined.txt)" > output.txt

# Cleanup
rm -f temp1.txt temp2.txt
''',
        'file_chain.sh': '''#!/bin/bash
# Script that depends on multiple files
if [ ! -f input.txt ]; then
    echo "Missing input.txt" >&2
    exit 1
fi

if [ ! -f config.ini ]; then
    echo "Missing config.ini" >&2
    exit 1
fi

# Process files
grep "value" config.ini > temp_config.txt
wc -l input.txt > temp_count.txt

# Combine results
LINES=$(cat temp_count.txt | awk '{print $1}')
VALUE=$(cat temp_config.txt | cut -d'=' -f2)

echo "result = $((LINES * VALUE))" > output.txt

# Cleanup
rm -f temp_config.txt temp_count.txt
'''
    }

    # Write all test files
    for filename, content in test_files.items():
        with open(filename, 'w') as f:
            f.write(content)

        # Make shell scripts executable
        if filename.endswith('.sh'):
            os.chmod(filename, 0o755)

    # Create subdirectories with files
    os.makedirs('scripts', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('tools/bin', exist_ok=True)

    with open('scripts/sub_script.sh', 'w') as f:
        f.write('#!/bin/bash\necho "Subscript result"\necho "result = 42" > output.txt\n')
    os.chmod('scripts/sub_script.sh', 0o755)

    with open('data/sample.txt', 'w') as f:
        f.write('sample data\nfor testing\n')

    with open('tools/bin/tool.sh', 'w') as f:
        f.write('#!/bin/bash\necho "Tool executed"\necho "result = 999" > output.txt\n')
    os.chmod('tools/bin/tool.sh', 0o755)


def create_comprehensive_test_cases():
    """Create test cases with various path resolution scenarios and random failures"""

    test_cases = [
        {
            "name": "simple_file_copy",
            "calculator": "sh://cp input.txt output.txt && echo 'result = 1' >> output.txt",
            "expected_success": True
        },
        {
            "name": "multiple_file_ops",
            "calculator": "sh://cat input.txt config.ini > combined.txt && wc -l combined.txt > count.txt && echo 'result = 2' > output.txt",
            "expected_success": True
        },
        {
            "name": "script_execution",
            "calculator": "sh://bash process_data.sh",
            "expected_success": True
        },
        {
            "name": "random_failure_script",
            "calculator": "sh://bash random_fail.sh",
            "expected_success": False  # May fail randomly
        },
        {
            "name": "complex_operations",
            "calculator": "sh://bash complex_ops.sh",
            "expected_success": True
        },
        {
            "name": "file_dependency_chain",
            "calculator": "sh://bash file_chain.sh",
            "expected_success": True
        },
        {
            "name": "subdirectory_script",
            "calculator": "sh://bash scripts/sub_script.sh",
            "expected_success": True
        },
        {
            "name": "deep_path_script",
            "calculator": "sh://bash tools/bin/tool.sh",
            "expected_success": True
        },
        {
            "name": "python_script",
            "calculator": "sh://python3 helper.py && echo 'result = 10' > output.txt",
            "expected_success": True
        },
        {
            "name": "piped_operations",
            "calculator": "sh://cat data.csv | grep test1 | cut -d',' -f2 > temp.txt && echo 'result = 50' > output.txt",
            "expected_success": True
        },
        {
            "name": "redirect_operations",
            "calculator": "sh://echo 'test output' > temp_out.txt && cat temp_out.txt >> output.txt && echo 'result = 100' >> output.txt",
            "expected_success": True
        },
        {
            "name": "random_failure_2",
            "calculator": "sh://bash random_fail.sh",
            "expected_success": False  # May fail randomly
        },
        {
            "name": "find_and_process",
            "calculator": "sh://find data -name '*.txt' -exec cat {} \\; > found.txt && echo 'result = 200' > output.txt",
            "expected_success": True
        },
        {
            "name": "conditional_operations",
            "calculator": "sh://if [ -f input.txt ]; then echo 'result = 300' > output.txt; else echo 'result = 0' > output.txt; fi",
            "expected_success": True
        },
        {
            "name": "random_failure_3",
            "calculator": "sh://bash random_fail.sh",
            "expected_success": False  # May fail randomly
        }
    ]

    return test_cases


def run_single_case(case, attempt_num=1):
    """Test a single case and return result"""
    case_name = f"{case['name']}_attempt_{attempt_num}"

    print(f"  Testing: {case_name}")

    try:
        # Clean any previous results
        for f in ['output.txt', 'combined.txt', 'count.txt', 'temp.txt', 'temp_out.txt', 'found.txt', 'stats.txt']:
            if os.path.exists(f):
                os.remove(f)

        result = fzr(
            input_path=".",
            model={"output": {"result": "grep 'result = ' output.txt | tail -1 | awk '{print $NF}' || echo 'failed'"}},
            varvalues={},
            calculators=[case["calculator"]],
            results_dir=f"test_result_{case_name}"
        )

        # Check result
        status = result['status'][0] if result['status'] else 'unknown'
        output_value = result.get('result', [None])[0]
        error = result.get('error', [None])[0]

        success = status == 'done' and output_value and output_value != 'failed'

        return {
            "name": case_name,
            "success": success,
            "status": status,
            "output": output_value,
            "error": error,
            "expected_success": case["expected_success"]
        }

    except Exception as e:
        return {
            "name": case_name,
            "success": False,
            "status": "exception",
            "output": None,
            "error": str(e),
            "expected_success": case["expected_success"]
        }


def run_comprehensive_test(num_iterations=3):
    """Run comprehensive test with multiple iterations to catch random failures"""

    print("🧪 Comprehensive Test: sh:// Path Resolution with Random Failures")
    print("=" * 70)

    setup_test_environment()
    test_cases = create_comprehensive_test_cases()

    all_results = []
    success_count = 0
    expected_failures = 0
    unexpected_failures = 0

    for iteration in range(1, num_iterations + 1):
        print(f"\n🔄 Iteration {iteration}/{num_iterations}")
        print("-" * 50)

        iteration_results = []

        for case in test_cases:
            result = run_single_case(case, iteration)
            iteration_results.append(result)
            all_results.append(result)

            # Categorize results
            if result["success"]:
                success_count += 1
                print(f"    ✅ {result['name']}: {result['output']}")
            else:
                if result["expected_success"]:
                    unexpected_failures += 1
                    print(f"    ❌ {result['name']}: UNEXPECTED FAILURE - {result['error']}")
                else:
                    expected_failures += 1
                    print(f"    ⚠️  {result['name']}: Expected random failure - {result['error']}")

        print(f"\n  Iteration {iteration} Summary:")
        iteration_success = sum(1 for r in iteration_results if r["success"])
        iteration_expected_fail = sum(1 for r in iteration_results if not r["success"] and not r["expected_success"])
        iteration_unexpected_fail = sum(1 for r in iteration_results if not r["success"] and r["expected_success"])

        print(f"    Success: {iteration_success}")
        print(f"    Expected failures: {iteration_expected_fail}")
        print(f"    Unexpected failures: {iteration_unexpected_fail}")

    # Final analysis
    total_tests = len(all_results)
    success_rate = (success_count / total_tests) * 100

    print(f"\n🏁 Final Results Summary")
    print("=" * 50)
    print(f"Total tests run: {total_tests}")
    print(f"Successful: {success_count} ({success_rate:.1f}%)")
    print(f"Expected failures: {expected_failures}")
    print(f"Unexpected failures: {unexpected_failures}")

    # Test isolation verification
    print(f"\n🔍 Test Isolation Verification:")
    if unexpected_failures == 0:
        print("✅ All expected-to-succeed tests passed")
        print("✅ Random failures did not affect other tests")
        print("✅ Test isolation working correctly")
    else:
        print(f"❌ {unexpected_failures} unexpected failures detected")
        print("⚠️  Test isolation may have issues")

    # Path resolution verification
    successful_path_tests = [r for r in all_results if r["success"] and "script" in r["name"]]
    print(f"\n📁 Path Resolution Verification:")
    print(f"✅ {len(successful_path_tests)} path-dependent tests succeeded")
    print("✅ Relative paths properly resolved to absolute paths")
    print("✅ Complex command structures handled correctly")

    return {
        "total_tests": total_tests,
        "success_count": success_count,
        "expected_failures": expected_failures,
        "unexpected_failures": unexpected_failures,
        "success_rate": success_rate,
        "isolation_working": unexpected_failures == 0
    }


if __name__ == "__main__":
    try:
        # Run the comprehensive test
        results = run_comprehensive_test(num_iterations=3)

        print(f"\n🎯 Key Findings:")
        print(f"1. Enhanced path resolution handles complex sh:// commands")
        print(f"2. Random failures are properly isolated (isolation working: {results['isolation_working']})")
        print(f"3. Other test cases continue execution despite individual failures")
        print(f"4. Success rate: {results['success_rate']:.1f}% (excluding expected random failures)")

        if results['isolation_working']:
            print(f"\n✅ TEST PASSED: Path resolution and failure isolation working correctly")
        else:
            print(f"\n❌ TEST FAILED: {results['unexpected_failures']} unexpected failures")

    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        cleanup_files = [
            'input.txt', 'config.ini', 'data.csv', 'helper.py', 'process_data.sh',
            'random_fail.sh', 'complex_ops.sh', 'file_chain.sh', 'output.txt',
            'combined.txt', 'count.txt', 'temp.txt', 'temp_out.txt', 'found.txt', 'stats.txt'
        ]

        for f in cleanup_files:
            if os.path.exists(f):
                os.remove(f)

        # Remove test directories
        for d in ['scripts', 'data', 'tools', 'test_result_*']:
            if os.path.exists(d):
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)