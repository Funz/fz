#!/usr/bin/env python3
"""
Debug path resolution to understand what's happening
"""
import sys
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz.runners import resolve_all_paths_in_command

def test_command_resolution():
    """Test path resolution on various commands"""

    original_cwd = "/home/richet/Sync/Open/Funz/fz"

    test_commands = [
        "bash simple_script.sh",
        "cp test_input.txt copy.txt && echo 'result = 10' > output.txt",
        "bash scripts/sub_script.sh",
        "cat input.txt > output.txt",
        "cat data/input.txt > results/output.txt",
        "python3 script.py > output.txt",
        "echo 'hello' > temp.txt && cat temp.txt > final.txt"
    ]

    print("🔍 Testing Path Resolution Commands")
    print("=" * 60)

    for cmd in test_commands:
        print(f"\nOriginal: {cmd}")
        resolved = resolve_all_paths_in_command(cmd, original_cwd)
        print(f"Resolved: {resolved}")
        print("-" * 40)

if __name__ == "__main__":
    test_command_resolution()