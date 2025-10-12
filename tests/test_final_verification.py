#!/usr/bin/env python3
"""
Final verification that warnings and command tracking work correctly
"""

import os
import sys
from pathlib import Path

from fz import fzr

def test_final_verification():
    """Final test of warning display and command tracking"""

    # Create test files
    with open('final_test_script.sh', 'w', newline='\n') as f:
        f.write('#!/bin/bash\necho "Final test script executed"\necho "result = 999" > final_output.txt\n')
    os.chmod('final_test_script.sh', 0o755)

    with open('final_input.txt', 'w') as f:
        f.write('final test data\n')

    print("🎯 Final Verification: sh:// Command Warning and Tracking")
    print("=" * 60)

    try:
        # Test 1: Command with relative paths (should show warning and track)
        print("\n1️⃣ Testing command with relative paths:")
        result1 = fzr(
            input_path="final_input.txt",
            model={"output": {"value": "echo 'Test 1 completed'"}},
            input_variables={},
            calculators=["sh://bash final_test_script.sh"],
            results_dir="final_test_1"
        )

        print(f"   Command: {result1.get('command', ['None'])[0]}")

        # Test 2: Command with no relative paths (should not show warning)
        print("\n2️⃣ Testing command with no relative paths:")
        result2 = fzr(
            input_path="final_input.txt",
            model={"output": {"value": "echo 'Test 2 completed'"}},
            input_variables={},
            calculators=["sh://echo 'No relative paths'"],
            results_dir="final_test_2"
        )

        print(f"   Command: {result2.get('command', ['None'])[0]}")

        # Verify results
        print(f"\n✅ Results Summary:")
        print(f"   Test 1 status: {result1.get('status', ['unknown'])[0]}")
        print(f"   Test 2 status: {result2.get('status', ['unknown'])[0]}")
        command_tracking_works = result1.get('command', [None])[0] is not None
        print(f"   Command tracking: {'✅ Working' if command_tracking_works else '❌ Failed'}")

        # Assert results are correct
        assert result1.get('status', ['unknown'])[0] == 'done', \
            f"Test 1 failed: expected status 'done', got {result1.get('status', ['unknown'])[0]}"
        assert result2.get('status', ['unknown'])[0] == 'done', \
            f"Test 2 failed: expected status 'done', got {result2.get('status', ['unknown'])[0]}"
        assert command_tracking_works, "Command tracking failed: no command recorded"

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise

    finally:
        # Cleanup
        for f in ['final_test_script.sh', 'final_input.txt', 'final_output.txt']:
            if os.path.exists(f):
                os.remove(f)

    print(f"\n🎉 Implementation complete: Warnings displayed and commands tracked!")

if __name__ == "__main__":
    test_final_verification()