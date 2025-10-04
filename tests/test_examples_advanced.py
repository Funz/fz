#!/usr/bin/env python3
"""
Test cases for advanced examples from examples/examples.md
Includes parallel execution, failure support, and non-numeric variables
Auto-generated from examples.md code chunks
"""

import os
import sys
from pathlib import Path
import pytest

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import fz


@pytest.fixture
def advanced_setup(tmp_path):
    """Setup test environment for advanced examples"""
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    # Create input.txt
    with open("input.txt", "w") as f:
        f.write("""# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@($T_celsius + 273.15)
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@(L_to_m3($V_L))
""")

    # Create PerfectGazPressure.sh (with shorter sleep for tests)
    with open("PerfectGazPressure.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 0.5 # simulate a calculation time
echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
echo 'Done'
""")
    os.chmod("PerfectGazPressure.sh", 0o755)

    # Create PerfectGazPressureRandomFails.sh
    with open("PerfectGazPressureRandomFails.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 0.5 # simulate a calculation time
if [ $((RANDOM % 2)) -eq 0 ]; then
  echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
  echo 'Done'
else
  echo "Calculation failed" >&2
  exit 1
fi
""")
    os.chmod("PerfectGazPressureRandomFails.sh", 0o755)

    # Create PerfectGazPressureAlwaysFails.sh
    with open("PerfectGazPressureAlwaysFails.sh", "w") as f:
        f.write("""#!/bin/bash
# read input file
source $1
sleep 0.5 # simulate a calculation time
echo "Calculation failed" >&2
exit 1
""")
    os.chmod("PerfectGazPressureAlwaysFails.sh", 0o755)

    yield tmp_path

    os.chdir(original_dir)


def test_parallel_2_calculators_2_cases(advanced_setup):
    """Test parallel execution with 2 calculators, 2 cases - from examples.md lines 253-265"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25],
        "V_L": 1,
        "n_mol": 1
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh", "sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results")

    assert len(result) == 2
    assert all(result["status"] == "done")


def test_parallel_3_calculators_2_cases(advanced_setup):
    """Test parallel execution with 3 calculators, 2 cases - from examples.md lines 268-281"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25],
        "V_L": 1,
        "n_mol": 1
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh", "sh:///bin/bash ./PerfectGazPressure.sh", "sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results")

    assert len(result) == 2
    assert all(result["status"] == "done")


def test_parallel_2_calculators_3_cases(advanced_setup):
    """Test parallel execution with 2 calculators, 3 cases - from examples.md lines 284-297"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": 1,
        "n_mol": 1
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh", "sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results")

    assert len(result) == 3
    assert all(result["status"] == "done")


def test_parallel_6_calculators_6_cases(advanced_setup):
    """Test parallel execution with 6 calculators, 6 cases - from examples.md lines 433-445"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 30, 40],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh"] * 6, results_dir="results")

    assert len(result) == 6
    assert all(result["status"] == "done")


def test_parallel_fzo_result(advanced_setup):
    """Test fzo on parallel execution results - from examples.md lines 448-450"""
    # First run fzr
    fz.fzr("input.txt", {
        "T_celsius": [20, 30, 40],
        "V_L": [1, 1.5],
        "n_mol": 1
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh"] * 6, results_dir="results")

    # Test fzo
    result = fz.fzo("results", {"output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}})

    assert len(result) == 6


def test_failure_never_fails(advanced_setup):
    """Test failure support - never fails - from examples.md lines 455-468"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh"] * 3, results_dir="results")

    assert len(result) == 12  # 3 * 2 * 2 = 12
    assert all(result["status"] == "done")


#disable @pytest.mark.flaky(reruns=5)  # Random failures, may need multiple retries
def test_failure_random_fails_retries(advanced_setup):
    """Test failure support - sometimes fails but retries - from examples.md lines 471-484"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressureRandomFails.sh"] * 3, results_dir="results")

    assert len(result) == 12
    # Should eventually succeed with retries
    assert sum(result["status"] == "done") >= 6  # At least half should succeed with retries


def test_failure_always_fails(advanced_setup):
    """Test failure support - always fails - from examples.md lines 487-500"""
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressureAlwaysFails.sh"] * 3, results_dir="results")

    assert len(result) == 12
    # All should fail
    assert all(result["status"] == "failed")
    # All pressure values should be None
    assert all(p is None for p in result["pressure"])


def test_failure_cache_with_fallback(advanced_setup):
    """Test cache with fallback after failures - from examples.md lines 503-516"""
    # First run that will fail and cache failures
    fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressureAlwaysFails.sh"] * 3, results_dir="results_fail")

    # Second run with cache and successful calculator
    result = fz.fzr("input.txt", {
        "T_celsius": [20, 25, 30],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["cache://_", "sh:///bin/bash ./PerfectGazPressure.sh", "sh:///bin/bash ./PerfectGazPressure.sh"], results_dir="results_fail")

    assert len(result) == 12
    # Should now succeed since fallback calculator is successful
    assert all(result["status"] == "done")


def test_non_numeric_variables(advanced_setup):
    """Test non-numeric variables with some wrong values - from examples.md lines 521-534"""
    result = fz.fzr("input.txt", {
        "T_celsius": ["20", "25", "abc"],
        "V_L": [1, 1.5],
        "n_mol": [1, 0]
    }, {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
    }, calculators=["sh:///bin/bash ./PerfectGazPressure.sh"] * 3, results_dir="results")

    assert len(result) == 12  # 3 * 2 * 2 = 12
    # Cases with "abc" should fail
    failed_cases = result[result["T_celsius"] == "abc"]
    assert len(failed_cases) == 4  # 1 * 2 * 2 = 4
    assert all(failed_cases["status"] == "done") # do not expect "failed", as it is a failure due to wrong input, not calculation failure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
