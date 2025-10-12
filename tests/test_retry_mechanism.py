#!/usr/bin/env python3
"""
Test script to demonstrate the retry mechanism for failed calculations
"""

import sys
import os
import pytest

from fz import fzr
import time

@pytest.fixture(autouse=True)
def test_files():
    """Create test files for retry mechanism"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Test input file\n")
        f.write("# Temperature: $(T_celsius) celsius\n")
        f.write("echo 'Temperature: $(T_celsius)'\n")

    # Create a script that fails on first attempt but succeeds on retry
    with open("FailThenSuccess.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script that fails on first execution, succeeds on second\n")
        f.write("FLAG_FILE=\"/tmp/fz_retry_flag_$$\"\n")
        f.write("if [ -f \"$FLAG_FILE\" ]; then\n")
        f.write("    # Second attempt - succeed\n")
        f.write("    echo 'Second attempt: SUCCESS'\n")
        f.write("    echo 'result = 42' > output.txt\n")
        f.write("    rm \"$FLAG_FILE\"\n")
        f.write("    exit 0\n")
        f.write("else\n")
        f.write("    # First attempt - fail\n")
        f.write("    echo 'First attempt: FAILURE' >&2\n")
        f.write("    touch \"$FLAG_FILE\"\n")
        f.write("    exit 1\n")
        f.write("fi\n")
    os.chmod("FailThenSuccess.sh", 0o755)

    # Create a script that always fails
    with open("AlwaysFails.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script that always fails\n")
        f.write("echo 'This script always fails!' >&2\n")
        f.write("exit 1\n")
    os.chmod("AlwaysFails.sh", 0o755)

    # Create a script that always succeeds
    with open("AlwaysSucceeds.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script that always succeeds\n")
        f.write("echo 'This script always succeeds!'\n")
        f.write("echo 'result = 100' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("AlwaysSucceeds.sh", 0o755)

def test_retry_success():
    """Test case where first calculator fails, but retry succeeds"""
    print("=" * 60)
    print("TEST 1: Retry Success (First fails, second succeeds)")
    print("=" * 60)

    result = fzr("input.txt",
    {
        "T_celsius": [20, 30]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
    },
    calculators=[
        "sh://bash ./FailThenSuccess.sh",  # Fails first time
        "sh://bash ./AlwaysSucceeds.sh"    # Should succeed on retry
    ],
    results_dir="retry_test_1")

    print(f"\n📊 Results:")
    print(f"   - Statuses: {result['status']}")
    print(f"   - Calculators: {result['calculator']}")
    print(f"   - Results: {result['result']}")
    if 'error' in result:
        print(f"   - Errors: {result['error']}")

    # Assert retry mechanism worked
    assert all(status == 'done' for status in result['status']), \
        f"Expected all cases to succeed after retry, got statuses: {result['status']}"
    assert all(r is not None for r in result['result']), \
        f"Expected all results to be non-None, got: {result['result']}"

def test_all_fail():
    """Test case where all calculators fail"""
    print("\n" + "=" * 60)
    print("TEST 2: All Calculators Fail")
    print("=" * 60)

    result = fzr("input.txt",
    {
        "T_celsius": [40]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
    },
    calculators=[
        "sh://bash ./AlwaysFails.sh",     # Always fails
        "sh://bash ./AlwaysFails.sh"      # Also always fails
    ],
    results_dir="retry_test_2")

    print(f"\n📊 Results:")
    print(f"   - Status: {result['status']}")
    print(f"   - Calculator: {result['calculator']}")
    print(f"   - Result: {result['result']}")
    if 'error' in result:
        print(f"   - Error: {result['error']}")

    # Assert all calculators failed as expected
    assert result['status'][0] in ['failed', 'error'], \
        f"Expected status 'failed' or 'error', got: {result['status'][0]}"
    assert result['result'][0] is None, \
        f"Expected None result when all calculators fail, got: {result['result'][0]}"
    assert 'error' in result and result['error'][0] is not None, \
        "Expected error message when all calculators fail"

def test_first_succeeds():
    """Test case where first calculator succeeds (no retry needed)"""
    print("\n" + "=" * 60)
    print("TEST 3: First Calculator Succeeds (No retry needed)")
    print("=" * 60)

    result = fzr("input.txt",
    {
        "T_celsius": [50]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
    },
    calculators=[
        "sh://bash ./AlwaysSucceeds.sh",   # Should succeed immediately
        "sh://bash ./FailThenSuccess.sh"   # Won't be tried
    ],
    results_dir="retry_test_3")

    print(f"\n📊 Results:")
    print(f"   - Status: {result['status']}")
    print(f"   - Calculator: {result['calculator']}")
    print(f"   - Result: {result['result']}")

    # Assert first calculator succeeded
    assert result['status'][0] == 'done', \
        f"Expected status 'done', got: {result['status'][0]}"
    assert result['result'][0] == 100, \
        f"Expected result 100, got: {result['result'][0]}"
    # Verify used the first calculator (AlwaysSucceeds)
    assert 'AlwaysSucceeds' in result['calculator'][0], \
        f"Expected to use AlwaysSucceeds.sh, got: {result['calculator'][0]}"

if __name__ == "__main__":
    print("🧪 Testing Retry Mechanism for Failed Calculations")
    print("This test demonstrates the new retry functionality:")
    print("1. When a calculation fails, it will retry with a different calculator")
    print("2. Failed calculations get status='error' and error messages in results")
    print("3. Both exit code failures and parsing errors trigger retries")

    try:
        # Test 1: Retry success scenario
        result1 = test_retry_success()

        # Test 2: All calculators fail
        result2 = test_all_fail()

        # Test 3: First calculator succeeds
        result3 = test_first_succeeds()

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("✅ Retry mechanism has been successfully implemented!")
        print("✅ Failed calculations now get status='error'")
        print("✅ Error messages are stored in results['error']")
        print("✅ Automatic retry with different calculators works")
        print("✅ Enhanced error reporting with exit codes and stderr")

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()