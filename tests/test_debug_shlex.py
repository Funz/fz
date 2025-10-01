#!/usr/bin/env python3
"""
Debug shlex parsing to understand what's happening
"""
import shlex

def test_shlex_parsing():
    """Test how shlex parses commands with redirections"""

    test_commands = [
        "cp test_input.txt copy.txt && echo 'result = 10' > output.txt",
        "cat input.txt > output.txt",
        "echo hello > temp.txt && cat temp.txt > final.txt"
    ]

    print("🔍 Testing shlex.split behavior")
    print("=" * 50)

    for cmd in test_commands:
        print(f"\nOriginal: {cmd}")
        try:
            parts = shlex.split(cmd)
            print(f"Parts: {parts}")
            for i, part in enumerate(parts):
                print(f"  [{i}]: '{part}'")
        except ValueError as e:
            print(f"Error: {e}")
        print("-" * 30)

if __name__ == "__main__":
    test_shlex_parsing()