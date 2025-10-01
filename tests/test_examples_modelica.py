#!/usr/bin/env python3
"""
Test cases for Modelica examples from .claude/examples.md
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import fz

def setup_modelica_test():
    """Setup test environment for Modelica examples"""
    # Create input.txt file for Modelica
    input_content = """model NewtonCooling
  parameter Real convection = $convection;
  Real T(start=373.15);
equation
  der(T) = -convection * (T - 293.15);
end NewtonCooling;
"""

    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create Modelica.sh script (simplified simulation)
    script_content = """#!/bin/bash
# Mock Modelica simulation
source $1
sleep 0.1

# Create mock CSV result files
cat > NewtonCooling_res.csv << EOF
time,T
0.0,373.15
1.0,`echo "373.15 - $convection * 80" | bc -l`
2.0,`echo "373.15 - $convection * 140" | bc -l`
3.0,`echo "373.15 - $convection * 180" | bc -l`
EOF

echo "Modelica simulation complete"
"""

    with open("Modelica.sh", "w") as f:
        f.write(script_content)
    os.chmod("Modelica.sh", 0o755)

def test_modelica_fzi():
    """Test Modelica fzi - input identification"""
    setup_modelica_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}
    }

    try:
        result = fz.fzi("input.txt", model)
        print("✅ Modelica fzi test passed")
        print(f"   Identified variables: {list(result.keys())}")
        assert "convection" in result
    except Exception as e:
        print(f"❌ Modelica fzi test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "Modelica.sh"]:
            if os.path.exists(f):
                os.remove(f)

def test_modelica_fzc():
    """Test Modelica fzc - calculation with specific values"""
    setup_modelica_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "echo '{\"NewtonCooling\": {\"time\": [0,1,2], \"T\": [373.15, 350.0, 330.0]}}'"}  # Simplified output
    }

    variables = {
        "convection": 0.123
    }

    try:
        result = fz.fzc("input.txt", model, variables, engine="python", outputdir="output")
        print("✅ Modelica fzc test passed")
        print(f"   Result keys: {list(result.keys()) if result else 'None'}")
        # Clean up output directory
        if os.path.exists("output"):
            shutil.rmtree("output")
    except Exception as e:
        print(f"❌ Modelica fzc test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "Modelica.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("output"):
            shutil.rmtree("output")

def test_modelica_fzr():
    """Test Modelica fzr - run with results"""
    setup_modelica_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "echo '{\"NewtonCooling\": {\"time\": [0,1,2], \"T\": [373.15, 350.0, 330.0]}}'"}  # Simplified output
    }

    variables = {
        "convection": [0.123, 0.456, 0.789]
    }

    try:
        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators="sh://bash ./Modelica.sh",
                       resultsdir="results")
        print("✅ Modelica fzr test passed")
        print(f"   Number of results: {len(result) if (hasattr(result, '__len__') and (not hasattr(result, 'empty') or not result.empty)) else 0}")
        # Clean up results directory
        if os.path.exists("results"):
            shutil.rmtree("results")
    except Exception as e:
        print(f"❌ Modelica fzr test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "Modelica.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    """Run all Modelica example tests"""
    print("🧪 Running Modelica Example Tests")
    print("=" * 50)

    # Change to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working in: {temp_dir}")

        try:
            test_modelica_fzi()
            test_modelica_fzc()
            test_modelica_fzr()

            print("\n✅ All Modelica example tests passed!")

        except Exception as e:
            print(f"\n❌ Tests failed: {e}")
            raise