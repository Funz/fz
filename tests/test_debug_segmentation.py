#!/usr/bin/env python3
"""
Debug how commands are segmented
"""
import sys
import re
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

def debug_command_segmentation(command: str):
    """Debug how a command gets segmented"""

    print(f"Original command: {command}")

    # Pattern for pipe separators to handle compound commands
    pipe_pattern = r'\s*(\|{1,2}|\&{1,2}|\;)\s*'

    # Split command by pipes/operators while preserving them
    command_segments = re.split(pipe_pattern, command)

    print(f"Raw segments: {command_segments}")

    resolved_segments = []

    for i, segment in enumerate(command_segments):
        segment = segment.strip()
        if not segment:
            print(f"  [{i}] Empty segment - skipping")
            continue

        # Check if this is an operator (|, ||, &&, ;)
        if re.match(r'^(\|{1,2}|\&{1,2}|\;)$', segment):
            print(f"  [{i}] Operator: '{segment}'")
            resolved_segments.append(segment)
            continue

        print(f"  [{i}] Command segment: '{segment}'")
        # We won't actually resolve here, just show what would be processed
        resolved_segments.append(f"[PROCESSED: {segment}]")

    result = ' '.join(resolved_segments)
    print(f"Final structure: {result}")
    return result

def test_segmentation():
    """Test command segmentation"""

    test_commands = [
        "cp test_input.txt copy.txt && echo 'result = 10' > output.txt",
        "cat input.txt > output.txt",
        "echo hello > temp.txt && cat temp.txt > final.txt"
    ]

    print("🔍 Testing Command Segmentation")
    print("=" * 50)

    for cmd in test_commands:
        print(f"\n{'='*50}")
        debug_command_segmentation(cmd)
        print(f"{'='*50}")

if __name__ == "__main__":
    test_segmentation()