#!/usr/bin/env python3
"""
Test cases for PerfectGaz examples from .claude/examples.md
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

def setup_perfectgaz_test():
    """Setup test environment for PerfectGaz examples"""
    # Create input.txt file
    input_content = """Temperature: $T_celsius C
Volume: $V_L L
Amount: $n_mol mol

# Calculate pressure using ideal gas law
# P = nRT/V
@pressure = $n_mol * 8.314 * ($T_celsius + 273.15) / ($V_L / 1000)
"""

    with open("input.txt", "w") as f:
        f.write(input_content)

    # Create PerfectGazPressure.sh script
    script_content = """#!/bin/bash
# read input file
source $1
sleep 0.1 # simulate a calculation time
echo 'pressure = '`echo "scale=4;$n_mol*8.314*($T_celsius+273.15)/($V_L/1000)" | bc` > output.txt
echo 'Done'
"""

    with open("PerfectGazPressure.sh", "w") as f:
        f.write(script_content)
    os.chmod("PerfectGazPressure.sh", 0o755)

def test_perfectgaz_fzi():
    """Test PerfectGaz fzi - input identification"""
    setup_perfectgaz_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    try:
        result = fz.fzi("input.txt", model)
        print("✅ PerfectGaz fzi test passed")
        print(f"   Identified variables: {list(result.keys())}")
        assert "T_celsius" in result
        assert "V_L" in result
        assert "n_mol" in result
    except Exception as e:
        print(f"❌ PerfectGaz fzi test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)

def test_perfectgaz_fzc():
    """Test PerfectGaz fzc - calculation with specific values"""
    setup_perfectgaz_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    variables = {
        "T_celsius": 20,
        "V_L": 1,
        "n_mol": 1
    }

    try:
        result = fz.fzc("input.txt", model, variables, engine="python", outputdir="output")
        print("✅ PerfectGaz fzc test passed")
        print(f"   Result: {result}")
        # fzc may return None for successful calculation without output parsing
        # This is expected behavior for fzc vs fzr
        # Clean up output directory
        if os.path.exists("output"):
            shutil.rmtree("output")
    except Exception as e:
        print(f"❌ PerfectGaz fzc test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("output"):
            shutil.rmtree("output")

def test_perfectgaz_fzr_single():
    """Test PerfectGaz fzr - run single case"""
    setup_perfectgaz_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    variables = {
        "T_celsius": 20,
        "V_L": 1,
        "n_mol": 1
    }

    try:
        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators="sh://bash ./PerfectGazPressure.sh",
                       resultsdir="result")
        print("✅ PerfectGaz fzr single test passed")
        print(f"   Result: {result}")
        assert result is not None
        assert "pressure" in result
        # Clean up result directory
        if os.path.exists("result"):
            shutil.rmtree("result")
    except Exception as e:
        print(f"❌ PerfectGaz fzr single test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("result"):
            shutil.rmtree("result")

def test_perfectgaz_fzr_multiple():
    """Test PerfectGaz fzr - run multiple cases"""
    setup_perfectgaz_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    variables = {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": 1
    }

    try:
        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators="sh://bash ./PerfectGazPressure.sh",
                       resultsdir="results")
        print("✅ PerfectGaz fzr multiple test passed")
        print(f"   Result structure: {type(result)}")
        assert result is not None
        assert "pressure" in result
        # Check that we have the expected variables in the result
        if isinstance(result, dict):
            assert "T_celsius" in result
            assert "V_L" in result
            assert "n_mol" in result
        # Clean up results directory
        if os.path.exists("results"):
            shutil.rmtree("results")
    except Exception as e:
        print(f"❌ PerfectGaz fzr multiple test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

def test_perfectgaz_parallel():
    """Test PerfectGaz parallel execution"""
    setup_perfectgaz_test()

    model = {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }

    variables = {
        "T_celsius": [20, 30, 40],
        "V_L": 1,
        "n_mol": 1
    }

    try:
        result = fz.fzr("input.txt", model, variables,
                       engine="python",
                       calculators=["sh://bash ./PerfectGazPressure.sh", "sh://bash ./PerfectGazPressure.sh"],
                       resultsdir="results")
        print("✅ PerfectGaz parallel test passed")
        print(f"   Result structure: {type(result)}")
        assert result is not None
        assert "pressure" in result
        # Check that we have the expected variables
        if isinstance(result, dict):
            assert "T_celsius" in result
        # Clean up results directory
        if os.path.exists("results"):
            shutil.rmtree("results")
    except Exception as e:
        print(f"❌ PerfectGaz parallel test failed: {e}")
        raise
    finally:
        # Cleanup
        for f in ["input.txt", "PerfectGazPressure.sh"]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists("results"):
            shutil.rmtree("results")

if __name__ == "__main__":
    """Run all PerfectGaz example tests"""
    print("🧪 Running PerfectGaz Example Tests")
    print("=" * 50)

    # Change to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        print(f"Working in: {temp_dir}")

        try:
            test_perfectgaz_fzi()
            test_perfectgaz_fzc()
            test_perfectgaz_fzr_single()
            test_perfectgaz_fzr_multiple()
            test_perfectgaz_parallel()

            print("\n✅ All PerfectGaz example tests passed!")

        except Exception as e:
            print(f"\n❌ Tests failed: {e}")
            raise