#!/usr/bin/env python3
"""
Test fzo/fzr coherence: verify that fzo() output matches fzr() results

This test suite ensures that when fzr() completes successfully, calling fzo()
on the results directory produces the same output values.
"""

import os
import sys
from pathlib import Path
import pytest
import platform

import fz

try:
    import pandas as pd
except ImportError:


def _get_value(result, key, index):
    """Helper to get value from DataFrame or dict"""
    if isinstance(result, pd.DataFrame):
        value = result[key].iloc[index]
        # Convert numpy types to native Python types
        if hasattr(value, 'item'):
            return value.item()
        return value
    else:
        return result[key][index]


def _get_length(result, key):
    """Helper to get length from DataFrame or dict"""
    if isinstance(result, pd.DataFrame):
        return len(result[key])
    else:
        return len(result[key])

def test_fzo_fzr_coherence_novariables():
    """Test that fzo output matches fzr results when no variables are used"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('constant_value = 123\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\necho "result = 99" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
            }
    variables = {}  # No variables

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="novar_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("novar_results", model)

    # Verify coherence
    assert "result" in fzr_result, "result not in fzr output"
    assert "result" in fzo_result, "result not in fzo output"

    fzr_res = _get_value(fzr_result, "result", 0)
    fzo_res = _get_value(fzo_result, "result", 0)
            # cast_output() converts "99" to int 99
    assert fzr_res == 99, f"fzr result={fzr_res}, expected 99"
    assert fzo_res == 99, f"fzo result={fzo_res}, expected 99"
    assert fzr_res == fzo_res, f"Result mismatch: fzr={fzr_res}, fzo={fzo_res}"

    print("✅ No variables: fzo matches fzr (outputs only)")

def test_fzo_fzr_coherence_single_case():
    """Test that fzo output matches fzr results for single case"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('Temperature: ${T} K\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\necho "result = 42" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
            }
    variables = {"T": 300}

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="test_1results")
    print("fzr_result:", fzr_result)

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("test_1results/*", model)
    print("fzo_result:", fzo_result)

    # Verify coherence
    assert "result" in fzr_result, "result not in fzr output"
    assert "result" in fzo_result, "result not in fzo output"

    fzr_res = _get_value(fzr_result, "result", 0)
    fzo_res = _get_value(fzo_result, "result", 0)
            # cast_output() converts "42" to int 42
    assert fzr_res == 42, f"fzr result={fzr_res}, expected 42"
    assert fzo_res == 42, f"fzo result={fzo_res}, expected 42"
    assert fzr_res == fzo_res, f"Result mismatch: fzr={fzr_res}, fzo={fzo_res}"

    # For single case, fzr includes variable in results but fzo doesn't
    # (since it can't extract from directory name when using results dir directly)
    fzr_t = _get_value(fzr_result, "T", 0)
    assert fzr_t == 300, f"fzr T={fzr_t}, expected 300"
    # fzo won't have T variable for single case - this is expected

    # Verify path coherence for single case
    fzr_path = _get_value(fzr_result, "path", 0)
    fzo_path = _get_value(fzo_result, "path", 0)
    # support windows & python 3.9 : convert to absolute paths
    if sys.version_info <= (3, 9) and platform.system() == 'Windows':
        assert os.path.abspath(fzr_path) == os.path.abspath(fzo_path), f"Path mismatch: fzr={fzr_path}, fzo={fzo_path}"
    else:
        assert fzr_path == fzo_path, f"Path mismatch: fzr={fzr_path}, fzo={fzo_path}"

    print("✅ Single case: fzo matches fzr (outputs only)")


