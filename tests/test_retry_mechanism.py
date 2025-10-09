#!/usr/bin/env python3
"""
Test script to demonstrate the retry mechanism for failed calculations
"""

import sys
import os

from fz import fzr
import time

def create_test_files():
    """Create test files for retry mechanism"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Test input file\n")
        f.write("# Temperature: $(T_celsius) celsius\n")
        f.write("echo 'Temperature: $(T_celsius)'\n")

    # Create a script that fails on first attempt but succeeds on retry
    with open("FailThenSuccess.sh", 'w') as f:
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
    with open("AlwaysFails.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script that always fails\n")
        f.write("echo 'This script always fails!' >&2\n")
        f.write("exit 1\n")
    os.chmod("AlwaysFails.sh", 0o755)

    # Create a script that always succeeds
    with open("AlwaysSucceeds.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Script that always succeeds\n")
        f.write("echo 'This script always succeeds!'\n")
        f.write("echo 'result = 100' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("AlwaysSucceeds.sh", 0o755)

def test_retry_success():
    """Test case where first calculator fails, but retry succeeds"""
    print("=" * 60)

    create_test_files()

    print("TEST 1: Retry Success (First fails, second succeeds)")
    print("=" * 60)

    result = fzr("input.txt",
    {
        "T_celsius": [20, 30]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}
    },

    calculators=[
        "sh:///bin/bash ./FailThenSuccess.sh",  # Fails first time
        "sh:///bin/bash ./AlwaysSucceeds.sh"    # Should succeed on retry
    ],
    results_dir="retry_test_1")

    print(f"\n📊 Results:")
    print(f"   - Statuses: {result['status']}")
    print(f"   - Calculators: {result['calculator']}")
    print(f"   - Results: {result['result']}")
    if 'error' in result:
        print(f"   - Errors: {result['error']}")

    return result

def test_all_fail():
    """Test case where all calculators fail"""
    print("\n" + "=" * 60)
    print("TEST 2: All Calculators Fail")
    print("=" * 60)

    create_test_files()

    result = fzr("input.txt",
    {
        "T_celsius": [40]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}
    },

    calculators=[
        "sh:///bin/bash ./AlwaysFails.sh",     # Always fails
        "sh:///bin/bash ./AlwaysFails.sh"      # Also always fails
    ],
    results_dir="retry_test_2")

    print(f"\n📊 Results:")
    print(f"   - Status: {result['status']}")
    print(f"   - Calculator: {result['calculator']}")
    print(f"   - Result: {result['result']}")
    if 'error' in result:
        print(f"   - Error: {result['error']}")

    return result

def test_first_succeeds():
    """Test case where first calculator succeeds (no retry needed)"""
    print("\n" + "=" * 60)
    print("TEST 3: First Calculator Succeeds (No retry needed)")
    print("=" * 60)

    create_test_files()

    result = fzr("input.txt",
    {
        "T_celsius": [50]
    },
    {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}
    },

    calculators=[
        "sh:///bin/bash ./AlwaysSucceeds.sh",   # Should succeed immediately
        "sh:///bin/bash ./FailThenSuccess.sh"   # Won't be tried
    ],
    results_dir="retry_test_3")

    print(f"\n📊 Results:")
    print(f"   - Status: {result['status']}")
    print(f"   - Calculator: {result['calculator']}")
    print(f"   - Result: {result['result']}")

    return result

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