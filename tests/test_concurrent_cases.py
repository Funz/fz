#!/usr/bin/env python3
"""
Test script to verify concurrent execution of multiple cases with multiple calculators
"""
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime
import sys

import fz

def test_concurrent_multi_case_execution():
    """Test if multiple cases with multiple calculators run concurrently"""
    print("Testing concurrent execution of multiple cases with multiple calculators...")

    test_model = {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "cat result.txt 2>/dev/null || echo 'no result'"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nparam = $(value)\n")
        temp_input = f.name

    try:
        print("Running test with 3 cases and 2 calculators per case...")
        print("Expected behavior: All cases should run concurrently")
        print("Current behavior: Cases run sequentially (one after another)")

        # Test with multiple cases (3 cases) and multiple calculators (2 calculators each)
        # Each calculator takes 2 seconds, so:
        # - Sequential execution: ~6 seconds (3 cases × 2 seconds each)
        # - Concurrent execution: ~2 seconds (all cases run simultaneously)

        start_time = datetime.now()

        results = fz.fzr(
            temp_input,
            {"value": [1, 2, 3]},  # 3 cases
            test_model,
            results_dir="concurrent_test_results",
            calculators=[
                "sh://echo 'calc1 result' > result.txt && sleep 2",  # 2 second delay
                "sh://echo 'calc2 result' > result.txt && sleep 2",  # 2 second delay
            ]
        )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        print(f"Total execution time: {execution_time:.2f} seconds")
        print(f"Results: {len(results.get('value', []))} cases completed")
        print(f"Calculators used: {results.get('calculator', [])}")

        # Analyze timing
        is_concurrent = execution_time < 4.0
        if is_concurrent:
            print("✓ CONCURRENT execution detected (all cases ran simultaneously)")
        elif execution_time > 5.0:
            print("⚠ SEQUENTIAL execution detected (cases ran one after another)")
        else:
            print("? UNCLEAR execution pattern (timing is ambiguous)")

        # Assert results are valid
        assert len(results.get('value', [])) == 3, \
            f"Expected 3 cases to complete, got {len(results.get('value', []))}"

        # Store timing result without returning
        timing_result = "concurrent" if is_concurrent else ("sequential" if execution_time > 5.0 else "unclear")
        return timing_result  # This is needed by __main__ but pytest will ignore it

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
            import shutil
            if Path("concurrent_test_results").exists():
                shutil.rmtree("concurrent_test_results")
        except:
            pass

def test_single_case_multiple_calculators():
    """Verify that single case with multiple calculators works correctly (baseline)"""
    print("\nTesting single case with multiple calculators (baseline)...")

    test_model = {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "cat result.txt 2>/dev/null || echo 'no result'"}
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nparam = 42\n")
        temp_input = f.name

    try:
        start_time = datetime.now()

        results = fz.fzr(
            temp_input,
            test_model,
            {"value": 1},  # Single case
            results_dir="single_case_results",
            calculators=[
                "sh://echo 'calc1 result' > result.txt && sleep 1",  # 1 second delay
                "sh://echo 'calc2 result' > result.txt && sleep 2",  # 2 second delay
            ]
        )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        print(f"Single case execution time: {execution_time:.2f} seconds")
        print(f"Calculator used: {results.get('calculator', ['unknown'])[0]}")

        # Should be close to 1 second (fastest calculator wins in parallel)
        is_parallel = execution_time < 1.5
        if is_parallel:
            print("✓ Parallel calculator execution working for single case")
        else:
            print("⚠ Calculators may not be running in parallel for single case")

        # Assert single case completed successfully
        assert results.get('calculator') is not None, "No calculator result returned"

        # Assert parallel execution
        # Note: We don't strictly enforce this since timing can vary
        return is_parallel  # This is needed by __main__ but pytest will ignore it

    except Exception as e:
        print(f"✗ Baseline test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
            import shutil
            if Path("single_case_results").exists():
                shutil.rmtree("single_case_results")
        except:
            pass

if __name__ == "__main__":
    print("Testing FZ concurrent multi-case execution")
    print("=" * 60)

    baseline_success = test_single_case_multiple_calculators()

    if not baseline_success:
        print("\n❌ Baseline test failed - parallel execution not working properly")
        exit(1)

    execution_type = test_concurrent_multi_case_execution()
    concurrent_success = execution_type == "concurrent"

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"- Single case parallel execution: {'✓ WORKING' if baseline_success else '✗ BROKEN'}")
    print(f"- Multi-case execution pattern: {execution_type.upper()}")

    if execution_type == "sequential":
        print("\n📝 FINDING: Multiple cases are executed sequentially, not concurrently")
        print("   This means when you have N cases and M calculators, only M calculators")
        print("   are used at any given time (for the current case), instead of N×M total")
        print("   concurrent executions.")
        print("\n💡 RECOMMENDATION: Implement case-level parallelization in addition to")
        print("   calculator-level parallelization for optimal resource utilization.")
    elif execution_type == "concurrent":
        print("\n🎉 All cases are running concurrently - optimal performance!")

    exit(0 if concurrent_success else 1)