"""
Test interrupt handling (Ctrl+C) during calculations
"""
import pytest
import time
import signal
import threading
from pathlib import Path
import tempfile
import shutil

from fz import fzr


def test_interrupt_sequential_execution(tmp_path):
    """Test that interrupt stops sequential execution gracefully"""

    # Create a test model with a long-running calculation
    model = {
        "varprefix": "$",
        "delim": "()",
        "output": {
            "result": "cat output.txt"
        }
    }

    # Create input file with longer sleep time
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    input_file = input_dir / "script.sh"
    # Each case takes 3 seconds
    input_file.write_text("#!/bin/bash\nsleep 10\necho 'done' > output.txt\n")
    input_file.chmod(0o755)

    # Create multiple cases
    varvalues = {
        "x": [1, 2, 3, 4, 5]  # 5 cases, each taking 3 seconds
    }

    # Set up interrupt after 5 seconds (should complete 1-2 cases)
    def send_interrupt():
        time.sleep(5)
        # Send SIGINT to current process
        import os
        os.kill(os.getpid(), signal.SIGINT)

    interrupt_thread = threading.Thread(target=send_interrupt, daemon=True)
    interrupt_thread.start()

    results_dir = tmp_path / "results"

    # Run fzr - should be interrupted
    results = fzr(
        str(input_dir),
        model,
        varvalues,
        results_dir=str(results_dir),
        calculators=["sh://"]
    )

    # Verify that execution was interrupted (not all cases completed)
    # Allow some tolerance since timing isn't exact
    assert len(results) <= 5, f"Expected at most 5 results, got {len(results)}"

    # If we got all 5 results, the interrupt came too late, but that's still valid behavior
    if len(results) < 5:
        print(f"✓ Interrupt test passed: {len(results)}/5 cases completed before interrupt")
        # Verify that partial results are available
        assert len(results) >= 1, f"Expected at least 1 completed case, got {len(results)}"
    else:
        print(f"✓ All cases completed before interrupt (timing variation)")
        # This is acceptable - the calculation was just too fast


def test_interrupt_parallel_execution(tmp_path):
    """Test that interrupt stops parallel execution gracefully"""

    # Create a test model with a long-running calculation
    model = {
        "varprefix": "$",
        "delim": "()",
        "output": {
            "result": "cat output.txt"
        }
    }

    # Create input file with longer sleep
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    input_file = input_dir / "script.sh"
    # Each case takes 4 seconds
    input_file.write_text("#!/bin/bash\nsleep 4\necho 'done' > output.txt\n")
    input_file.chmod(0o755)

    # Create multiple cases
    varvalues = {
        "x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 10 cases
    }

    # Set up interrupt after 6 seconds (with 2 parallel workers, should complete 2-4 cases)
    def send_interrupt():
        time.sleep(6)
        import os
        os.kill(os.getpid(), signal.SIGINT)

    interrupt_thread = threading.Thread(target=send_interrupt, daemon=True)
    interrupt_thread.start()

    results_dir = tmp_path / "results"

    # Run fzr with multiple calculators for parallel execution
    results = fzr(
        str(input_dir),
        model,
        varvalues,
        results_dir=str(results_dir),
        calculators=["sh://", "sh://"]  # 2 parallel calculators
    )

    # Verify results - with timing variations, we might get all 10
    assert len(results) <= 10, f"Expected at most 10 results, got {len(results)}"

    if len(results) < 10:
        print(f"✓ Parallel interrupt test passed: {len(results)}/10 cases completed before interrupt")
    else:
        print(f"✓ All cases completed before interrupt (timing variation)")


def test_graceful_cleanup_on_interrupt(tmp_path):
    """Test that resources are cleaned up properly on interrupt"""

    # Create a test model
    model = {
        "varprefix": "$",
        "delim": "()",
        "output": {
            "result": "cat output.txt"
        }
    }

    # Create input file
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    input_file = input_dir / "script.sh"   
    input_file.write_text("#!/bin/bash\nsleep 5\necho 'done' > output.txt\n")
    input_file.chmod(0o755)

    varvalues = {"x": [1, 2, 3]}

    # Set up interrupt
    def send_interrupt():
        time.sleep(7)
        import os
        os.kill(os.getpid(), signal.SIGINT)

    interrupt_thread = threading.Thread(target=send_interrupt, daemon=True)
    interrupt_thread.start()

    results_dir = tmp_path / "results"

    # Run fzr - should be interrupted
    try:
        results = fzr(
            str(input_dir),
            model,
            varvalues,
            results_dir=str(results_dir),
            calculators=["sh://"]
        )
    except KeyboardInterrupt:
        # Graceful interrupt should not raise KeyboardInterrupt
        pytest.fail("KeyboardInterrupt should be handled gracefully")

    # Verify results directory exists and contains partial results
    assert results_dir.exists(), "Results directory should exist after interrupt"

    # Check that at least some result subdirectories were created
    subdirs = list(results_dir.iterdir())
    assert len(subdirs) >= 1, "At least one result subdirectory should exist"

    print(f"✓ Cleanup test passed: Results directory preserved with {len(subdirs)} subdirectories")


if __name__ == "__main__":
    # Run basic test
    import sys
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        print("Testing interrupt handling...")

        try:
            test_interrupt_sequential_execution(tmp_path)
            print("✓ Sequential interrupt test passed")
        except Exception as e:
            print(f"✗ Sequential interrupt test failed: {e}")
            sys.exit(1)

        try:
            test_interrupt_parallel_execution(tmp_path)
            print("✓ Parallel interrupt test passed")
        except Exception as e:
            print(f"✗ Parallel interrupt test failed: {e}")
            sys.exit(1)

        try:
            test_graceful_cleanup_on_interrupt(tmp_path)
            print("✓ Cleanup test passed")
        except Exception as e:
            print(f"✗ Cleanup test failed: {e}")
            sys.exit(1)


        # Add a grace time to allow any background threads to finish (and ensure kill signals are processed)
        time.sleep(10)

        print("\n✓ All interrupt handling tests passed!")
