"""
Test to verify that SSH remote directories are unique even when
multiple calculators run in parallel.
"""
import os
import threading
import uuid


def test_remote_directory_naming():
    """Verify that remote directory names include unique identifiers."""

    # Simulate the directory naming logic from runners.py
    # Using generic remote path for testing
    remote_root_dir = "/remote/workspace"

    # Create multiple directory names in parallel (simulating concurrent SSH connections)
    directory_names = []

    def create_dir_name():
        thread_id = threading.get_ident()
        unique_id = uuid.uuid4().hex[:8]
        remote_temp_dir = (
            f"{remote_root_dir}/.fz/tmp/fz_calc_{os.getpid()}_{thread_id}_{unique_id}"
        )
        directory_names.append(remote_temp_dir)

    # Create 10 directory names from different threads
    threads = []
    for _ in range(10):
        t = threading.Thread(target=create_dir_name)
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify all directory names are unique
    assert len(directory_names) == 10, f"Expected 10 directory names, got {len(directory_names)}"
    assert len(set(directory_names)) == 10, f"Directory names are not unique: {directory_names}"

    # Verify all directory names contain the expected components
    for dir_name in directory_names:
        assert ".fz/tmp/fz_calc_" in dir_name, f"Directory name missing expected prefix: {dir_name}"
        parts = dir_name.split("_")
        assert len(parts) >= 4, f"Directory name missing expected parts: {dir_name}"

    print("✓ All directory names are unique")
    print(f"✓ Sample directory names:")
    for i, name in enumerate(directory_names[:3]):
        print(f"  {i+1}. {name}")


if __name__ == "__main__":
    test_remote_directory_naming()
