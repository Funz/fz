"""Tests for MCNP plugin model"""
import os
import sys
import json
import tempfile
from pathlib import Path
import fz


def test_mcnp_model_extraction():
    """Test MCNP model output extraction"""

    original_dir = os.getcwd()

    # Load the mcnp model from project root
    project_root = Path(__file__).parent.parent
    model_file = project_root / ".fz" / "models" / "mcnp.json"
    with open(model_file, 'r') as f:
        model = json.load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            tmpdir = Path(tmpdir)

            # Create a simple MCNP input file
            input_file = tmpdir / "test.mcnp"
            input_file.write_text("""Godiva-type critical reactor
c kcode example with %(n_particles) neutrons
 1    1  -18.74  -1  imp:n=1   $ enriched uranium sphere
 2    0           1  imp:n=0   $ all space outside

 1    so %(radius)              $ radius of sphere

 kcode %(n_particles) 1.0 10 110
 ksrc  0 0 0
 m1    92235 -93.71  92238 -5.27  92234 -1.02
""")

            # Create mock calculator that generates expected output
            calc_script = tmpdir / "mock_mcnp.sh"
            calc_script.write_text("""#!/bin/bash
# Mock MCNP calculator
cat > outp << 'EOF'
 | the final estimated combined collision/absorption/track-length keff = 1.00248 with an estimated standard deviation of 0.00062   |
EOF
echo "Done"
""")
            calc_script.chmod(0o755)

            # Test fzi - extract variables
            variables = fz.fzi(str(input_file), model)
            expected_vars = {'n_particles': None, 'radius': None}
            assert variables == expected_vars, f"Expected {expected_vars}, got {variables}"

            # Test fzr - run calculation and extract outputs
            results = fz.fzr(
                str(input_file),
                model,
                var_values={'n_particles': 1000, 'radius': 8.741},
                calculators=f"sh://bash {calc_script}",
                results_dir="results"
            )

            # Verify outputs
            assert results is not None, "Results should not be None"
            assert 'mean_keff' in results, "mean_keff should be in results"
            assert 'sigma_keff' in results, "sigma_keff should be in results"

            # Check extracted values
            mean_keff = float(results['mean_keff'][0])
            sigma_keff = float(results['sigma_keff'][0])

            assert abs(mean_keff - 1.00248) < 0.00001, f"Expected mean_keff=1.00248, got {mean_keff}"
            assert abs(sigma_keff - 0.00062) < 0.00001, f"Expected sigma_keff=0.00062, got {sigma_keff}"

            print("✓ MCNP model test passed!")

        finally:
            os.chdir(original_dir)


def test_mcnp_sample_file():
    """Test with the imported MCNP sample file"""

    # Check if sample was copied
    sample_file = Path.cwd() / "examples" / "mcnp" / "godiva"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"

    # Load model and extract variables
    model_file = Path.cwd() / ".fz" / "models" / "mcnp.json"
    with open(model_file, 'r') as f:
        model = json.load(f)
    variables = fz.fzi(str(sample_file), model)

    # The godiva sample has no variables (it's a fixed case)
    assert isinstance(variables, dict), "Variables should be a dict"
    print(f"✓ Sample file has {len(variables)} variables: {list(variables.keys())}")


if __name__ == '__main__':
    test_mcnp_model_extraction()
    test_mcnp_sample_file()
