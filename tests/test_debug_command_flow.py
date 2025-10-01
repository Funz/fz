#!/usr/bin/env python3
"""
Debug command flow to see where the tracking gets lost
"""

import os
import sys
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_debug_command_flow():
    """Debug where command tracking gets lost"""

    # Create test files
    with open('debug_script.sh', 'w') as f:
        f.write('#!/bin/bash\necho "Debug script"\necho "result = 789" > debug_output.txt\n')
    os.chmod('debug_script.sh', 0o755)

    with open('debug_input.txt', 'w') as f:
        f.write('debug data\n')

    print("🔍 Debugging Command Flow")
    print("=" * 50)

    try:
        result = fzr(
            input_path="debug_input.txt",
            model={"output": {"value": "echo 'Debug test'"}},
            varvalues={},
            calculators=["sh://bash debug_script.sh"],
            resultsdir="debug_result"
        )

        print(f"\nResult keys: {list(result.keys())}")
        print(f"Status: {result.get('status', 'missing')}")
        print(f"Calculator: {result.get('calculator', 'missing')}")
        print(f"Command: {result.get('command', 'missing')}")

        # Let's also check if there are any values in the list
        if 'command' in result and result['command']:
            print(f"Command list: {result['command']}")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

    finally:
        # Cleanup
        for f in ['debug_script.sh', 'debug_input.txt', 'debug_output.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_debug_command_flow()