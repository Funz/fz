#!/usr/bin/env python3
"""
Test cases for PerfectGaz examples from examples/examples.md
Auto-generated from examples.md code chunks
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import fz


@pytest.fixture
def perfectgaz_setup(tmp_path):
    """Setup test environment for PerfectGaz examples"""
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    # Create input.txt (from examples.md lines 10-17)
    with open("input.txt", "w") as f:
        f.write("""# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@($T_celsius + 273.15)
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@(L_to_m3($V_L))
""")

    # Create PerfectGazPressure.sh (from examples.md lines 22-28)
    with open("PerfectGazPressure.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 1 # simulate a calculation time
echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
echo 'Done'
""")
    os.chmod("PerfectGazPressure.sh", 0o755)

    # Create PerfectGazPressureRandomFails.sh (from examples.md lines 30-44)
    with open("PerfectGazPressureRandomFails.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 1 # simulate a calculation time
if [ $((RANDOM % 2)) -eq 0 ]; then
  echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
  echo 'Done'
else
  echo "Calculation failed" >&2
  exit 1
fi
""")
    os.chmod("PerfectGazPressureRandomFails.sh", 0o755)

    # Create PerfectGazPressureAlwaysFails.sh (from examples.md lines 46-54)
    with open("PerfectGazPressureAlwaysFails.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 1 # simulate a calculation time
echo "Calculation failed" >&2
exit 1
""")
    os.chmod("PerfectGazPressureAlwaysFails.sh", 0o755)

    yield tmp_path

    os.chdir(original_dir)


def test_perfectgaz_fzi(perfectgaz_setup):
    """Test fzi - from examples.md lines 167-175"""
    result = fz.fzi("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    })

    assert "T_celsius" in result
    assert "V_L" in result
    assert "n_mol" in result


def test_perfectgaz_fzc(perfectgaz_setup):
    """Test fzc - from examples.md lines 178-190"""
    fz.fzc("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": 20,
        "V_L": 1,
        "n_mol": 1
    }, output_dir="output")

    # Check if (relative) output directory is created
    assert Path("output").is_dir()


def test_perfectgaz_fzr_single_case(perfectgaz_setup):
    """Test fzr with single case - from examples.md lines 194-207"""
    result = fz.fzr("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": 20,
        "V_L": 1,
        "n_mol": 1
    }, calculators="sh:///bin/bash ./PerfectGazPressure.sh", results_dir="result")

    assert len(result) == 1
    assert result["pressure"][0] is not None


def test_perfectgaz_fzr_factorial_design(perfectgaz_setup):
    """Test fzr with factorial design - from examples.md lines 211-224"""
    result = fz.fzr("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, calculators="sh:///bin/bash ./PerfectGazPressure.sh", results_dir="results")

    assert len(result) == 6  # 3 * 2 combinations


def test_perfectgaz_fzo(perfectgaz_setup):
    """Test fzo to read results - from examples.md lines 227-229"""
    # First run fzr to create results
    fz.fzr("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, calculators="sh:///bin/bash ./PerfectGazPressure.sh", results_dir="results")

    # Now test fzo
    result = fz.fzo("results", {"output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}})

    assert len(result) == 6


def test_perfectgaz_cache(perfectgaz_setup):
    """Test cache usage - from examples.md lines 232-245"""
    # First run to populate cache
    result1 = fz.fzr("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, calculators="sh:///bin/bash ./PerfectGazPressure.sh", results_dir="results_cache")

    # Second run should use cache
    result2 = fz.fzr("input.txt", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, calculators=["cache://results_cache*", "sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results_cache")

    assert len(result2) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
