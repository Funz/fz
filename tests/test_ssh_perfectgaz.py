"""
Test perfect gas calculation using fzr over SSH to localhost.
Combines SSH functionality with parametric calculations.

This test requires the paramiko library to run. Install it with:
    pip install paramiko

The test will be skipped if paramiko is not available.

The test:
1. Generates a dedicated SSH key pair in the test's temp directory
2. Adds the public key to ~/.ssh/authorized_keys
3. Adds the key to SSH agent (or copies to standard location as fallback)
4. Verifies SSH connectivity to localhost
5. Creates perfect gas calculation files (input.txt, PerfectGazPressure.sh)
6. Runs fzr with ssh://localhost calculator
7. Verifies results and cleanup
"""
import os
import subprocess
import time
from pathlib import Path
import pytest
import getpass
from fz import fzr
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
def test_perfectgaz_via_ssh_localhost():
    """Test perfect gas calculation executed via SSH on localhost."""

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
            "-C", "fz-perfectgaz-test"
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
    key_marker = f"# FZ-PERFECTGAZ-TEST-{os.getpid()}"
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

        # Step 3: Add key to SSH agent (so paramiko can find it)
        print("\n3. Adding key to SSH agent...")

        # Start ssh-agent if not running
        agent_output = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True
        )

        # Add our test key to the agent
        result = subprocess.run(
            ["ssh-add", str(key_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Warning: Could not add key to agent: {result.stderr}")
            print("Trying to copy key to standard location instead...")

            # Fallback: Copy key to a standard location that paramiko will find
            home_ssh = Path.home() / ".ssh"
            test_key_std = home_ssh / "id_rsa_fz_test"
            test_key_std_pub = home_ssh / "id_rsa_fz_test.pub"

            # Backup if it exists
            test_key_backup = None
            if test_key_std.exists():
                test_key_backup = test_key_std.read_bytes()

            # Copy our test key
            test_key_std.write_bytes(key_path.read_bytes())
            test_key_std.chmod(0o600)
            test_key_std_pub.write_bytes(pub_key_path.read_bytes())
            test_key_std_pub.chmod(0o644)

            print(f"✓ Test key copied to {test_key_std}")
        else:
            print(f"✓ Key added to SSH agent")

        # Step 4: Test basic SSH connection
        print("\n4. Testing SSH connection...")
        result = subprocess.run(
            [
                "ssh",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "LogLevel=ERROR",
                f"{getpass.getuser()}@localhost",
                "echo 'SSH OK'"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"SSH connection failed: {result.stderr}")

        print("✓ SSH connection verified")

        # Step 5: Create perfect gas calculation files
        print("\n5. Creating perfect gas calculation files...")

        # Create input template
        input_file = test_dir / "input.txt"
        input_file.write_text("""# Perfect Gas Calculation Input
Temperature_Celsius = $(T_celsius)
Volume_Liters = $(V_L)
Amount_Moles = $(n_mol)
Gas_Constant_R = 0.08314  # L⋅bar/(mol⋅K)
""")

        # Create calculator script
        calc_script = test_dir / "PerfectGazPressure.sh"
        calc_script.write_text("""#!/bin/bash
# Perfect Gas Pressure Calculator
echo 'Calculating perfect gas pressure...'

# Read variables from input.txt
T_CELSIUS=$(grep 'Temperature_Celsius =' input.txt | cut -d'=' -f2 | tr -d ' ')
V_L=$(grep 'Volume_Liters =' input.txt | cut -d'=' -f2 | tr -d ' ')
N_MOL=$(grep 'Amount_Moles =' input.txt | cut -d'=' -f2 | tr -d ' ')
R=0.08314

# Convert temperature to Kelvin
T_KELVIN=$(python3 -c "print($T_CELSIUS + 273.15)")

# Calculate pressure using ideal gas law: P = nRT/V
if [ "$N_MOL" != "0" ] && [ "$V_L" != "0" ]; then
    PRESSURE=$(python3 -c "print(round($N_MOL * $R * $T_KELVIN / $V_L, 4))")
    echo "pressure = $PRESSURE bar" > output.txt
    echo "Calculated pressure: $PRESSURE bar"
else
    echo "pressure = 0.0 bar" > output.txt
    echo "Warning: Zero moles or volume, pressure set to 0"
fi

echo "Calculation completed"
""")
        calc_script.chmod(0o755)

        print("✓ Created input.txt")
        print("✓ Created PerfectGazPressure.sh")

        # Step 6: Run fzr with SSH calculator
        print("\n6. Running fzr with SSH calculator...")

        # Build SSH calculator URL
        ssh_calculator = f"ssh://{getpass.getuser()}@localhost/bash " + str(calc_script.resolve()) #./PerfectGazPressure.sh"

        print(f"Calculator: {ssh_calculator}")

        result = fzr(
            "input.txt",
            {
                "T_celsius": [20],
                "V_L": [1.0],
                "n_mol": [1.0]
            },
            {
                "varprefix": "$",
                "delim": "()",
                "commentline": "#",
                "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
            },
            calculators=[ssh_calculator],
            results_dir="results"
        )

        # Step 7: Verify results
        print("\n7. Verifying results...")
        print(f"Cases executed: {len(result['status'])}")

        # Check all cases completed
        success_count = sum(1 for status in result['status'] if status == 'done')
        total_count = len(result['status'])

        print(f"Status summary: {success_count}/{total_count} successful")

        # Print errors if any
        if 'error' in result and any(result['error']):
            print("\nErrors encountered:")
            for i, error in enumerate(result['error']):
                if error:
                    print(f"  Case {i}: {error}")

        assert success_count > 0, f"No cases completed successfully. Errors: {result.get('error', [])}"
        print(f"✓ {success_count} cases completed successfully")

        # Verify we have pressure results
        if 'pressure' in result:
            pressures = [p for p in result['pressure'] if p is not None]
            print(f"✓ Got {len(pressures)} pressure values")
            print(f"  Sample pressures: {pressures[:3]}")

            # Verify at least some pressures are reasonable (> 0)
            positive_pressures = [float(p) for p in pressures if float(p) > 0]
            assert len(positive_pressures) > 0, "No positive pressure values found"
            print(f"✓ Found {len(positive_pressures)} positive pressure values")
        else:
            print("⚠ No pressure output column found")

        # Verify results directory was created
        results_dir = test_dir / "results"
        assert results_dir.exists(), "Results directory not created"
        print(f"✓ Results directory created: {results_dir}")

        # Count result subdirectories
        case_dirs = list(results_dir.glob("*"))
        print(f"✓ Found {len(case_dirs)} case directories")

        print("\n✅ All perfect gas SSH tests passed!")

        return True

    finally:
        # Step 8: Cleanup - Remove test key from authorized_keys and SSH agent
        print("\n8. Cleaning up...")

        # Remove key from SSH agent if it was added
        subprocess.run(
            ["ssh-add", "-d", str(key_path)],
            capture_output=True,
            text=True
        )

        # Remove key from standard location if we copied it there
        home_ssh = Path.home() / ".ssh"
        test_key_std = home_ssh / "id_rsa_fz_test"
        test_key_std_pub = home_ssh / "id_rsa_fz_test.pub"

        if test_key_std.exists():
            test_key_std.unlink()
            print("✓ Removed test key from standard location")
        if test_key_std_pub.exists():
            test_key_std_pub.unlink()

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
    test_perfectgaz_via_ssh_localhost()
