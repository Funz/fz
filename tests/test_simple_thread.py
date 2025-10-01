#!/usr/bin/env python3
"""
Simple test to verify ThreadPoolExecutor behavior
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

def task(name, duration):
    print(f"Task {name} starting at {datetime.now().strftime('%H:%M:%S.%f')}")
    time.sleep(duration)
    print(f"Task {name} completed at {datetime.now().strftime('%H:%M:%S.%f')}")
    return f"Result from {name}"

def test_thread_pool():
    print("Testing ThreadPoolExecutor with as_completed...")

    tasks = [
        ("Fast", 1),    # Should complete first
        ("Slow", 2),    # Should complete second
    ]

    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit all tasks
        future_to_name = {
            executor.submit(task, name, duration): name
            for name, duration in tasks
        }

        print(f"All tasks submitted at {start_time.strftime('%H:%M:%S.%f')}")

        # Process as they complete
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            result = future.result()
            completion_time = datetime.now()
            elapsed = (completion_time - start_time).total_seconds()

            print(f"First completed: {name} at {completion_time.strftime('%H:%M:%S.%f')} ({elapsed:.2f}s)")
            print(f"Result: {result}")

            # Return immediately after first completion
            print("Returning immediately after first completion...")
            return result, elapsed

if __name__ == "__main__":
    result, elapsed = test_thread_pool()
    print(f"\nTotal time: {elapsed:.2f} seconds")

    if elapsed < 1.5:
        print("✓ Fast completion - ThreadPoolExecutor working correctly")
    else:
        print("⚠ Slow completion - may be running sequentially")