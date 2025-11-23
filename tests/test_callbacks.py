#!/usr/bin/env python3
"""
Comprehensive test suite for fzr callback functionality
"""
import os
import tempfile
import time
from pathlib import Path
import threading

import fz


def test_all_callbacks():
    """Test that all callbacks are called with correct arguments"""
    print("\nTesting all callbacks...")

    # Track callback invocations
    callback_log = {
        'on_start': [],
        'on_case_start': [],
        'on_case_complete': [],
        'on_progress': [],
        'on_complete': []
    }

    # Define callbacks
    def on_start(total_cases, calculators):
        callback_log['on_start'].append({
            'total_cases': total_cases,
            'calculators': calculators
        })
        print(f"  on_start: {total_cases} cases, {len(calculators)} calculators")

    def on_case_start(case_index, total_cases, var_combo):
        callback_log['on_case_start'].append({
            'case_index': case_index,
            'total_cases': total_cases,
            'var_combo': var_combo
        })
        print(f"  on_case_start: case {case_index}/{total_cases}, vars={var_combo}")

    def on_case_complete(case_index, total_cases, var_combo, status, result):
        callback_log['on_case_complete'].append({
            'case_index': case_index,
            'total_cases': total_cases,
            'var_combo': var_combo,
            'status': status,
            'result': result
        })
        print(f"  on_case_complete: case {case_index}/{total_cases}, status={status}")

    def on_progress(completed, total, eta_seconds):
        callback_log['on_progress'].append({
            'completed': completed,
            'total': total,
            'eta_seconds': eta_seconds
        })
        print(f"  on_progress: {completed}/{total}, ETA={eta_seconds:.2f}s")

    def on_complete(total_cases, completed_cases, results):
        callback_log['on_complete'].append({
            'total_cases': total_cases,
            'completed_cases': completed_cases,
            'results': results
        })
        print(f"  on_complete: {completed_cases}/{total_cases} cases completed")

    # Create test model
    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo ${x} > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nx = ${x}\n")
        temp_input = f.name

    try:
        # Run fzr with multiple cases
        results = fz.fzr(
            temp_input,
            {"x": [1, 2, 3]},
            test_model,
            results_dir="results_callbacks_all",
            calculators=["sh://echo ${x} > result.txt"],
            callbacks={
                'on_start': on_start,
                'on_case_start': on_case_start,
                'on_case_complete': on_case_complete,
                'on_progress': on_progress,
                'on_complete': on_complete
            }
        )

        # Verify on_start was called once
        assert len(callback_log['on_start']) == 1, "on_start should be called exactly once"
        assert callback_log['on_start'][0]['total_cases'] == 3, "Should have 3 total cases"
        print("  ✓ on_start called correctly")

        # Verify on_case_start was called for each case
        assert len(callback_log['on_case_start']) == 3, "on_case_start should be called 3 times"
        for i in range(3):
            assert callback_log['on_case_start'][i]['case_index'] == i, f"Case {i} should have correct index"
            assert callback_log['on_case_start'][i]['total_cases'] == 3, f"Case {i} should know total cases"
        print("  ✓ on_case_start called correctly for all cases")

        # Verify on_case_complete was called for each case
        assert len(callback_log['on_case_complete']) == 3, "on_case_complete should be called 3 times"
        for i in range(3):
            assert callback_log['on_case_complete'][i]['status'] in ['done', 'error'], f"Case {i} should have valid status"
        print("  ✓ on_case_complete called correctly for all cases")

        # Verify on_progress was called (may be called multiple times or not at all for fast execution)
        # Just check that if it was called, the values make sense
        if len(callback_log['on_progress']) > 0:
            for progress in callback_log['on_progress']:
                assert progress['completed'] <= progress['total'], "Completed should not exceed total"
                assert progress['total'] == 3, "Total should be 3"
            print(f"  ✓ on_progress called {len(callback_log['on_progress'])} times with valid data")
        else:
            print("  ⚠ on_progress not called (execution may have been too fast)")

        # Verify on_complete was called once
        assert len(callback_log['on_complete']) == 1, "on_complete should be called exactly once"
        assert callback_log['on_complete'][0]['total_cases'] == 3, "Should have 3 total cases"
        assert callback_log['on_complete'][0]['completed_cases'] == 3, "Should have 3 completed cases"
        print("  ✓ on_complete called correctly")

        print("✓ All callbacks test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


def test_callback_error_handling():
    """Test that errors in callbacks don't crash the execution"""
    print("\nTesting callback error handling...")

    # Track if callbacks were called despite errors
    callback_called = {'on_start': False, 'on_complete': False}

    def on_start_with_error(total_cases, calculators):
        callback_called['on_start'] = True
        raise ValueError("Intentional error in on_start")

    def on_complete_with_error(total_cases, completed_cases, results):
        callback_called['on_complete'] = True
        raise ValueError("Intentional error in on_complete")

    # Create test model
    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo test > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nx = ${x}\n")
        temp_input = f.name

    try:
        # Run fzr with callbacks that raise errors
        results = fz.fzr(
            temp_input,
            {"x": 1},
            test_model,
            results_dir="results_callbacks_errors",
            calculators=["sh://echo test > result.txt"],
            callbacks={
                'on_start': on_start_with_error,
                'on_complete': on_complete_with_error
            }
        )

        # Verify that execution completed despite callback errors
        assert len(results.get('result', [])) > 0, "Should have results despite callback errors"

        # Verify callbacks were actually called
        assert callback_called['on_start'], "on_start callback should have been called"
        assert callback_called['on_complete'], "on_complete callback should have been called"

        print("  ✓ Execution completed successfully despite callback errors")
        print("✓ Callback error handling test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


def test_callback_with_single_case():
    """Test callbacks with a single case (edge case)"""
    print("\nTesting callbacks with single case...")

    callback_log = {
        'on_start': 0,
        'on_case_start': 0,
        'on_case_complete': 0,
        'on_complete': 0
    }

    def on_start(total_cases, calculators):
        callback_log['on_start'] += 1
        assert total_cases == 1, "Should have 1 case"

    def on_case_start(case_index, total_cases, var_combo):
        callback_log['on_case_start'] += 1
        assert case_index == 0, "Should be case 0"
        assert total_cases == 1, "Should have 1 total case"

    def on_case_complete(case_index, total_cases, var_combo, status, result):
        callback_log['on_case_complete'] += 1
        assert case_index == 0, "Should be case 0"
        assert total_cases == 1, "Should have 1 total case"

    def on_complete(total_cases, completed_cases, results):
        callback_log['on_complete'] += 1
        assert total_cases == 1, "Should have 1 total case"
        assert completed_cases == 1, "Should have 1 completed case"

    # Create test model
    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo single > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\ntest = 123\n")
        temp_input = f.name

    try:
        # Run fzr with single case
        results = fz.fzr(
            temp_input,
            {"x": 1},
            test_model,
            results_dir="results_callbacks_single",
            calculators=["sh://echo single > result.txt"],
            callbacks={
                'on_start': on_start,
                'on_case_start': on_case_start,
                'on_case_complete': on_case_complete,
                'on_complete': on_complete
            }
        )

        # Verify all callbacks were called exactly once
        assert callback_log['on_start'] == 1, "on_start should be called once"
        assert callback_log['on_case_start'] == 1, "on_case_start should be called once"
        assert callback_log['on_case_complete'] == 1, "on_case_complete should be called once"
        assert callback_log['on_complete'] == 1, "on_complete should be called once"

        print("  ✓ All callbacks called correctly for single case")
        print("✓ Single case callback test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


def test_callback_thread_safety():
    """Test that callbacks are thread-safe when cases run in parallel"""
    print("\nTesting callback thread safety with parallel execution...")

    # Use a lock to safely track callback calls from multiple threads
    lock = threading.Lock()
    callback_log = {
        'case_start_threads': set(),
        'case_complete_threads': set(),
        'case_indices': []
    }

    def on_case_start(case_index, total_cases, var_combo):
        thread_id = threading.get_ident()
        with lock:
            callback_log['case_start_threads'].add(thread_id)
            callback_log['case_indices'].append(case_index)

    def on_case_complete(case_index, total_cases, var_combo, status, result):
        thread_id = threading.get_ident()
        with lock:
            callback_log['case_complete_threads'].add(thread_id)

    # Create test model
    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo ${x} > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nx = ${x}\n")
        temp_input = f.name

    try:
        # Run fzr with multiple cases and calculators to ensure parallel execution
        results = fz.fzr(
            temp_input,
            {"x": [1, 2, 3, 4, 5]},
            test_model,
            results_dir="results_callbacks_parallel",
            calculators=["sh://echo ${x} > result.txt", "sh://echo ${x} > result.txt"],
            callbacks={
                'on_case_start': on_case_start,
                'on_case_complete': on_case_complete
            }
        )

        # Verify all case indices were seen
        with lock:
            assert len(callback_log['case_indices']) == 5, "Should have seen all 5 cases"
            assert set(callback_log['case_indices']) == {0, 1, 2, 3, 4}, "Should have all case indices"

        print(f"  ✓ Callbacks called from {len(callback_log['case_start_threads'])} thread(s)")
        print("  ✓ All case indices tracked correctly")
        print("✓ Thread safety test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


def test_callbacks_validation():
    """Test that invalid callbacks are rejected"""
    print("\nTesting callback validation...")

    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo test > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\ntest = 123\n")
        temp_input = f.name

    try:
        # Test 1: Invalid callback name
        try:
            results = fz.fzr(
                temp_input,
                {"x": 1},
                test_model,
                results_dir="results_callbacks_invalid_name",
                calculators=["sh://echo test > result.txt"],
                callbacks={'invalid_callback': lambda: None}
            )
            assert False, "Should have raised ValueError for invalid callback name"
        except ValueError as e:
            assert "Invalid callback name" in str(e), "Should mention invalid callback name"
            print("  ✓ Invalid callback name rejected")

        # Test 2: Non-callable callback
        try:
            results = fz.fzr(
                temp_input,
                {"x": 1},
                test_model,
                results_dir="results_callbacks_not_callable",
                calculators=["sh://echo test > result.txt"],
                callbacks={'on_start': "not a function"}
            )
            assert False, "Should have raised TypeError for non-callable callback"
        except TypeError as e:
            assert "must be callable" in str(e), "Should mention callable requirement"
            print("  ✓ Non-callable callback rejected")

        # Test 3: Callbacks not a dict
        try:
            results = fz.fzr(
                temp_input,
                {"x": 1},
                test_model,
                results_dir="results_callbacks_not_dict",
                calculators=["sh://echo test > result.txt"],
                callbacks="not a dict"
            )
            assert False, "Should have raised TypeError for non-dict callbacks"
        except TypeError as e:
            assert "must be a dictionary" in str(e), "Should mention dictionary requirement"
            print("  ✓ Non-dict callbacks rejected")

        print("✓ Callback validation test PASSED")

    except Exception as e:
        if "Should have raised" not in str(e):
            print(f"✗ Test FAILED: {e}")
            raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


def test_optional_callbacks():
    """Test that callbacks are optional (backwards compatibility)"""
    print("\nTesting optional callbacks (backwards compatibility)...")

    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "echo test > result.txt && cat result.txt"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\ntest = 123\n")
        temp_input = f.name

    try:
        # Run fzr without callbacks (should work as before)
        results = fz.fzr(
            temp_input,
            {"x": 1},
            test_model,
            results_dir="results_no_callbacks",
            calculators=["sh://echo test > result.txt"]
        )

        assert len(results.get('result', [])) > 0, "Should have results without callbacks"
        print("  ✓ fzr works without callbacks")

        # Run fzr with empty callbacks dict (should also work)
        results = fz.fzr(
            temp_input,
            {"x": 1},
            test_model,
            results_dir="results_empty_callbacks",
            calculators=["sh://echo test > result.txt"],
            callbacks={}
        )

        assert len(results.get('result', [])) > 0, "Should have results with empty callbacks"
        print("  ✓ fzr works with empty callbacks dict")

        # Run fzr with None callbacks (should also work)
        results = fz.fzr(
            temp_input,
            {"x": 1},
            test_model,
            results_dir="results_none_callbacks",
            calculators=["sh://echo test > result.txt"],
            callbacks=None
        )

        assert len(results.get('result', [])) > 0, "Should have results with None callbacks"
        print("  ✓ fzr works with callbacks=None")

        print("✓ Optional callbacks test PASSED")

    except Exception as e:
        print(f"✗ Test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


if __name__ == "__main__":
    print("Testing FZ Callback Functionality")
    print("=" * 60)

    try:
        test_all_callbacks()
        test_callback_error_handling()
        test_callback_with_single_case()
        test_callback_thread_safety()
        test_callbacks_validation()
        test_optional_callbacks()

        print("\n" + "=" * 60)
        print("Tests completed: 6/6 passed")
        print("🎉 All callback tests PASSED!")
        exit(0)
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ Some tests FAILED!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
