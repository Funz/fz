"""Tests for MORET plugin model"""
import os
import sys
import json
import tempfile
from pathlib import Path
import fz


def test_moret_model_extraction():
    """Test MORET model output extraction"""

    original_dir = os.getcwd()

    # Load the moret model from project root
    project_root = Path(__file__).parent.parent
    model_file = project_root / ".fz" / "models" / "moret.json"
    with open(model_file, 'r') as f:
        model = json.load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            tmpdir = Path(tmpdir)

            # Create a simple MORET input file
            input_file = tmpdir / "test.m5"
            input_file.write_text("""MORET_BEGIN
TITLE TEST

TERM
  CYCL
    ACTI $(n_cycles)
    PASS 3
  KEFF
    SIGM 0.001
ENDT

* Geometry modelling
GEOM
  MODU 0
  TYPE 1 SPHE $(radius)
  VOLU Ext0 0 1 1 0.0 0.0 0.0
  ENDM
ENDG

ENDD
MORET_END
""")

            # Create mock calculator that generates expected output
            calc_script = tmpdir / "mock_moret.sh"
            calc_script.write_text("""#!/bin/bash
# Mock MORET calculator
cat > test.m5.listing << 'EOF'
##                 ETAPE    417  ESTI. + FAIBLE SIGMA     0.99612 +/-  0.00100  :  0.99314 < KEFF < 0.99911           ##
EOF
echo "Done"
""")
            calc_script.chmod(0o755)

            # Test fzi - extract variables
            variables = fz.fzi(str(input_file), model)
            expected_vars = {'n_cycles': None, 'radius': None}
            assert variables == expected_vars, f"Expected {expected_vars}, got {variables}"

            # Test fzr - run calculation and extract outputs
            results = fz.fzr(
                str(input_file),
                model,
                var_values={'n_cycles': 100, 'radius': 8.741},
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

            assert abs(mean_keff - 0.99612) < 0.00001, f"Expected mean_keff=0.99612, got {mean_keff}"
            assert abs(sigma_keff - 0.00100) < 0.00001, f"Expected sigma_keff=0.00100, got {sigma_keff}"

            print("✓ MORET model test passed!")

        finally:
            os.chdir(original_dir)


def test_moret_sample_file():
    """Test with the imported MORET sample file"""

    # Check if sample was copied
    sample_file = Path.cwd() / "examples" / "moret" / "godiva.m5"
    assert sample_file.exists(), f"Sample file not found: {sample_file}"

    # Load model and extract variables
    model_file = Path.cwd() / ".fz" / "models" / "moret.json"
    with open(model_file, 'r') as f:
        model = json.load(f)
    variables = fz.fzi(str(sample_file), model)

    # The godiva.m5 sample has no variables (it's a fixed case)
    assert isinstance(variables, dict), "Variables should be a dict"
    print(f"✓ Sample file has {len(variables)} variables: {list(variables.keys())}")


if __name__ == '__main__':
    test_moret_model_extraction()
    test_moret_sample_file()
