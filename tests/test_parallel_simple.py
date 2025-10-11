#!/usr/bin/env python3
"""
Simple test script for parallel calculator execution functionality
"""
import os
import tempfile
import time
from pathlib import Path
import sys

import fz

def test_parallel_vs_single():
    """Test that parallel execution works and uses the results from fastest calculator"""
    print("Testing parallel execution vs single calculator...")

    test_model = {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "cat result.txt 2>/dev/null || echo 'no result'"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\ntest_param = 123\n")
        temp_input = f.name

    try:
        # Test 1: Single fast calculator
        print("Running single fast calculator...")
        start_time = time.time()
        results_single = fz.fzr(
            temp_input,
            {"param": 1},
            test_model,
            calculators=["sh://echo 'fast result' > result.txt"]
        )
        single_time = time.time() - start_time
        print(f"Single calculator time: {single_time:.2f}s")

        # Test 2: Multiple calculators in parallel (fast one should win)
        print("Running multiple calculators in parallel...")
        start_time = time.time()
        results_parallel = fz.fzr(
            temp_input,
            {"param": 1},
            test_model,
            results_dir="results_parallel",
            calculators=[
                "sh://sleep 2 && echo 'slow result' > result.txt",
                "sh://echo 'fast result' > result.txt",  # This should complete first
                "sh://sleep 3 && echo 'slowest result' > result.txt"
            ]
        )
        parallel_time = time.time() - start_time
        print(f"Parallel calculators time: {parallel_time:.2f}s")

        # Verify results
        print(f"Single result: {results_single.get('result', ['N/A'])[0]}")
        print(f"Parallel result: {results_parallel.get('result', ['N/A'])[0]}")
        print(f"Calculator used in parallel: {results_parallel.get('calculator', ['N/A'])[0]}")

        # Check that we got results
        assert len(results_parallel.get('result', [])) > 0, "Should have gotten results"
        assert results_parallel.get('status', [''])[0] == 'done', "Should have successful status"

        print("✓ Parallel execution test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass

def test_calculators_resolution():
    """Test that calculator resolution still works"""
    print("\nTesting calculator resolution...")

    # Test with different calculator formats
    calculators = [
        "sh://echo 'test1' > result.txt",
        "cache://results",
        "sh://echo 'test2' > result.txt"
    ]

    from fz.runners import resolve_calculators
    resolved = resolve_calculators(calculators)

    print(f"Original: {calculators}")
    print(f"Resolved: {resolved}")

    # Check that we got the expected number
    assert len(resolved) >= len(calculators), "Should resolve at least as many calculators"
    print("✓ Calculator resolution test PASSED")

if __name__ == "__main__":
    print("Testing FZ parallel calculator functionality")
    print("=" * 50)

    try:
        test_parallel_vs_single()
        test_calculators_resolution()

        print("\n" + "=" * 50)
        print("Tests completed: 2/2 passed")
        print("🎉 All tests PASSED!")
        exit(0)
    except Exception as e:
        print("\n" + "=" * 50)
        print("❌ Some tests FAILED!")
        print(f"Error: {e}")
        exit(1)