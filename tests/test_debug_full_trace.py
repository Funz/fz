#!/usr/bin/env python3
"""
Full trace of path resolution
"""
import sys
import re
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz.runners import _resolve_paths_in_segment

def debug_full_resolution(command: str, original_cwd: str):
    """Debug the full resolution process"""

    print(f"Original command: {command}")
    print(f"Working from: {original_cwd}")

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
            print(f"  [{i}] Operator: '{segment}' - preserving")
            resolved_segments.append(segment)
            continue

        print(f"\n  [{i}] Processing segment: '{segment}'")
        resolved_segment, was_changed = _resolve_paths_in_segment(segment, original_cwd)
        print(f"       Result: '{resolved_segment}' (changed: {was_changed})")
        resolved_segments.append(resolved_segment)

    result = ' '.join(resolved_segments)
    print(f"\nFinal result: {result}")
    return result

def test_full_trace():
    """Test full trace of resolution"""

    original_cwd = "/home/richet/Sync/Open/Funz/fz"

    test_commands = [
        "cp test_input.txt copy.txt && echo 'result = 10' > output.txt",
        "cat input.txt > output.txt"
    ]

    print("🔍 Full Trace of Path Resolution")
    print("=" * 60)

    for cmd in test_commands:
        print(f"\n{'='*60}")
        debug_full_resolution(cmd, original_cwd)
        print(f"{'='*60}")

if __name__ == "__main__":
    test_full_trace()