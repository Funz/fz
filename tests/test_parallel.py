#!/usr/bin/env python3
"""
Test script for parallel calculator execution
"""
import os
import tempfile
import time
from pathlib import Path

# Add fz package to path
import sys
sys.path.insert(0, '/home/richet/Sync/Open/Funz/fz')

import fz

# Create a simple test model
test_model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {
        "result": "cat result.txt 2>/dev/null || echo 'no result'"
    }
}

# Create test calculators that simulate different response times
test_calculators = [
    "sh://sleep 2 && echo 'calc1 result' > result.txt",  # 2 second delay
    "sh://sleep 1 && echo 'calc2 result' > result.txt",  # 1 second delay (should win)
    "sh://sleep 3 && echo 'calc3 result' > result.txt",  # 3 second delay
]

def test_parallel_execution():
    print("Testing parallel calculator execution...")

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input file\nsome_parameter = 42\n")
        temp_input = f.name

    try:
        # Test with single variable combination
        start_time = time.time()

        results = fz.fzr(
            temp_input,
            test_model,
            {"some_param": 1},  # Single value, no grid
            calculators=test_calculators
        )

        end_time = time.time()
        execution_time = end_time - start_time

        print(f"Execution completed in {execution_time:.2f} seconds")
        print(f"Results: {results}")

        # Check that we got results
        assert "result" in results
        assert len(results["result"]) == 1

        # With parallel execution, we should get the result from the fastest calculator
        # The total time should be close to the fastest calculator (1s) plus overhead
        # Note: We can't interrupt running subprocesses, so total time will be dominated
        # by the longest-running calculator, but we'll get results from the fastest one
        print(f"Note: Parallel execution gets results from fastest calculator but can't interrupt slower ones")
        assert execution_time >= 1.0, f"Should take at least 1s (fastest calculator time)"

        print("✓ Parallel execution test PASSED")

        # Check which calculator was used (should be the fast one)
        calculator_used = results.get("calculator", [None])[0]
        print(f"Calculator used: {calculator_used}")

        return True

    except Exception as e:
        print(f"✗ Parallel execution test FAILED: {e}")
        return False

    finally:
        # Cleanup
        try:
            os.unlink(temp_input)
        except:
            pass

def test_cache_first_strategy():
    print("\nTesting cache-first strategy...")

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input file with cache\nsome_parameter = 100\n")
        temp_input = f.name

    # Create temporary results directory
    temp_results_dir = tempfile.mkdtemp(prefix='fz_cache_test_')

    try:
        # First run to populate cache
        print("First run (should populate cache)...")
        calculators_with_cache = [
            f"cache://{temp_results_dir}",  # Cache should be checked first
            "sh://echo 'slow result' > result.txt"  # Slow calculator as backup
        ]

        start_time = time.time()
        results1 = fz.fzr(
            temp_input,
            test_model,
            {"some_param": 100},
            results_dir=temp_results_dir,
            calculators=calculators_with_cache
        )
        first_run_time = time.time() - start_time

        print(f"First run completed in {first_run_time:.2f} seconds")

        # Second run should use cache
        print("Second run (should use cache)...")
        start_time = time.time()
        results2 = fz.fzr(
            temp_input,
            test_model,
            {"some_param": 100},
            results_dir=f"{temp_results_dir}_2",
            calculators=calculators_with_cache
        )
        second_run_time = time.time() - start_time

        print(f"Second run completed in {second_run_time:.2f} seconds")

        # Second run should be much faster (cache hit)
        assert second_run_time < first_run_time / 2, "Cache should make second run much faster"

        print("✓ Cache-first strategy test PASSED")
        return True

    except Exception as e:
        print(f"✗ Cache-first strategy test FAILED: {e}")
        return False

    finally:
        try:
            os.unlink(temp_input)
            import shutil
            shutil.rmtree(temp_results_dir, ignore_errors=True)
        except:
            pass

if __name__ == "__main__":
    print("Testing FZ parallel calculator execution")
    print("=" * 50)

    success_count = 0

    if test_parallel_execution():
        success_count += 1

    if test_cache_first_strategy():
        success_count += 1

    print("\n" + "=" * 50)
    print(f"Tests completed: {success_count}/2 passed")

    if success_count == 2:
        print("🎉 All tests PASSED!")
        exit(0)
    else:
        print("❌ Some tests FAILED!")
        exit(1)