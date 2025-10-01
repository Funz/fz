#!/usr/bin/env python3
"""
Debug path resolution step by step
"""
import sys
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz.runners import _resolve_paths_in_segment

def test_segment_resolution():
    """Test path resolution on individual segments"""

    original_cwd = "/home/richet/Sync/Open/Funz/fz"

    test_segments = [
        "cp test_input.txt copy.txt",
        "echo 'result = 10' > output.txt",
        "cat input.txt > output.txt"
    ]

    print("🔍 Testing Segment Path Resolution")
    print("=" * 50)

    for segment in test_segments:
        print(f"\nSegment: {segment}")
        resolved = _resolve_paths_in_segment(segment, original_cwd)
        print(f"Resolved: {resolved}")
        print("-" * 30)

if __name__ == "__main__":
    test_segment_resolution()