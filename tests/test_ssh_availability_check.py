"""
Test that SSH availability check works correctly.
"""
from conftest import is_ssh_server_available, SSH_AVAILABLE


def test_ssh_availability_check():
    """Test that SSH availability check function runs without errors."""

    # Call the function
    result = is_ssh_server_available()

    # Result should be a boolean
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"

    # The constant should match the function result
    assert SSH_AVAILABLE == result, "SSH_AVAILABLE constant doesn't match function result"

    print(f"SSH server available: {result}")

    if result:
        print("✓ SSH server detected on localhost:22")
    else:
        print("✗ No SSH server found on localhost:22")
        print("  Tests requiring SSH will be skipped")


if __name__ == "__main__":
    test_ssh_availability_check()