def test_fzo_fzr_coherence_multiple_cases():
    """Test that fzo output matches fzr results for multiple cases"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('T=${T}\nP=${P}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\n')
                f.write('source input.txt\n')
                f.write('RESULT=$((T * P))\n')
                f.write('echo "result = $RESULT" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
            }
    variables = {"T": [100, 200, 300], "P": [1, 2]}  # 6 cases

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="multi_results")
            
    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("multi_results/*", model)

    # Verify coherence
    fzr_len = _get_length(fzr_result, "result")
    fzo_len = _get_length(fzo_result, "result")
    assert fzr_len == 6, f"Expected 6 results from fzr, got {fzr_len}"
    assert fzo_len == 6, f"Expected 6 results from fzo, got {fzo_len}"

    for i in range(6):
        fzr_res = _get_value(fzr_result, "result", i)
        fzo_res = _get_value(fzo_result, "result", i)
        assert fzr_res == fzo_res, \
                    f"Case {i}: fzr={fzr_res}, fzo={fzo_res}"

        fzr_t = _get_value(fzr_result, "T", i)
        fzo_t = _get_value(fzo_result, "T", i)
        assert fzr_t == fzo_t, f"Case {i} T: fzr={fzr_t}, fzo={fzo_t}"

        fzr_p = _get_value(fzr_result, "P", i)
        fzo_p = _get_value(fzo_result, "P", i)
        assert fzr_p == fzo_p, f"Case {i} P: fzr={fzr_p}, fzo={fzo_p}"

        # Verify path coherence (both should include results directory)
        fzr_path = _get_value(fzr_result, "path", i)
        fzo_path = _get_value(fzo_result, "path", i)
        # support windows & python 3.9 : convert to absolute paths
        if sys.version_info <= (3, 9) and platform.system() == 'Windows':
            assert os.path.abspath(fzr_path) == os.path.abspath(fzo_path), f"Case {i} path: fzr={fzr_path}, fzo={fzo_path}"
        else:
            assert fzr_path == fzo_path, f"Case {i} path: fzr={fzr_path}, fzo={fzo_path}"

    print("✅ Multiple cases: fzo matches fzr")


def test_fzo_fzr_coherence_multiple_outputs():
    """Test fzo/fzr coherence with multiple output values"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('X=${X}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\n')
                f.write('source input.txt\n')
                f.write('echo "square = $((X * X))" > output1.txt\n')
                f.write('echo "cube = $((X * X * X))" > output2.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {
                    "square": "grep 'square = ' output1.txt | cut -d '=' -f2",
                    "cube": "grep 'cube = ' output2.txt | cut -d '=' -f2"
                }
            }
    variables = {"X": [2, 3, 4, 5]}  # 4 cases

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="multi_output_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("multi_output_results/*", model)

    # Verify coherence
    assert _get_length(fzr_result, "square") == 4
    assert _get_length(fzo_result, "square") == 4

    for i in range(4):
        fzr_sq = _get_value(fzr_result, "square", i)
        fzo_sq = _get_value(fzo_result, "square", i)
        assert fzr_sq == fzo_sq, f"Case {i} square: fzr={fzr_sq}, fzo={fzo_sq}"

        fzr_cube = _get_value(fzr_result, "cube", i)
        fzo_cube = _get_value(fzo_result, "cube", i)
        assert fzr_cube == fzo_cube, f"Case {i} cube: fzr={fzr_cube}, fzo={fzo_cube}"

        fzr_x = _get_value(fzr_result, "X", i)
        fzo_x = _get_value(fzo_result, "X", i)
        assert fzr_x == fzo_x, f"Case {i} X: fzr={fzr_x}, fzo={fzo_x}"

    print("✅ Multiple outputs: fzo matches fzr")


def test_fzo_fzr_coherence_with_formulas():
    """Test fzo/fzr coherence with formula evaluation"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('base = ${base}\n')
                f.write('multiplier = ${mult}\n')
                f.write('#@ def calculate(b, m):\n')
                f.write('#@     return b * m + 10\n')
                f.write('result = @{calculate(${base}, ${mult})}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\n')
                f.write('source input.txt\n')
                f.write('echo "computed = $result" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "formulaprefix": "@",
                "delim": "{}",
                "commentline": "#",
                "output": {"computed": "grep 'computed = ' output.txt | cut -d '=' -f2"}
            }
    variables = {"base": [5], "mult": [2]}  # 1 cases

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="formula_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("formula_results/*", model)

    print("fzo_result:", fzo_result)
    print("fzr_result:", fzr_result)

    # Verify coherence
    for i in range(1):
        fzr_comp = _get_value(fzr_result, "computed", i)
        fzo_comp = _get_value(fzo_result, "computed", i)
        assert fzr_comp == fzo_comp, f"Case {i} computed: fzr={fzr_comp}, fzo={fzo_comp}"

        fzr_base = _get_value(fzr_result, "base", i)
        fzo_base = _get_value(fzo_result, "base", i)
        assert fzr_base == fzo_base, f"Case {i} base: fzr={fzr_base}, fzo={fzo_base}"

        fzr_mult = _get_value(fzr_result, "mult", i)
        fzo_mult = _get_value(fzo_result, "mult", i)
        assert fzr_mult == fzo_mult

    print("✅ Formula evaluation: fzo matches fzr")


def test_fzo_fzr_coherence_with_failures():
    """Test fzo/fzr coherence when some cases fail"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('value = ${value}\n')

            # Calculator that fails for value=2
    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\n')
                f.write('source input.txt\n')
                f.write('if [ "$value" -eq "2" ]; then\n')
                f.write('  exit 1\n')
                f.write('fi\n')
                f.write('echo "result = $((value * 10))" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
            }
    variables = {"value": [1, 2, 3]}  # Case 2 will fail

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash calc.sh",
                                results_dir="failure_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("failure_results/*", model)

    # Verify coherence - both should handle failures the same way
            # Successful cases should have matching results
    fzr_len = _get_length(fzr_result, "result")
    fzo_len = _get_length(fzo_result, "result")
    assert fzr_len == fzo_len

    for i in range(fzr_len):
        # For successful cases, results should match
        fzr_status = _get_value(fzr_result, "status", i)
        if fzr_status == "done":
            fzr_res = _get_value(fzr_result, "result", i)
            fzo_res = _get_value(fzo_result, "result", i)
            assert fzr_res == fzo_res, f"Case {i} result: fzr={fzr_res}, fzo={fzo_res}"

    print("✅ Partial failures: fzo matches fzr")


def test_fzo_fzr_coherence_perfectgaz_example():
    """Test fzo/fzr coherence with realistic perfect gas example"""

    # Use temp directory from conftest fixture

    # Setup realistic perfect gas example
    with open('input.txt', 'w') as f:
                f.write('# Perfect Gas Law: PV = nRT\n')
                f.write('T_celsius = ${T_celsius}\n')
                f.write('V_L = ${V_L}\n')
                f.write('n_mol = ${n_mol}\n')

    with open('PerfectGazPressure.sh', 'w', newline='\n') as f:
                f.write('#!/bin/bash\n')
                f.write('source input.txt\n')
                f.write('# Convert Celsius to Kelvin\n')
                #f.write('T_K=$(echo "$T_celsius + 273.15" | bc -l)\n')
                f.write('T_K=$(python3 -c "print($T_celsius + 273.15)")\n')
                f.write('# R = 8.314 J/(mol·K), convert to L·Pa\n')
                f.write('R=8314\n')
                f.write('# Calculate pressure: P = nRT/V\n')
                #f.write('P=$(echo "$n_mol * $R * $T_K / $V_L" | bc -l)\n')
                f.write('P=$(python3 -c "print(round($n_mol * $R * $T_K / $V_L, 4))")\n')
                f.write('printf "pressure = %.2f\\n" "$P" > output.txt\n')
    os.chmod('PerfectGazPressure.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "commentline": "#",
                "output": {"pressure": "grep 'pressure = ' output.txt | cut -d '=' -f2"}
            }

            # Test with multiple temperature and volume combinations
    variables = {
                "T_celsius": [20, 25, 30],
                "V_L": [1, 2],
                "n_mol": 1
            }  # 6 cases total

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://bash PerfectGazPressure.sh",
                                results_dir="perfectgaz_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("perfectgaz_results/*", model)

    # Verify coherence
    assert _get_length(fzr_result, "pressure") == 6
    assert _get_length(fzo_result, "pressure") == 6

    for i in range(6):
        fzr_press = _get_value(fzr_result, "pressure", i)
        fzo_press = _get_value(fzo_result, "pressure", i)
        assert fzr_press == fzo_press, f"Case {i} pressure: fzr={fzr_press}, fzo={fzo_press}"

        fzr_t = _get_value(fzr_result, "T_celsius", i)
        fzo_t = _get_value(fzo_result, "T_celsius", i)
        assert fzr_t == fzo_t

        fzr_v = _get_value(fzr_result, "V_L", i)
        fzo_v = _get_value(fzo_result, "V_L", i)
        assert fzr_v == fzo_v

        fzr_n = _get_value(fzr_result, "n_mol", i)
        fzo_n = _get_value(fzo_result, "n_mol", i)
        assert fzr_n == fzo_n

    print("✅ Perfect gas example: fzo matches fzr")


def test_fzo_fzr_coherence_simple_echo():
    """Test fzo/fzr coherence with simple echo commands (cross-platform)"""

    # Use temp directory from conftest fixture

    # Setup simple test that works on all platforms
    with open('input.txt', 'w') as f:
                f.write('x=${x}\ny=${y}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/sh\n')
                f.write('echo "output = test" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"output": "cat output.txt | grep output | cut -d= -f2 | tr -d ' '"}
            }
    variables = {"x": [1, 2, 3], "y": [10, 20]}  # 6 cases

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://sh calc.sh",
                                results_dir="echo_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("echo_results/*", model)

    # Verify coherence
    fzr_len = _get_length(fzr_result, "output")
    fzo_len = _get_length(fzo_result, "output")
    assert fzr_len == 6, f"Expected 6 results from fzr, got {fzr_len}"
    assert fzo_len == 6, f"Expected 6 results from fzo, got {fzo_len}"

    for i in range(6):
        fzr_out = _get_value(fzr_result, "output", i)
        fzo_out = _get_value(fzo_result, "output", i)
        assert fzr_out == fzo_out, f"Case {i}: fzr={fzr_out}, fzo={fzo_out}"

        fzr_x = _get_value(fzr_result, "x", i)
        fzo_x = _get_value(fzo_result, "x", i)
        assert fzr_x == fzo_x, f"Case {i} x: fzr={fzr_x}, fzo={fzo_x}"

        fzr_y = _get_value(fzr_result, "y", i)
        fzo_y = _get_value(fzo_result, "y", i)
        assert fzr_y == fzo_y, f"Case {i} y: fzr={fzr_y}, fzo={fzo_y}"

    print("✅ Simple echo: fzo matches fzr")


def test_fzo_fzr_coherence_three_variables():
    """Test fzo/fzr coherence with three variables (more complex sorting)"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('a=${a}\nb=${b}\nc=${c}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/sh\n')
                f.write('echo "result = ok" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "cat output.txt | grep result | cut -d= -f2 | tr -d ' '"}
            }
            # 2x2x3 = 12 cases
    variables = {"a": [1, 2], "b": [10, 20], "c": [100, 200, 300]}

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://sh calc.sh",
                                results_dir="three_var_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("three_var_results/*", model)

    # Verify coherence
    assert _get_length(fzr_result, "result") == 12
    assert _get_length(fzo_result, "result") == 12

    for i in range(12):
        fzr_a = _get_value(fzr_result, "a", i)
        fzo_a = _get_value(fzo_result, "a", i)
        assert fzr_a == fzo_a, f"Case {i} a: fzr={fzr_a}, fzo={fzo_a}"

        fzr_b = _get_value(fzr_result, "b", i)
        fzo_b = _get_value(fzo_result, "b", i)
        assert fzr_b == fzo_b, f"Case {i} b: fzr={fzr_b}, fzo={fzo_b}"

        fzr_c = _get_value(fzr_result, "c", i)
        fzo_c = _get_value(fzo_result, "c", i)
        assert fzr_c == fzo_c, f"Case {i} c: fzr={fzr_c}, fzo={fzo_c}"

    print("✅ Three variables: fzo matches fzr")


def test_fzo_fzr_coherence_float_values():
    """Test fzo/fzr coherence with float variable values"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('temp=${temp}\npressure=${pressure}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/sh\n')
                f.write('echo "measurement = 42.5" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"measurement": "cat output.txt | grep measurement | cut -d= -f2 | tr -d ' '"}
            }
            # Float values should be sorted numerically
    variables = {"temp": [20.5, 25.0, 30.5], "pressure": [1.0, 1.5]}

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://sh calc.sh",
                                results_dir="float_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)

    # Parse with fzo
    fzo_result = fz.fzo("float_results/*", model)

    # Verify coherence - 3x2 = 6 cases
    assert _get_length(fzr_result, "measurement") == 6
    assert _get_length(fzo_result, "measurement") == 6

    for i in range(6):
        fzr_temp = _get_value(fzr_result, "temp", i)
        fzo_temp = _get_value(fzo_result, "temp", i)
        assert fzr_temp == fzo_temp, f"Case {i} temp: fzr={fzr_temp}, fzo={fzo_temp}"

        fzr_press = _get_value(fzr_result, "pressure", i)
        fzo_press = _get_value(fzo_result, "pressure", i)
        assert fzr_press == fzo_press, f"Case {i} pressure: fzr={fzr_press}, fzo={fzo_press}"

    print("✅ Float values: fzo matches fzr")


def test_fzo_fzr_coherence_large_grid():
    """Test fzo/fzr coherence with larger parameter grid"""

    # Use temp directory from conftest fixture

    # Setup
    with open('input.txt', 'w') as f:
                f.write('p1=${p1}\np2=${p2}\n')

    with open('calc.sh', 'w', newline='\n') as f:
                f.write('#!/bin/sh\n')
                f.write('echo "value = computed" > output.txt\n')
    os.chmod('calc.sh', 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"value": "cat output.txt | grep value | cut -d= -f2 | tr -d ' '"}
            }
            # 5x4 = 20 cases
    variables = {"p1": [1, 2, 3, 4, 5], "p2": [10, 20, 30, 40]}

    # Run fzr
    fzr_result = fz.fzr("input.txt", variables, model,
                                calculators="sh://sh calc.sh",
                                results_dir="large_grid_results")

    # Add delay (mainly fo windows) to ensure files are flushed
    import time
    time.sleep(1)
            
    # Parse with fzo
    fzo_result = fz.fzo("large_grid_results/*", model)

    # Verify coherence - 20 cases
    assert _get_length(fzr_result, "value") == 20
    assert _get_length(fzo_result, "value") == 20

    for i in range(20):
        fzr_p1 = _get_value(fzr_result, "p1", i)
        fzo_p1 = _get_value(fzo_result, "p1", i)
        assert fzr_p1 == fzo_p1, f"Case {i} p1: fzr={fzr_p1}, fzo={fzo_p1}"

        fzr_p2 = _get_value(fzr_result, "p2", i)
        fzo_p2 = _get_value(fzo_result, "p2", i)
        assert fzr_p2 == fzo_p2, f"Case {i} p2: fzr={fzr_p2}, fzo={fzo_p2}"

    print("✅ Large grid (20 cases): fzo matches fzr")


if __name__ == "__main__":
    """Run all fzo/fzr coherence tests"""
    print("🧪 Running fzo/fzr Coherence Tests")
    print("=" * 60)

    try:
        test_fzo_fzr_coherence_single_case()
        test_fzo_fzr_coherence_multiple_cases()
        test_fzo_fzr_coherence_multiple_outputs()
        test_fzo_fzr_coherence_with_formulas()
        test_fzo_fzr_coherence_with_failures()
        test_fzo_fzr_coherence_perfectgaz_example()

        print("\n" + "=" * 60)
        print("🎉 All fzo/fzr coherence tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)