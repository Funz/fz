"""
Test SSH calculator with many cases running on localhost.

This test verifies that the SSH calculator can handle multiple parametric cases
efficiently, running them all on localhost via SSH.

This test requires the paramiko library to run. Install it with:
    pip install paramiko

The test will be skipped if paramiko is not available.
"""
import os
import subprocess
import time
from pathlib import Path
import pytest
from conftest import SSH_AVAILABLE

# Check if paramiko is available
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
def test_ssh_many_cases_localhost():
    """Test SSH calculator with many parametric cases on localhost."""

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
            "-C", "fz-many-cases-test"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate SSH key: {result.stderr}")

    assert key_path.exists(), "Private key not created"
    assert pub_key_path.exists(), "Public key not created"

    # Set correct permissions
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)
    print("✓ SSH key pair generated")

    # Step 2: Add public key to authorized_keys
    print("\n2. Setting up SSH access...")
    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys_path = home_ssh_dir / "authorized_keys"

    pub_key_content = pub_key_path.read_text().strip()
    key_marker = f"# FZ-MANY-CASES-TEST-{os.getpid()}"
    key_entry = f"{key_marker}\n{pub_key_content}\n"

    # Backup existing authorized_keys
    original_authorized_keys = None
    if authorized_keys_path.exists():
        original_authorized_keys = authorized_keys_path.read_text()

    try:
        # Append our test key
        with open(authorized_keys_path, "a") as f:
            f.write(key_entry)
        authorized_keys_path.chmod(0o600)
        print("✓ SSH key added to authorized_keys")

        time.sleep(0.5)  # Give SSH time to recognize changes

        # Step 3: Add key to SSH agent
        print("\n3. Adding key to SSH agent...")
        result = subprocess.run(
            ["ssh-add", str(key_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Warning: Could not add key to agent: {result.stderr}")
            print("Trying fallback method...")

            # Fallback: Copy key to standard location
            home_ssh = Path.home() / ".ssh"
            test_key_std = home_ssh / "id_rsa_fz_many_test"
            test_key_std_pub = home_ssh / "id_rsa_fz_many_test.pub"

            test_key_std.write_bytes(key_path.read_bytes())
            test_key_std.chmod(0o600)
            test_key_std_pub.write_bytes(pub_key_path.read_bytes())
            test_key_std_pub.chmod(0o644)

            print(f"✓ Test key copied to {test_key_std}")
        else:
            print("✓ Key added to SSH agent")

        # Step 4: Test basic SSH connection
        print("\n4. Testing SSH connection...")
        result = subprocess.run(
            [
                "ssh",
                "-i" if key_path.exists() else "", str(key_path) if key_path.exists() else "",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "LogLevel=ERROR",
                f"{os.getenv('USER')}@localhost",
                "echo 'SSH OK'"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"SSH connection failed: {result.stderr}")

        print("✓ SSH connection verified")

        # Step 5: Create calculation files
        print("\n5. Creating calculation files...")

        # Create input template with 3 variables
        input_file = test_dir / "input.txt"
        input_file.write_text("""# Multi-variable calculation
x = $(x)
y = $(y)
z = $(z)
""")

        # Create calculator script that computes various functions
        calc_script = test_dir / "Calculator.sh"
        calc_script.write_text("""#!/bin/bash
# Multi-variable calculator
echo 'Running calculation...'

# Read variables
X=$(grep '^x =' input.txt | cut -d'=' -f2 | tr -d ' ')
Y=$(grep '^y =' input.txt | cut -d'=' -f2 | tr -d ' ')
Z=$(grep '^z =' input.txt | cut -d'=' -f2 | tr -d ' ')

echo "Inputs: x=$X, y=$Y, z=$Z"

# Calculate various outputs
SUM=$(python3 -c "print($X + $Y + $Z)")
PRODUCT=$(python3 -c "print($X * $Y * $Z)")
AVG=$(python3 -c "print(($X + $Y + $Z) / 3.0)")
MAX=$(python3 -c "print(max($X, $Y, $Z))")

# Write outputs
echo "sum = $SUM" > output.txt
echo "product = $PRODUCT" >> output.txt
echo "average = $AVG" >> output.txt
echo "maximum = $MAX" >> output.txt

echo "Results:"
cat output.txt
""")
        calc_script.chmod(0o755)

        print("✓ Created input.txt")
        print("✓ Created Calculator.sh")

        # Step 6: Run fzr with SSH calculator and MANY cases
        print("\n6. Running fzr with SSH calculator...")
        print("   Using multiple parameter values to generate many cases...")

        # Import fzr
        from fz import fzr

        # Build SSH calculator URL
        ssh_calculator = f"ssh://{os.getenv('USER')}@localhost/bash {calc_script.resolve()}"

        print(f"   Calculator: {ssh_calculator}")

        # Run with many parameter combinations
        # 5 * 4 * 3 = 60 cases
        result = fzr(
            "input.txt",
            {
                "x": [1, 2, 3],
                "y": [10, 20],
                "z": [100]
            },
            {
                "varprefix": "$",
                "delim": "()",
                "commentline": "#",
                "output": {
                    "sum": "grep '^sum =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "product": "grep '^product =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "average": "grep '^average =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "maximum": "grep '^maximum =' output.txt | cut -d'=' -f2 | tr -d ' '"
                }
            },
            calculators=[ssh_calculator],
            results_dir="results"
        )

        print(result)

        # Step 7: Verify results
        print("\n7. Verifying results...")
        total_cases = len(result['status'])
        print(f"   Total cases: {total_cases}")
        # also check 'sum' in result is matching x+y+z
        assert 'x' in result and 'y' in result and 'z' in result, "Missing input variables in results"
        assert len(result['x']) == total_cases, "Mismatch in number of x values"
        assert len(result['y']) == total_cases, "Mismatch in number of y values"
        assert len(result['z']) == total_cases, "Mismatch in number of z values"
        assert len(result['sum']) == total_cases, "Mismatch in number of sum values"
        assert all(result['sum'] == [result['x'][i] + result['y'][i] + result['z'][i] for i in range(total_cases)]), "Sum values incorrect"

        # Expected: 3 * 2 * 1 = 6 cases
        assert total_cases == 6, f"Expected 6 cases, got {total_cases}"
        print("✓ Correct number of cases")

        # Check all cases completed
        success_count = sum(1 for status in result['status'] if status == 'done')
        failed_count = total_cases - success_count

        print(f"   Successful: {success_count}")
        print(f"   Failed: {failed_count}")

        # Print errors if any
        if 'error' in result and any(result['error']):
            print("\nErrors encountered:")
            error_count = 0
            for i, error in enumerate(result['error']):
                if error and error_count < 5:  # Show first 5 errors
                    print(f"  Case {i}: {error}")
                    error_count += 1
            if error_count >= 5:
                print(f"  ... and {failed_count - 5} more errors")

        # Require at least 90% success rate (allowing for some transient SSH issues)
        success_rate = success_count / total_cases
        assert success_rate >= 0.9, f"Success rate too low: {success_rate:.1%} (expected >= 90%)"
        print(f"✓ Success rate: {success_rate:.1%}")

        # Verify we have output results
        assert 'sum' in result, "Missing 'sum' output"
        assert 'product' in result, "Missing 'product' output"
        assert 'average' in result, "Missing 'average' output"
        assert 'maximum' in result, "Missing 'maximum' output"
        print("✓ All output variables present")

        # Verify some sample calculations
        print("\n8. Verifying sample calculations...")
        for i in range(min(3, len(result['x']))):
            if result['status'][i] == 'done':
                x = float(result['x'][i])
                y = float(result['y'][i])
                z = float(result['z'][i])
                sum_result = float(result['sum'][i])
                expected_sum = x + y + z

                print(f"   Case {i}: x={x}, y={y}, z={z}")
                print(f"     sum={sum_result}, expected={expected_sum}")

                assert abs(sum_result - expected_sum) < 0.01, f"Sum calculation incorrect for case {i}"

        print("✓ Sample calculations verified")

        # Verify results directory was created
        results_dir = test_dir / "results"
        assert results_dir.exists(), "Results directory not created"

        # Count result subdirectories
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        print(f"✓ Results directory has {len(case_dirs)} case directories")

        print(f"\n✅ All SSH many-cases tests passed!")
        print(f"   Successfully processed {success_count}/{total_cases} cases via SSH")

        return True

    finally:
        # Step 9: Cleanup
        print("\n9. Cleaning up...")

        # Remove key from SSH agent
        subprocess.run(
            ["ssh-add", "-d", str(key_path)],
            capture_output=True,
            text=True
        )

        # Remove key from standard location if we copied it there
        home_ssh = Path.home() / ".ssh"
        test_key_std = home_ssh / "id_rsa_fz_many_test"
        test_key_std_pub = home_ssh / "id_rsa_fz_many_test.pub"

        if test_key_std.exists():
            test_key_std.unlink()
            print("✓ Removed test key from standard location")
        if test_key_std_pub.exists():
            test_key_std_pub.unlink()

        # Remove test key from authorized_keys
        if authorized_keys_path.exists():
            current_content = authorized_keys_path.read_text()
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

            # Restore original authorized_keys
            if original_authorized_keys is not None:
                authorized_keys_path.write_text(original_authorized_keys)
            else:
                cleaned_content = '\n'.join(cleaned_lines)
                if cleaned_content.strip():
                    authorized_keys_path.write_text(cleaned_content)
                else:
                    authorized_keys_path.unlink()

        print("✓ Cleaned up authorized_keys")
        print("✓ Test cleanup complete")


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
def test_ssh_many_cases_many_localhost():
    """Test SSH calculator with many parametric cases on localhost."""

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
            "-C", "fz-many-cases-test"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate SSH key: {result.stderr}")

    assert key_path.exists(), "Private key not created"
    assert pub_key_path.exists(), "Public key not created"

    # Set correct permissions
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)
    print("✓ SSH key pair generated")

    # Step 2: Add public key to authorized_keys
    print("\n2. Setting up SSH access...")
    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys_path = home_ssh_dir / "authorized_keys"

    pub_key_content = pub_key_path.read_text().strip()
    key_marker = f"# FZ-MANY-CASES-TEST-{os.getpid()}"
    key_entry = f"{key_marker}\n{pub_key_content}\n"

    # Backup existing authorized_keys
    original_authorized_keys = None
    if authorized_keys_path.exists():
        original_authorized_keys = authorized_keys_path.read_text()

    try:
        # Append our test key
        with open(authorized_keys_path, "a") as f:
            f.write(key_entry)
        authorized_keys_path.chmod(0o600)
        print("✓ SSH key added to authorized_keys")

        time.sleep(0.5)  # Give SSH time to recognize changes

        # Step 3: Add key to SSH agent
        print("\n3. Adding key to SSH agent...")
        result = subprocess.run(
            ["ssh-add", str(key_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Warning: Could not add key to agent: {result.stderr}")
            print("Trying fallback method...")

            # Fallback: Copy key to standard location
            home_ssh = Path.home() / ".ssh"
            test_key_std = home_ssh / "id_rsa_fz_many_test"
            test_key_std_pub = home_ssh / "id_rsa_fz_many_test.pub"

            test_key_std.write_bytes(key_path.read_bytes())
            test_key_std.chmod(0o600)
            test_key_std_pub.write_bytes(pub_key_path.read_bytes())
            test_key_std_pub.chmod(0o644)

            print(f"✓ Test key copied to {test_key_std}")
        else:
            print("✓ Key added to SSH agent")

        # Step 4: Test basic SSH connection
        print("\n4. Testing SSH connection...")
        result = subprocess.run(
            [
                "ssh",
                "-i" if key_path.exists() else "", str(key_path) if key_path.exists() else "",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "LogLevel=ERROR",
                f"{os.getenv('USER')}@localhost",
                "echo 'SSH OK'"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"SSH connection failed: {result.stderr}")

        print("✓ SSH connection verified")

        # Step 5: Create calculation files
        print("\n5. Creating calculation files...")

        # Create input template with 3 variables
        input_file = test_dir / "input.txt"
        input_file.write_text("""# Multi-variable calculation
x = $(x)
y = $(y)
z = $(z)
""")

        # Create calculator script that computes various functions
        calc_script = test_dir / "Calculator.sh"
        calc_script.write_text("""#!/bin/bash
# Multi-variable calculator
echo 'Running calculation...'

# Read variables
X=$(grep '^x =' input.txt | cut -d'=' -f2 | tr -d ' ')
Y=$(grep '^y =' input.txt | cut -d'=' -f2 | tr -d ' ')
Z=$(grep '^z =' input.txt | cut -d'=' -f2 | tr -d ' ')

echo "Inputs: x=$X, y=$Y, z=$Z"

# Calculate various outputs
SUM=$(python3 -c "print($X + $Y + $Z)")
PRODUCT=$(python3 -c "print($X * $Y * $Z)")
AVG=$(python3 -c "print(($X + $Y + $Z) / 3.0)")
MAX=$(python3 -c "print(max($X, $Y, $Z))")

# Write outputs
echo "sum = $SUM" > output.txt
echo "product = $PRODUCT" >> output.txt
echo "average = $AVG" >> output.txt
echo "maximum = $MAX" >> output.txt

echo "Results:"
cat output.txt
""")
        calc_script.chmod(0o755)

        print("✓ Created input.txt")
        print("✓ Created Calculator.sh")

        # Step 6: Run fzr with SSH calculator and MANY cases
        print("\n6. Running fzr with SSH calculator...")
        print("   Using multiple parameter values to generate many cases...")

        # Import fzr
        from fz import fzr

        # Build SSH calculator URL
        ssh_calculator = [f"ssh://{os.getenv('USER')}@localhost/bash {calc_script.resolve()}"]*3

        print(f"   Calculators: {ssh_calculator}")

        # Run with many parameter combinations
        # 5 * 4 * 3 = 60 cases
        result = fzr(
            "input.txt",
            {
                "x": [1, 2, 3],
                "y": [10, 20],
                "z": [100]
            },
            {
                "varprefix": "$",
                "delim": "()",
                "commentline": "#",
                "output": {
                    "sum": "grep '^sum =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "product": "grep '^product =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "average": "grep '^average =' output.txt | cut -d'=' -f2 | tr -d ' '",
                    "maximum": "grep '^maximum =' output.txt | cut -d'=' -f2 | tr -d ' '"
                }
            },
            calculators=ssh_calculator,
            results_dir="results"
        )

        print(result)

        # Step 7: Verify results
        print("\n7. Verifying results...")
        total_cases = len(result['status'])
        print(f"   Total cases: {total_cases}")
        # also check 'sum' in result is matching x+y+z
        assert 'x' in result and 'y' in result and 'z' in result, "Missing input variables in results"
        assert len(result['x']) == total_cases, "Mismatch in number of x values"
        assert len(result['y']) == total_cases, "Mismatch in number of y values"
        assert len(result['z']) == total_cases, "Mismatch in number of z values"
        assert len(result['sum']) == total_cases, "Mismatch in number of sum values"
        assert all(result['sum'] == [result['x'][i] + result['y'][i] + result['z'][i] for i in range(total_cases)]), "Sum values incorrect"

        # Expected: 3 * 2 * 1 = 6 cases
        assert total_cases == 6, f"Expected 6 cases, got {total_cases}"
        print("✓ Correct number of cases")

        # Check all cases completed
        success_count = sum(1 for status in result['status'] if status == 'done')
        failed_count = total_cases - success_count

        print(f"   Successful: {success_count}")
        print(f"   Failed: {failed_count}")

        # Print errors if any
        if 'error' in result and any(result['error']):
            print("\nErrors encountered:")
            error_count = 0
            for i, error in enumerate(result['error']):
                if error and error_count < 5:  # Show first 5 errors
                    print(f"  Case {i}: {error}")
                    error_count += 1
            if error_count >= 5:
                print(f"  ... and {failed_count - 5} more errors")

        # Require at least 90% success rate (allowing for some transient SSH issues)
        success_rate = success_count / total_cases
        assert success_rate >= 0.9, f"Success rate too low: {success_rate:.1%} (expected >= 90%)"
        print(f"✓ Success rate: {success_rate:.1%}")

        # Verify we have output results
        assert 'sum' in result, "Missing 'sum' output"
        assert 'product' in result, "Missing 'product' output"
        assert 'average' in result, "Missing 'average' output"
        assert 'maximum' in result, "Missing 'maximum' output"
        print("✓ All output variables present")

        # Verify some sample calculations
        print("\n8. Verifying sample calculations...")
        for i in range(min(3, len(result['x']))):
            if result['status'][i] == 'done':
                x = float(result['x'][i])
                y = float(result['y'][i])
                z = float(result['z'][i])
                sum_result = float(result['sum'][i])
                expected_sum = x + y + z

                print(f"   Case {i}: x={x}, y={y}, z={z}")
                print(f"     sum={sum_result}, expected={expected_sum}")

                assert abs(sum_result - expected_sum) < 0.01, f"Sum calculation incorrect for case {i}"

        print("✓ Sample calculations verified")

        # Verify results directory was created
        results_dir = test_dir / "results"
        assert results_dir.exists(), "Results directory not created"

        # Count result subdirectories
        case_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        print(f"✓ Results directory has {len(case_dirs)} case directories")

        print(f"\n✅ All SSH many-cases tests passed!")
        print(f"   Successfully processed {success_count}/{total_cases} cases via SSH")

        return True

    finally:
        # Step 9: Cleanup
        print("\n9. Cleaning up...")

        # Remove key from SSH agent
        subprocess.run(
            ["ssh-add", "-d", str(key_path)],
            capture_output=True,
            text=True
        )

        # Remove key from standard location if we copied it there
        home_ssh = Path.home() / ".ssh"
        test_key_std = home_ssh / "id_rsa_fz_many_test"
        test_key_std_pub = home_ssh / "id_rsa_fz_many_test.pub"

        if test_key_std.exists():
            test_key_std.unlink()
            print("✓ Removed test key from standard location")
        if test_key_std_pub.exists():
            test_key_std_pub.unlink()

        # Remove test key from authorized_keys
        if authorized_keys_path.exists():
            current_content = authorized_keys_path.read_text()
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

            # Restore original authorized_keys
            if original_authorized_keys is not None:
                authorized_keys_path.write_text(original_authorized_keys)
            else:
                cleaned_content = '\n'.join(cleaned_lines)
                if cleaned_content.strip():
                    authorized_keys_path.write_text(cleaned_content)
                else:
                    authorized_keys_path.unlink()

        print("✓ Cleaned up authorized_keys")
        print("✓ Test cleanup complete")


if __name__ == "__main__":
    test_ssh_many_cases_localhost()
    test_ssh_many_cases_many_localhost()
