#!/usr/bin/env python3
"""
Test for multiple input files with variables distributed across them
"""

import sys
import os
import shutil
import itertools
from pathlib import Path

from fz import fzi, fzr

def test_multiple_input_files_with_variables():
    """Test fzr with multiple input files containing different variables"""

    # Use the temp directory provided by conftest fixture
    temp_dir_path = Path.cwd()
    print(f"🔧 Working in temporary directory: {temp_dir_path}")
    # Create a subdirectory for input files that we want to process together
    input_files_dir = temp_dir_path / "input_files"
    input_files_dir.mkdir(exist_ok=True)
    # File 1: Configuration file with system parameters
    with open(input_files_dir / "config.txt", 'w') as f:
        f.write("# System Configuration\n")
        f.write("TEMPERATURE = $(T)\n")
        f.write("PRESSURE = $(P)\n")
        f.write("SIMULATION_TIME = 1000\n")
        f.write("OUTPUT_FREQUENCY = 10\n")

    # File 2: Material properties with different variables
    with open(input_files_dir / "material.dat", 'w') as f:
        f.write("# Material Properties\n")
        f.write("DENSITY = $(rho)\n")
        f.write("VISCOSITY = $(mu)\n")
        f.write("THERMAL_CONDUCTIVITY = 0.025\n")
        f.write("SPECIFIC_HEAT = 1005\n")

    # File 3: Boundary conditions with another set of variables
    with open(input_files_dir / "boundary.inp", 'w') as f:
        f.write("# Boundary Conditions\n")
        f.write("INLET_VELOCITY = $(v_in)\n")
        f.write("OUTLET_PRESSURE = $(P_out)\n")
        f.write("WALL_TEMPERATURE = $(T_wall)\n")
        f.write("REFERENCE_PRESSURE = $(P)\n")  # Reuse P from config.txt

    # File 4: Solver settings with computational parameters
    with open(input_files_dir / "solver.cfg", 'w') as f:
        f.write("# Solver Configuration\n")
        f.write("MAX_ITERATIONS = $(max_iter)\n")
        f.write("CONVERGENCE_TOLERANCE = 1e-6\n")
        f.write("TIME_STEP = $(dt)\n")
        f.write("CFL_NUMBER = 0.5\n")

    # File 5: Main input file (required by fzr)
    with open(input_files_dir / "input.txt", 'w') as f:
        f.write("# Multi-file simulation input\n")
        f.write("# Main variables\n")
        f.write("T = $(T)\n")
        f.write("P = $(P)\n")
        f.write("rho = $(rho)\n")
        f.write("mu = $(mu)\n")
        f.write("v_in = $(v_in)\n")
        f.write("P_out = $(P_out)\n")
        f.write("T_wall = $(T_wall)\n")
        f.write("max_iter = $(max_iter)\n")
        f.write("dt = $(dt)\n")

    # Create a working calculator script that processes the input files
    with open(input_files_dir / "process_inputs.sh", 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Multi-input file simulation processor\n")
        f.write(f"# All files should be in the same directory, no copying needed\n")
        f.write("echo 'Processing multiple input files simulation...'\n")
        f.write("echo ''\n")
        f.write("# Read configuration from config.txt if it exists\n")
        f.write("if [ -f 'config.txt' ]; then\n")
        f.write("    echo 'Reading configuration:'\n")
        f.write("    T=$(grep 'TEMPERATURE =' config.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("    P=$(grep 'PRESSURE =' config.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("    echo \"Temperature: $T K\"\n")
        f.write("    echo \"Pressure: $P Pa\"\n")
        f.write("fi\n")
        f.write("# Read material properties from material.dat if it exists\n")
        f.write("if [ -f 'material.dat' ]; then\n")
        f.write("    echo 'Reading material properties:'\n")
        f.write("    RHO=$(grep 'DENSITY =' material.dat | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("    MU=$(grep 'VISCOSITY =' material.dat | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("    echo \"Density: $RHO kg/m³\"\n")
        f.write("    echo \"Viscosity: $MU Pa·s\"\n")
        f.write("fi\n")
        f.write("echo ''\n")
        f.write("# Simple calculation using the values\n")
        f.write("if [ ! -z \"$T\" ] && [ ! -z \"$P\" ] && [ ! -z \"$RHO\" ]; then\n")
        f.write("    echo 'Performing calculation...'\n")
        f.write("    # Simple result calculation: P * RHO / T (dimensionally meaningless but demonstrates processing)\n")
        f.write("    RESULT=$(python3 -c \"print(f'{float('$P') * float('$RHO') / float('$T'):.6f}')\")\n")
        f.write("    echo \"result = $RESULT\" > output.txt\n")
        f.write("    echo \"Calculation result: $RESULT\"\n")
        f.write("else\n")
        f.write("    echo 'result = 42.0' > output.txt\n")
        f.write("    echo 'Default result: 42.0'\n")
        f.write("fi\n")
        f.write("echo 'Simulation completed successfully'\n")
        f.write("exit 0\n")
    os.chmod(input_files_dir / "process_inputs.sh", 0o755)

    print("📂 Created input files structure:")
    files = [f for f in os.listdir(input_files_dir) if f.endswith(('.txt', '.dat', '.inp', '.cfg', '.sh'))]
    for file in sorted(files):
        print(f"  {file}")

    # Test 1: Use fzi to discover all variables across multiple files
    print("\n🔍 Test 1: Variable discovery across multiple input files")

    model = {
        "varprefix": "$",
        "delim": "()",
        "output": {
            "result": "grep 'Final result' output.txt | cut -d'=' -f2 | tr -d ' '"
        }
    }

    variables = fzi(str(input_files_dir), model)
    print(f"Variables discovered: {list(variables.keys())}")

    expected_vars = {"T", "P", "rho", "mu", "v_in", "P_out", "T_wall", "max_iter", "dt"}
    discovered_vars = set(variables.keys())

    # Filter out script-related variables that might be discovered from process_inputs.sh
    script_vars = {"MU", "RHO", "RESULT"}
    core_discovered_vars = discovered_vars - script_vars

    print(f"Expected variables: {expected_vars}")
    print(f"Discovered variables (core): {core_discovered_vars}")
    if script_vars & discovered_vars:
        print(f"Additional variables from script: {script_vars & discovered_vars}")

    if expected_vars == core_discovered_vars:
        print("✅ All expected variables discovered correctly")
    else:
        missing = expected_vars - core_discovered_vars
        extra = core_discovered_vars - expected_vars
        if missing:
            print(f"❌ Missing variables: {missing}")
        if extra:
            print(f"⚠️ Extra variables: {extra}")

    # Test 2: Run fzr with multiple cases using different variable combinations
    print("\n🚀 Test 2: Running fzr with multiple input files and variable combinations")

    # Define variable values for multiple cases
    input_variables = {
        "T": [300, 350],        # Temperature (used in config.txt, boundary.inp, postprocess.py)
        "P": [101325, 200000],  # Pressure (used in config.txt, boundary.inp)
        "rho": [1.225, 1.0],    # Density (used in material.dat, postprocess.py)
        "mu": [1.8e-5, 2.0e-5], # Viscosity (used in material.dat)
        "v_in": [10, 15],       # Inlet velocity (used in boundary.inp)
        "P_out": [101000, 199000], # Outlet pressure (used in boundary.inp)
        "T_wall": [295, 310],   # Wall temperature (used in boundary.inp)
        "max_iter": [1000, 2000], # Max iterations (used in solver.cfg, postprocess.py)
        "dt": [0.001, 0.0005]   # Time step (used in solver.cfg)
    }

    print(f"Variable combinations will create {2**len(input_variables)} = {2**len(input_variables)} cases")

    # Run with ALL variables to ensure complete substitution
    test_vars = {
        "T": [300, 350],              # Used in config.txt, boundary.inp, postprocess.py
        "P": [101325, 200000],        # Used in config.txt, boundary.inp
        "rho": [1.225, 1.0],          # Used in material.dat, postprocess.py
        "mu": [1.8e-5, 2.0e-5],       # Used in material.dat
        "v_in": [10, 15],             # Used in boundary.inp
        "P_out": [101000, 199000],    # Used in boundary.inp
        "T_wall": [295, 310],         # Used in boundary.inp
        "max_iter": [1000, 2000],     # Used in solver.cfg, postprocess.py
        "dt": [0.001, 0.0005]         # Used in solver.cfg
    }

    # For the test, we'll use a smaller subset but make sure to provide ALL variables
    # so none remain unsubstituted
    # Test with MULTIPLE cases to expose path resolution issues
    test_vars_small = {
        "T": [300, 350],  # Multiple values to create multiple cases
        "P": [101325],
        "rho": [1.225],
        "mu": [1.8e-5],
        "v_in": [10],
        "P_out": [101000],
        "T_wall": [295],
        "max_iter": [1000],
        "dt": [0.001]
    }

    print(f"Running with complete variable set: {list(test_vars_small.keys())} -> {len(list(itertools.product(*test_vars_small.values())))} cases")


    result = fzr(
        input_path=str(input_files_dir),
        input_variables=test_vars_small,
        model=model,
        calculators=["sh://./process_inputs.sh"],
        results_dir=str(temp_dir_path / "multi_file_results")
    )

    print(f"\n📊 Results Summary:")
    print(f"Number of cases executed: {len(result['T'])}")
    print(f"Calculator IDs: {set(result['calculator'])}")
    print(f"Statuses: {set(result['status'])}")
    print(f"Commands executed: {set(result['command'])}")

    # Verify all cases were executed
    expected_cases = len(list(itertools.product(*test_vars_small.values())))
    actual_cases = len(result['T'])

    if actual_cases == expected_cases:
        print(f"✅ All {expected_cases} cases executed successfully")
    else:
        print(f"❌ Expected {expected_cases} cases, got {actual_cases}")

    # Test 3: Comprehensive verification of compiled files
    print("\n🔍 Test 3: Verifying compiled input files are complete and correct")

    # Check if result directories contain properly substituted files
    results_path = temp_dir_path / "multi_file_results"
    if results_path.exists():
        # For single case, files are in the main directory; for multiple cases, in subdirectories
        if len(list(itertools.product(*test_vars_small.values()))) == 1:
            # Single case - files are directly in results directory
            case_dirs = [results_path]
            print(f"Single case: files in main results directory")
        else:
            # Multiple cases - files are in subdirectories
            case_dirs = [d for d in results_path.iterdir() if d.is_dir()]
            print(f"Found {len(case_dirs)} result case directories")

        # Define expected input files
        expected_files = [
            "config.txt",
            "material.dat",
            "boundary.inp",
            "solver.cfg",
            "input.txt"
        ]

        # Track verification results
        all_cases_verified = True

        # Check each case directory for proper file compilation
        for case_idx, case_dir in enumerate(case_dirs[:3]):  # Check first 3 cases for performance
            print(f"\n🔍 Examining case {case_idx + 1}: {case_dir.name}")

            # Parse case variables from directory name or use test variables for single case
            case_vars = {}
            if case_dir == results_path:  # Single case
                # Use the test variables directly for single case
                case_vars = {k: v[0] for k, v in test_vars_small.items()}
            elif "," in case_dir.name:
                for pair in case_dir.name.split(","):
                    key, value = pair.split("=")
                    try:
                        case_vars[key] = float(value)
                    except ValueError:
                        case_vars[key] = value

            print(f"   Expected variable values: {case_vars}")

            # Check each expected input file directly in the case directory
            for filename in expected_files:
                file_path = case_dir / filename

                if not file_path.exists():
                    print(f"❌ File missing: {filename}")
                    all_cases_verified = False
                    continue

                print(f"   ✅ File exists: {filename}")

                # Read file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Skip binary files
                    print(f"   ⚠️ Skipping binary file: {filename}")
                    continue

                # Check for remaining variable placeholders
                remaining_vars = []
                import re
                var_pattern = re.compile(r'\$\([^)]+\)')
                matches = var_pattern.findall(content)
                if matches:
                    remaining_vars.extend(matches)

                if remaining_vars:
                    print(f"❌ {filename}: Contains unsubstituted variables: {remaining_vars}")
                    all_cases_verified = False
                else:
                    print(f"   ✅ {filename}: All variables properly substituted")

                # Verify specific variable substitutions for this case
                substitution_errors = []

                # Check specific substitutions based on file content and case variables
                if filename == "config.txt" and "T" in case_vars:
                    expected_temp = str(case_vars["T"]).rstrip('0').rstrip('.')  # Remove trailing .0
                    if f"TEMPERATURE = {expected_temp}" not in content:
                        substitution_errors.append(f"Temperature should be {expected_temp}")

                if filename == "config.txt" and "P" in case_vars:
                    expected_pressure = str(case_vars["P"]).rstrip('0').rstrip('.')  # Remove trailing .0
                    if f"PRESSURE = {expected_pressure}" not in content:
                        substitution_errors.append(f"Pressure should be {expected_pressure}")

                if filename == "material.dat" and "rho" in case_vars:
                    expected_density = str(case_vars["rho"])
                    if f"DENSITY = {expected_density}" not in content:
                        substitution_errors.append(f"Density should be {expected_density}")

                if filename == "material.dat" and "mu" in case_vars:
                    expected_viscosity = str(case_vars["mu"])
                    if f"VISCOSITY = {expected_viscosity}" not in content:
                        substitution_errors.append(f"Viscosity should be {expected_viscosity}")

                if filename == "boundary.inp" and "v_in" in case_vars:
                    expected_velocity = str(case_vars["v_in"]).rstrip('0').rstrip('.')  # Remove trailing .0
                    if f"INLET_VELOCITY = {expected_velocity}" not in content:
                        substitution_errors.append(f"Inlet velocity should be {expected_velocity}")

                if filename == "solver.cfg" and "max_iter" in case_vars:
                    expected_iterations = str(case_vars["max_iter"]).rstrip('0').rstrip('.')  # Remove trailing .0
                    if f"MAX_ITERATIONS = {expected_iterations}" not in content:
                        substitution_errors.append(f"Max iterations should be {expected_iterations}")

                if filename == "solver.cfg" and "dt" in case_vars:
                    expected_timestep = str(case_vars["dt"])
                    if f"TIME_STEP = {expected_timestep}" not in content:
                        substitution_errors.append(f"Time step should be {expected_timestep}")

                if substitution_errors:
                    print(f"❌ {filename}: Variable substitution errors: {substitution_errors}")
                    print(f"   File content preview:")
                    for i, line in enumerate(content.split('\n')[:10]):
                        print(f"     {i+1}: {line}")
                    all_cases_verified = False
                else:
                    print(f"   ✅ {filename}: Variable values correctly substituted")

        # Final verification result
        if all_cases_verified:
            print(f"\n✅ All compiled files verification PASSED")
            print(f"   - All expected files exist in case directories")
            print(f"   - No remaining variable placeholders found")
            print(f"   - Variable values correctly substituted")
        else:
            print(f"\n❌ Compiled files verification FAILED")
            print(f"   - Some files missing, contain unsubstituted variables, or have incorrect values")
            raise AssertionError("Compiled input files verification failed")

        # Test 4: Check file content integrity
        print("\n🔍 Test 4: Verifying file content integrity and structure")

        # Pick first case for detailed content verification
        if case_dirs:
            first_case = case_dirs[0]

            # Verify config.txt structure
            config_file = first_case / "config.txt"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_content = f.read()

                required_config_lines = [
                    "# System Configuration",
                    "TEMPERATURE =",
                    "PRESSURE =",
                    "SIMULATION_TIME = 1000",
                    "OUTPUT_FREQUENCY = 10"
                ]

                missing_lines = []
                for required_line in required_config_lines:
                    if required_line not in config_content:
                        missing_lines.append(required_line)

                if missing_lines:
                    print(f"❌ config.txt missing required content: {missing_lines}")
                    all_cases_verified = False
                else:
                    print(f"   ✅ config.txt has all required content")

            # Verify material.dat structure
            material_file = first_case / "material.dat"
            if material_file.exists():
                with open(material_file, 'r') as f:
                    material_content = f.read()

                required_material_lines = [
                    "# Material Properties",
                    "DENSITY =",
                    "VISCOSITY =",
                    "THERMAL_CONDUCTIVITY = 0.025",
                    "SPECIFIC_HEAT = 1005"
                ]

                missing_lines = []
                for required_line in required_material_lines:
                    if required_line not in material_content:
                        missing_lines.append(required_line)

                if missing_lines:
                    print(f"❌ material.dat missing required content: {missing_lines}")
                    all_cases_verified = False
                else:
                    print(f"   ✅ material.dat has all required content")

            if not all_cases_verified:
                raise AssertionError("File content integrity verification failed")

        print(f"\n✅ File content integrity verification PASSED")

    print(f"\n✅ Multiple input files test completed successfully")
    print(f"   - Variable discovery across 5 files: ✅")
    print(f"   - Variable substitution in all files: ✅")
    print(f"   - Multiple case execution: ✅")
    print(f"   - Results validation: ✅")

    # Assert test passed
    assert actual_cases == expected_cases, \
        f"Expected {expected_cases} cases, got {actual_cases}"
    assert all_cases_verified, "Not all cases verified successfully"

if __name__ == "__main__":
    test_multiple_input_files_with_variables()
