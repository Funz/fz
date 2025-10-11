#!/usr/bin/env python3
"""
Debug path resolution step by step
"""
import sys
import os
from pathlib import Path

from fz.runners import _resolve_paths_in_segment

def test_segment_resolution():
    """Test path resolution on individual segments"""

    # Use project root (parent of tests directory)
    original_cwd = str(Path(__file__).parent.parent.absolute())

    test_segments = [
        "cp test_input.txt copy.txt",
        "echo 'result = 10' > output.txt",
        "cat input.txt > output.txt"
    ]

    print("🔍 Testing Segment Path Resolution")
    print("=" * 50)

    results = []
    for segment in test_segments:
        print(f"\nSegment: {segment}")
        resolved = _resolve_paths_in_segment(segment, original_cwd)
        print(f"Resolved: {resolved}")
        results.append(resolved is not None)
        print("-" * 30)

    # Assert all segments were resolved
    assert all(results), "Some segments failed to resolve"

if __name__ == "__main__":
    test_segment_resolution()