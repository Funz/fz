"""
Test SSH connection to localhost with dedicated key.
"""
import os
import subprocess
import tempfile
from pathlib import Path
import time


def test_ssh_localhost_with_dedicated_key():
    """Test SSH connection to localhost using a dedicated key."""

    # Get the temp directory from conftest fixture (already in temp dir)
    test_dir = Path.cwd()
    ssh_dir = test_dir / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    key_path = ssh_dir / "test_key"
    pub_key_path = ssh_dir / "test_key.pub"

    print(f"Test directory: {test_dir}")
    print(f"SSH key path: {key_path}")

    # Step 1: Generate SSH key pair
    print("\n1. Generating SSH key pair...")
    result = subprocess.run(
        [
            "ssh-keygen",
            "-t", "rsa",
            "-b", "2048",
            "-f", str(key_path),
            "-N", "",  # No passphrase
            "-C", "fz-test-key"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error generating key: {result.stderr}")
        raise RuntimeError(f"Failed to generate SSH key: {result.stderr}")

    assert key_path.exists(), "Private key not created"
    assert pub_key_path.exists(), "Public key not created"
    print(f"✓ SSH key pair generated")

    # Set correct permissions
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)

    # Step 2: Read the public key
    pub_key_content = pub_key_path.read_text().strip()
    print(f"✓ Public key: {pub_key_content[:50]}...")

    # Step 3: Add public key to authorized_keys
    print("\n2. Adding public key to ~/.ssh/authorized_keys...")
    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)

    authorized_keys_path = home_ssh_dir / "authorized_keys"

    # Mark the key with a comment so we can remove it later
    key_marker = f"# FZ-TEST-KEY-MARKER-{os.getpid()}"
    key_entry = f"{key_marker}\n{pub_key_content}\n"

    # Backup existing authorized_keys if it exists
    original_authorized_keys = None
    if authorized_keys_path.exists():
        original_authorized_keys = authorized_keys_path.read_text()

    try:
        # Append our test key
        with open(authorized_keys_path, "a") as f:
            f.write(key_entry)
        authorized_keys_path.chmod(0o600)
        print(f"✓ Public key added to {authorized_keys_path}")

        # Give SSH a moment to recognize the change
        time.sleep(0.5)

        # Step 4: Test SSH connection to localhost
        print("\n3. Testing SSH connection to localhost...")

        # Create SSH config to avoid host key checking
        ssh_config_path = ssh_dir / "config"
        ssh_config_path.write_text("""
Host localhost
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
""")
        ssh_config_path.chmod(0o600)

        # Test simple SSH command
        result = subprocess.run(
            [
                "ssh",
                "-i", str(key_path),
                "-F", str(ssh_config_path),
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=5",
                f"{os.getenv('USER')}@localhost",
                "echo 'SSH connection successful'"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        print(f"SSH return code: {result.returncode}")
        print(f"SSH stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"SSH stderr: {result.stderr.strip()}")

        assert result.returncode == 0, f"SSH connection failed: {result.stderr}"
        assert "SSH connection successful" in result.stdout, "SSH command output unexpected"
        print("✓ SSH connection to localhost successful")

        # Step 5: Test SSH with command execution
        print("\n4. Testing SSH command execution...")
        result = subprocess.run(
            [
                "ssh",
                "-i", str(key_path),
                "-F", str(ssh_config_path),
                "-o", "BatchMode=yes",
                f"{os.getenv('USER')}@localhost",
                "pwd"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, "SSH command execution failed"
        print(f"✓ Remote pwd: {result.stdout.strip()}")

        # Step 6: Test file transfer with scp
        print("\n5. Testing file transfer with scp...")
        test_file = test_dir / "test_file.txt"
        test_file.write_text("Test content for SSH transfer")

        remote_path = f"{os.getenv('USER')}@localhost:/tmp/fz_ssh_test_{os.getpid()}.txt"

        result = subprocess.run(
            [
                "scp",
                "-i", str(key_path),
                "-F", str(ssh_config_path),
                "-o", "BatchMode=yes",
                str(test_file),
                remote_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, f"SCP transfer failed: {result.stderr}"
        print("✓ File transfer via scp successful")

        # Verify the transferred file
        remote_file = Path(f"/tmp/fz_ssh_test_{os.getpid()}.txt")
        if remote_file.exists():
            assert remote_file.read_text() == "Test content for SSH transfer"
            remote_file.unlink()  # Clean up
            print("✓ Transferred file verified and cleaned up")

        print("\n✅ All SSH tests passed!")

    finally:
        # Step 7: Cleanup - Remove the test key from authorized_keys
        print("\n6. Cleaning up...")

        if authorized_keys_path.exists():
            current_content = authorized_keys_path.read_text()

            # Remove our test key (both the marker and the key line)
            lines = current_content.split('\n')
            cleaned_lines = []
            skip_next = False

            for line in lines:
                if key_marker in line:
                    skip_next = True
                    continue
                if skip_next and line.strip() == pub_key_content.strip():
                    skip_next = False
                    continue
                cleaned_lines.append(line)

            # Write back the cleaned content
            if original_authorized_keys is not None:
                # Restore original if we had one
                authorized_keys_path.write_text(original_authorized_keys)
            else:
                # Or write cleaned content
                cleaned_content = '\n'.join(cleaned_lines)
                if cleaned_content.strip():
                    authorized_keys_path.write_text(cleaned_content)
                else:
                    # Remove empty authorized_keys file
                    authorized_keys_path.unlink()

            print("✓ Cleaned up authorized_keys")

        print("✓ Test cleanup complete")


if __name__ == "__main__":
    test_ssh_localhost_with_dedicated_key()
