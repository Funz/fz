#!/usr/bin/env python3
"""
Master test runner for all example tests from .claude/examples.md
Runs all example test suites and provides summary
"""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

def run_test_file(test_file):
    """Run a single test file and return success status"""
    print(f"\n🚀 Running {test_file}")
    print("-" * 60)

    try:
        # Run the test file as a subprocess
        result = subprocess.run([sys.executable, test_file],
                              capture_output=True,
                              text=True,
                              cwd=Path(__file__).parent)

        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {test_file} PASSED")
            return True
        else:
            print(f"❌ {test_file} FAILED (exit code: {result.returncode})")
            return False

    except Exception as e:
        print(f"❌ {test_file} FAILED with exception: {e}")
        return False

def main():
    """Run all example tests"""
    print("🧪 Funz Examples Test Suite")
    print("=" * 60)
    print("Running all example tests from .claude/examples.md")

    # List of test files to run
    test_files = [
        "test_examples_perfectgaz.py",
        "test_examples_modelica.py",
        "test_examples_telemac.py",
        "test_examples_advanced.py"
    ]

    results = {}

    # Run each test file
    for test_file in test_files:
        if os.path.exists(test_file):
            results[test_file] = run_test_file(test_file)
        else:
            print(f"⚠️ Test file {test_file} not found, skipping...")
            results[test_file] = False

    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = 0
    total = 0

    for test_file, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_file:<35} {status}")
        if success:
            passed += 1
        total += 1

    print("-" * 60)
    print(f"Results: {passed}/{total} test suites passed")

    if passed == total:
        print("\n🎉 All example tests passed!")
        return 0
    else:
        print(f"\n💥 {total - passed} test suite(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)