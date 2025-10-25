# FZ - Parametric Scientific Computing Framework

[![CI](https://github.com/Funz/fz/workflows/CI/badge.svg)](https://github.com/Funz/fz/actions/workflows/ci.yml)
<!--
[![Python Version](https://img.shields.io/pypi/pyversions/funz.svg)](https://pypi.org/project/funz/)
-->
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Version](https://img.shields.io/badge/version-0.9.0-blue.svg)](https://github.com/Funz/fz/releases)

A powerful Python package for parametric simulations and computational experiments. FZ wraps your simulation codes to automatically run parametric studies, manage input/output files, handle parallel execution, and collect results in structured DataFrames.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Core Functions](#core-functions)
- [Model Definition](#model-definition)
- [Calculator Types](#calculator-types)
- [Advanced Features](#advanced-features)
- [Complete Examples](#complete-examples)
- [Writing Custom Algorithms for fzd](#writing-custom-algorithms-for-fzd)
- [Configuration](#configuration)
- [Interrupt Handling](#interrupt-handling)
- [Development](#development)

## Features

### Core Capabilities

- **🔄 Parametric Studies**: Factorial designs (dict with Cartesian product) or non-factorial designs (DataFrame with specific cases)
- **⚡ Parallel Execution**: Run multiple cases concurrently across multiple calculators with automatic load balancing
- **💾 Smart Caching**: Reuse previous calculation results based on input file hashes to avoid redundant computations
- **🔁 Retry Mechanism**: Automatically retry failed calculations with alternative calculators
- **🌐 Remote Execution**: Execute calculations on remote servers via SSH with automatic file transfer
- **📊 DataFrame I/O**: Input and output using pandas DataFrames with automatic type casting and variable extraction
- **🛑 Interrupt Handling**: Gracefully stop long-running calculations with Ctrl+C while preserving partial results
- **🔍 Formula Evaluation**: Support for calculated parameters using Python or R expressions
- **📁 Directory Management**: Automatic organization of inputs, outputs, and logs for each case
- **🎯 Adaptive Algorithms**: Iterative design of experiments with intelligent sampling strategies (fzd)

### Five Core Functions

1. **`fzi`** - Parse **I**nput files to identify variables
2. **`fzc`** - **C**ompile input files by substituting variable values
3. **`fzo`** - Parse **O**utput files from calculations
4. **`fzr`** - **R**un complete parametric calculations end-to-end
5. **`fzd`** - Run iterative **D**esign of experiments with adaptive algorithms

## Installation

### Using pip

```bash
pip install funz-fz
```

### Using pipx (recommended for CLI tools)

```bash
pipx install funz-fz
```

[pipx](https://pypa.github.io/pipx/) installs the package in an isolated environment while making the CLI commands (`fz`, `fzi`, `fzc`, `fzo`, `fzr`) available globally.

### From Source

```bash
git clone https://github.com/Funz/fz.git
cd fz
pip install -e .
```

Or straight from GitHub via pip:

```bash
pip install -e git+https://github.com/Funz/fz.git
```

### Dependencies

```bash
# Optional dependencies:

# for SSH support
pip install paramiko

# for DataFrame support (recommended)
pip install pandas

# for fzd (design of experiments) - REQUIRED
pip install pandas

# for R interpreter support
pip install funz-fz[r]
# OR
pip install rpy2
# Note: Requires R installed with system libraries - see examples/r_interpreter_example.md

# for optimization algorithms (scipy-based algorithms in examples/)
pip install scipy numpy
```

## Quick Start

Here's a complete example for a simple parametric study:

### 1. Create an Input Template

Create `input.txt`:
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@{L_to_m3($V_L)}
```

Or using R for formulas (assuming R interpreter is set up: `fz.set_interpreter("R")`):
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ L_to_m3 <- function(L) {
#@     return (L / 1000)
#@ }
V_m3=@{L_to_m3($V_L)}
```

### 2. Create a Calculation Script

Create `PerfectGazPressure.sh`:
```bash
#!/bin/bash

# read input file
source $1

sleep 5 # simulate a calculation time

echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt

echo 'Done'
```

Make it executable:
```bash
chmod +x PerfectGazPressure.sh
```

### 3. Run Parametric Study

Create `run_study.py`:
```python
import fz

# Define the model
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

# Define parameter values
input_variables = {
    "T_celsius": [10, 20, 30, 40],  # 4 temperatures
    "V_L": [1, 2, 5],                # 3 volumes
    "n_mol": 1.0                     # fixed amount
}

# Run all combinations (4 × 3 = 12 cases)
results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="results"
)

# Display results
print(results)
print(f"\nCompleted {len(results)} calculations")
```

Run it:
```bash
python run_study.py
```

Expected output:
```
   T_celsius  V_L  n_mol     pressure status calculator       error command
0         10  1.0    1.0  235358.1200   done     sh://        None    bash...
1         10  2.0    1.0  117679.0600   done     sh://        None    bash...
2         10  5.0    1.0   47071.6240   done     sh://        None    bash...
3         20  1.0    1.0  243730.2200   done     sh://        None    bash...
...

Completed 12 calculations
```

## CLI Usage

FZ provides command-line tools for quick operations without writing Python scripts. All four core functions are available as CLI commands.

### Installation of CLI Tools

The CLI commands are automatically installed when you install the fz package:

```bash
pip install -e .
```

Available commands:
- `fz`  - Main entry point (general configuration, plugins management, logging, ...)
- `fzi` - Parse input variables
- `fzc` - Compile input files
- `fzo` - Read output files
- `fzr` - Run parametric calculations
- `fzd` - Run design of experiments with adaptive algorithms

### fzi - Parse Input Variables

Identify variables in input files:

```bash
# Parse a single file
fzi input.txt --model perfectgas

# Parse a directory
fzi input_dir/ --model mymodel

# Output formats
fzi input.txt --model perfectgas --format json
fzi input.txt --model perfectgas --format table
fzi input.txt --model perfectgas --format csv
```

**Example:**

```bash
$ fzi input.txt --model perfectgas --format table
┌──────────────┬───────┐
│ Variable     │ Value │
├──────────────┼───────┤
│ T_celsius    │ None  │
│ V_L          │ None  │
│ n_mol        │ None  │
└──────────────┴───────┘
```

**With inline model definition:**

```bash
fzi input.txt \
  --varprefix '$' \
  --delim '{}' \
  --format json
```

**Output (JSON):**
```json
{
  "T_celsius": null,
  "V_L": null,
  "n_mol": null
}
```

### fzc - Compile Input Files

Substitute variables and create compiled input files:

```bash
# Basic usage
fzc input.txt \
  --model perfectgas \
  --variables '{"T_celsius": 25, "V_L": 10, "n_mol": 1}' \
  --output compiled/

# Grid of values (creates subdirectories)
fzc input.txt \
  --model perfectgas \
  --variables '{"T_celsius": [10, 20, 30], "V_L": [1, 2], "n_mol": 1}' \
  --output compiled_grid/
```

**Directory structure created:**
```
compiled_grid/
├── T_celsius=10,V_L=1/
│   └── input.txt
├── T_celsius=10,V_L=2/
│   └── input.txt
├── T_celsius=20,V_L=1/
│   └── input.txt
...
```

**Using formula evaluation:**

```bash
# Input file with formulas
cat > input.txt << 'EOF'
Temperature: $T_celsius C
#@ T_kelvin = $T_celsius + 273.15
Calculated T: @{T_kelvin} K
EOF

# Compile with formula evaluation
fzc input.txt \
  --varprefix '$' \
  --formulaprefix '@' \
  --delim '{}' \
  --commentline '#' \
  --variables '{"T_celsius": 25}' \
  --output compiled/
```

### fzo - Read Output Files

Parse calculation results:

```bash
# Read single directory
fzo results/case1/ --model perfectgas --format table

# Read directory with subdirectories
fzo results/ --model perfectgas --format json

# Different output formats
fzo results/ --model perfectgas --format csv > results.csv
fzo results/ --model perfectgas --format html > results.html
fzo results/ --model perfectgas --format markdown
```

**Example output:**

```bash
$ fzo results/ --model perfectgas --format table
┌─────────────────────────┬──────────┬────────────┬──────┬───────┐
│ path                    │ pressure │ T_celsius  │ V_L  │ n_mol │
├─────────────────────────┼──────────┼────────────┼──────┼───────┤
│ T_celsius=10,V_L=1      │ 235358.1 │ 10         │ 1.0  │ 1.0   │
│ T_celsius=10,V_L=2      │ 117679.1 │ 10         │ 2.0  │ 1.0   │
│ T_celsius=20,V_L=1      │ 243730.2 │ 20         │ 1.0  │ 1.0   │
└─────────────────────────┴──────────┴────────────┴──────┴───────┘
```

**With inline model definition:**

```bash
fzo results/ \
  --output-cmd pressure="grep 'pressure = ' output.txt | awk '{print \$3}'" \
  --output-cmd temperature="cat temp.txt" \
  --format json
```

### fzr - Run Parametric Calculations

Execute complete parametric studies from the command line:

```bash
# Basic usage
fzr input.txt \
  --model perfectgas \
  --variables '{"T_celsius": [10, 20, 30], "V_L": [1, 2], "n_mol": 1}' \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --results results/

# Multiple calculators for parallel execution
fzr input.txt \
  --model perfectgas \
  --variables '{"param": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}' \
  --calculator "sh://bash calc.sh" \
  --calculator "sh://bash calc.sh" \
  --calculator "sh://bash calc.sh" \
  --results results/ \
  --format table
```

**Using cache:**

```bash
# First run
fzr input.txt \
  --model perfectgas \
  --variables '{"T_celsius": [10, 20, 30], "V_L": [1, 2]}' \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --results run1/

# Resume with cache (only runs missing cases)
fzr input.txt \
  --model perfectgas \
  --variables '{"T_celsius": [10, 20, 30, 40], "V_L": [1, 2, 3]}' \
  --calculator "cache://run1" \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --results run2/ \
  --format table
```

**Remote SSH execution:**

```bash
fzr input.txt \
  --model mymodel \
  --variables '{"mesh_size": [100, 200, 400]}' \
  --calculator "ssh://user@cluster.edu/bash /path/to/submit.sh" \
  --results hpc_results/ \
  --format json
```

**Output formats:**

```bash
# Table (default)
fzr input.txt --model perfectgas --variables '{"x": [1, 2, 3]}' --calculator "sh://calc.sh"

# JSON
fzr ... --format json

# CSV
fzr ... --format csv > results.csv

# Markdown
fzr ... --format markdown

# HTML
fzr ... --format html > results.html
```

### CLI Options Reference

#### Common Options (all commands)

```
--help, -h                Show help message
--version                 Show version
--model MODEL             Model alias or inline definition
--varprefix PREFIX        Variable prefix (default: $)
--delim DELIMITERS        Formula delimiters (default: {})
--formulaprefix PREFIX    Formula prefix (default: @)
--commentline CHAR        Comment character (default: #)
--format FORMAT           Output format: json, table, csv, markdown, html
```

#### Model Definition Options

Instead of using `--model alias`, you can define the model inline:

```bash
fzr input.txt \
  --varprefix '$' \
  --formulaprefix '@' \
  --delim '{}' \
  --commentline '#' \
  --output-cmd pressure="grep 'pressure' output.txt | awk '{print \$2}'" \
  --output-cmd temp="cat temperature.txt" \
  --variables '{"x": 10}' \
  --calculator "sh://bash calc.sh"
```

#### fzr-Specific Options

```
--calculator URI          Calculator URI (can be specified multiple times)
--results DIR             Results directory (default: results)
```

### Complete CLI Examples

#### Example 1: Quick Variable Discovery

```bash
# Check what variables are in your input files
$ fzi simulation_template.txt --varprefix '$' --format table
┌──────────────┬───────┐
│ Variable     │ Value │
├──────────────┼───────┤
│ mesh_size    │ None  │
│ timestep     │ None  │
│ iterations   │ None  │
└──────────────┴───────┘
```

#### Example 2: Quick Compilation Test

```bash
# Test variable substitution
$ fzc simulation_template.txt \
  --varprefix '$' \
  --variables '{"mesh_size": 100, "timestep": 0.01, "iterations": 1000}' \
  --output test_compiled/

$ cat test_compiled/simulation_template.txt
# Compiled with mesh_size=100
mesh_size=100
timestep=0.01
iterations=1000
```

#### Example 3: Parse Existing Results

```bash
# Extract results from previous calculations
$ fzo old_results/ \
  --output-cmd energy="grep 'Total Energy' log.txt | awk '{print \$3}'" \
  --output-cmd time="grep 'CPU Time' log.txt | awk '{print \$3}'" \
  --format csv > analysis.csv
```

#### Example 4: End-to-End Parametric Study

```bash
#!/bin/bash
# run_study.sh - Complete parametric study from CLI

# 1. Parse input to verify variables
echo "Step 1: Parsing input variables..."
fzi input.txt --model perfectgas --format table

# 2. Run parametric study
echo -e "\nStep 2: Running calculations..."
fzr input.txt \
  --model perfectgas \
  --variables '{
    "T_celsius": [10, 20, 30, 40, 50],
    "V_L": [1, 2, 5, 10],
    "n_mol": 1
  }' \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --results results/ \
  --format table

# 3. Export results to CSV
echo -e "\nStep 3: Exporting results..."
fzo results/ --model perfectgas --format csv > results.csv
echo "Results saved to results.csv"
```

#### Example 5: Using Model and Calculator Aliases

First, create model and calculator configurations:

```bash
# Create model alias
mkdir -p .fz/models
cat > .fz/models/perfectgas.json << 'EOF'
{
  "varprefix": "$",
  "formulaprefix": "@",
  "delim": "{}",
  "commentline": "#",
  "output": {
    "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
  },
  "id": "perfectgas"
}
EOF

# Create calculator alias
mkdir -p .fz/calculators
cat > .fz/calculators/local.json << 'EOF'
{
  "uri": "sh://",
  "models": {
    "perfectgas": "bash PerfectGazPressure.sh"
  }
}
EOF

# Now run with short aliases
fzr input.txt \
  --model perfectgas \
  --variables '{"T_celsius": [10, 20, 30], "V_L": [1, 2]}' \
  --calculator local \
  --results results/ \
  --format table
```

#### Example 6: Interrupt and Resume

```bash
# Start long-running calculation
fzr input.txt \
  --model mymodel \
  --variables '{"param": [1..100]}' \
  --calculator "sh://bash slow_calc.sh" \
  --results run1/
# Press Ctrl+C after some cases complete...
# ⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
# ⚠️  Execution was interrupted. Partial results may be available.

# Resume from cache
fzr input.txt \
  --model mymodel \
  --variables '{"param": [1..100]}' \
  --calculator "cache://run1" \
  --calculator "sh://bash slow_calc.sh" \
  --results run1_resumed/ \
  --format table
# Only runs the remaining cases
```

### fzd - Run Design of Experiments

Run iterative design of experiments with adaptive algorithms:

```bash
# Basic usage with Monte Carlo algorithm
fzd input.txt \
  --model perfectgas \
  --variables '{"T_celsius": "[10;50]", "V_L": "[1;10]", "n_mol": 1}' \
  --calculator "sh://bash PerfectGazPressure.sh" \
  --output-expression "pressure" \
  --algorithm examples/algorithms/montecarlo_uniform.py \
  --algorithm-options '{"batch_sample_size": 20, "max_iterations": 10}' \
  --analysis-dir fzd_results/

# With optimization algorithm (BFGS)
fzd input.txt \
  --model perfectgas \
  --variables '{"T_celsius": "[10;50]", "V_L": "[1;10]", "n_mol": 1}' \
  --calculator "sh://bash calc.sh" \
  --output-expression "pressure" \
  --algorithm examples/algorithms/bfgs.py \
  --algorithm-options '{"minimize": true, "max_iterations": 50}' \
  --analysis-dir optimization_results/

# Fixed and variable inputs
fzd input.txt \
  --model perfectgas \
  --variables '{"T_celsius": "[10;50]", "V_L": "5.0", "n_mol": 1}' \
  --calculator "sh://bash calc.sh" \
  --output-expression "pressure" \
  --algorithm examples/algorithms/brent.py \
  --analysis-dir brent_results/
```

**Key Differences from fzr**:
- Variables use `"[min;max]"` for ranges (algorithm decides values) or `"value"` for fixed
- Requires `--algorithm` parameter with path to algorithm file
- Optionally accepts `--algorithm-options` as JSON dict
- Returns DataFrame with all sampled points and analysis results

### Environment Variables for CLI

```bash
# Set logging level
export FZ_LOG_LEVEL=DEBUG
fzr input.txt --model perfectgas ...

# Set maximum parallel workers
export FZ_MAX_WORKERS=4
fzr input.txt --model perfectgas --calculator "sh://calc.sh" ...

# Set retry attempts
export FZ_MAX_RETRIES=3
fzr input.txt --model perfectgas ...

# SSH configuration
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1  # Use with caution
export FZ_SSH_KEEPALIVE=300
fzr input.txt --calculator "ssh://user@host/bash calc.sh" ...

# Shell path for binary resolution (Windows)
export FZ_SHELL_PATH="C:\msys64\usr\bin;C:\msys64\mingw64\bin"
fzr input.txt --model perfectgas ...
```

## Core Functions

### fzi - Parse Input Variables

Identify all variables in an input file or directory:

```python
import fz

model = {
    "varprefix": "$",
    "delim": "{}"
}

# Parse single file
variables = fz.fzi("input.txt", model)
# Returns: {'T_celsius': None, 'V_L': None, 'n_mol': None}

# Parse directory (scans all files)
variables = fz.fzi("input_dir/", model)
```

**Returns**: Dictionary with variable names as keys (values are None)

### fzc - Compile Input Files

Substitute variable values and evaluate formulas:

```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}

input_variables = {
    "T_celsius": 25,
    "V_L": 10,
    "n_mol": 2
}

# Compile single file
fz.fzc(
    "input.txt",
    input_variables,
    model,
    output_dir="compiled"
)

# Compile with multiple value sets (creates subdirectories)
fz.fzc(
    "input.txt",
    {
        "T_celsius": [20, 30],  # 2 values
        "V_L": [5, 10],         # 2 values
        "n_mol": 1              # fixed
    },
    model,
    output_dir="compiled_grid"
)
# Creates: compiled_grid/T_celsius=20,V_L=5/, T_celsius=20,V_L=10/, etc.
```

**Parameters**:
- `input_path`: Path to input file or directory
- `input_variables`: Dictionary of variable values (scalar or list)
- `model`: Model definition (dict or alias name)
- `output_dir`: Output directory path

### fzo - Read Output Files

Parse calculation results from output directory:

```python
import fz

model = {
    "output": {
        "pressure": "grep 'Pressure:' output.txt | awk '{print $2}'",
        "temperature": "grep 'Temperature:' output.txt | awk '{print $2}'"
    }
}

# Read from single directory
output = fz.fzo("results/case1", model)
# Returns: DataFrame with 1 row

# Read from directory with subdirectories
output = fz.fzo("results/*", model)
# Returns: DataFrame with 1 row per subdirectory
```

**Automatic Path Parsing**: If subdirectory names follow the pattern `key1=val1,key2=val2,...`, variables are automatically extracted as columns:

```python
# Directory structure:
# results/
#   ├── T_celsius=20,V_L=1/output.txt
#   ├── T_celsius=20,V_L=2/output.txt
#   └── T_celsius=30,V_L=1/output.txt

output = fz.fzo("results/*", model)
print(output)
#                          path  pressure  T_celsius  V_L
# 0  T_celsius=20,V_L=1  2437.30       20.0  1.0
# 1  T_celsius=20,V_L=2  1218.65       20.0  2.0
# 2  T_celsius=30,V_L=1  2520.74       30.0  1.0
```

### fzr - Run Parametric Calculations

Execute complete parametric study with automatic parallelization:

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "result": "cat output.txt"
    }
}

results = fz.fzr(
    input_path="input.txt",
    input_variables={
        "temperature": [100, 200, 300],
        "pressure": [1, 10, 100],
        "concentration": 0.5
    },
    model=model,
    calculators=["sh://bash calculate.sh"],
    results_dir="results"
)

# Results DataFrame includes:
# - All variable columns
# - All output columns
# - Metadata: status, calculator, error, command
print(results)
```

**Parameters**:
- `input_path`: Input file or directory path
- `input_variables`: Variable values - dict (factorial) or DataFrame (non-factorial)
- `model`: Model definition (dict or alias)
- `calculators`: Calculator URI(s) - string or list
- `results_dir`: Results directory path

**Returns**: pandas DataFrame with all results

### fzd - Run Design of Experiments

Execute iterative design of experiments with adaptive algorithms:

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "result": "grep 'Result:' output.txt | awk '{print $2}'"
    }
}

# Run Monte Carlo sampling
results = fz.fzd(
    input_file="input.txt",
    input_variables={
        "x": "[0;10]",      # Range: algorithm decides values
        "y": "[-5;5]",      # Range: algorithm decides values
        "z": "2.5"          # Fixed value
    },
    model=model,
    output_expression="result",
    algorithm="examples/algorithms/montecarlo_uniform.py",
    calculators=["sh://bash calculate.sh"],
    algorithm_options={"batch_sample_size": 10, "max_iterations": 20},
    analysis_dir="results_fzd"
)

# Results include:
# - results['XY']: DataFrame with all input/output values
# - results['analysis']: Processed analysis (HTML, plots, metrics, etc.)
# - results['iterations']: Number of iterations completed
# - results['total_evaluations']: Total function evaluations
# - results['summary']: Summary text
print(results['XY'])  # All sampled points and outputs
print(results['summary'])  # Algorithm completion summary
```

**Algorithm Examples**:
- `examples/algorithms/montecarlo_uniform.py` - Uniform random sampling
- `examples/algorithms/randomsampling.py` - Simple random sampling
- `examples/algorithms/bfgs.py` - BFGS optimization (requires scipy)
- `examples/algorithms/brent.py` - Brent's 1D optimization (requires scipy)

**Parameters**:
- `input_file`: Input file or directory path
- `input_variables`: Dict with `"[min;max]"` for ranges or `"value"` for fixed
- `model`: Model definition (dict or alias)
- `output_expression`: Expression to evaluate from outputs (e.g., `"pressure"` or `"out1 + out2 * 2"`)
- `algorithm`: Path to algorithm Python file
- `calculators`: Calculator URI(s) - string or list
- `algorithm_options`: Dict of algorithm-specific options
- `analysis_dir`: Analysis results directory

**Returns**: Dict with:
- `XY`: pandas DataFrame with all input and output values
- `analysis`: Processed analysis results (HTML files, plots, metrics)
- `algorithm`: Algorithm path
- `iterations`: Number of iterations completed
- `total_evaluations`: Total number of function evaluations
- `summary`: Human-readable summary text

### Input Variables: Factorial vs Non-Factorial Designs

FZ supports two types of parametric study designs through different `input_variables` formats:

#### Factorial Design (Dict)

Use a **dict** to create a full factorial design (Cartesian product of all variable values):

```python
# Dict with lists creates ALL combinations (factorial)
input_variables = {
    "temp": [100, 200, 300],      # 3 values
    "pressure": [1.0, 2.0]         # 2 values
}
# Creates 6 cases: 3 × 2 = 6
# (100,1.0), (100,2.0), (200,1.0), (200,2.0), (300,1.0), (300,2.0)

results = fz.fzr(input_file, input_variables, model, calculators)
```

**Use factorial design when:**
- You want to explore all possible combinations
- Variables are independent
- You need a complete design space exploration

#### Non-Factorial Design (DataFrame)

Use a **pandas DataFrame** to specify exactly which cases to run (non-factorial):

```python
import pandas as pd

# DataFrame: each row is ONE case (non-factorial)
input_variables = pd.DataFrame({
    "temp":     [100, 200, 100, 300],
    "pressure": [1.0, 1.0, 2.0, 1.5]
})
# Creates 4 cases ONLY:
# (100,1.0), (200,1.0), (100,2.0), (300,1.5)
# Note: (100,2.0) is included but (200,2.0) is not

results = fz.fzr(input_file, input_variables, model, calculators)
```

**Use non-factorial design when:**
- You have specific combinations to test
- Variables are coupled or have constraints
- You want to import a design from another tool
- You need an irregular or optimized sampling pattern

**Examples of non-factorial patterns:**
```python
# Latin Hypercube Sampling
import pandas as pd
from scipy.stats import qmc

sampler = qmc.LatinHypercube(d=2)
sample = sampler.random(n=10)
input_variables = pd.DataFrame({
    "x": sample[:, 0] * 100,  # Scale to [0, 100]
    "y": sample[:, 1] * 10    # Scale to [0, 10]
})

# Constraint-based design (only valid combinations)
input_variables = pd.DataFrame({
    "rpm": [1000, 1500, 2000, 2500],
    "load": [10, 20, 40, 50]  # load increases with rpm
})

# Imported from design of experiments tool
input_variables = pd.read_csv("doe_design.csv")
```

## Model Definition

A model defines how to parse inputs and extract outputs:

```python
model = {
    # Input parsing
    "varprefix": "$",           # Variable marker (e.g., $temp)
    "formulaprefix": "@",       # Formula marker (e.g., @pressure)
    "delim": "{}",              # Formula delimiters
    "commentline": "#",         # Comment character

    # Optional: formula interpreter
    "interpreter": "python",    # "python" (default) or "R"

    # Output extraction (shell commands)
    "output": {
        "pressure": "grep 'P =' out.txt | awk '{print $3}'",
        "temperature": "cat temp.txt",
        "energy": "python extract.py"
    },

    # Optional: model identifier
    "id": "perfectgas"
}
```

### Model Aliases

Store reusable models in `.fz/models/`:

**`.fz/models/perfectgas.json`**:
```json
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    },
    "id": "perfectgas"
}
```

Use by name:
```python
results = fz.fzr("input.txt", input_variables, "perfectgas")
```

### Formula Evaluation

Formulas in input files are evaluated during compilation using Python or R interpreters.

#### Python Interpreter (Default)

```text
# Input template with formulas
Temperature: $T_celsius C
Volume: $V_L L

# Context (available in all formulas)
#@import math
#@R = 8.314
#@def celsius_to_kelvin(t):
#@    return t + 273.15

# Calculated value
#@T_kelvin = celsius_to_kelvin($T_celsius)
#@pressure = $n_mol * R * T_kelvin / ($V_L / 1000)

Result: @{pressure} Pa
Circumference: @{2 * math.pi * $radius}
```

#### R Interpreter

For statistical computing, you can use R for formula evaluation:

```python
from fz import fzi
from fz.config import set_interpreter

# Set interpreter to R
set_interpreter("R")

# Or specify in model
model = {"interpreter": "R", "formulaprefix": "@", "delim": "{}", "commentline": "#"}
```

**R template example**:
```text
# Input template with R formulas
Sample size: $n
Mean: $mu
SD: $sigma

# R context (available in all formulas)
#@samples <- rnorm($n, mean=$mu, sd=$sigma)

Mean (sample): @{mean(samples)}
SD (sample): @{sd(samples)}
Median: @{median(samples)}
```

**Installation requirements**: R must be installed along with system libraries. See `examples/r_interpreter_example.md` for detailed installation instructions.

```bash
# Install with R support
pip install funz-fz[r]
```

**Key differences**:
- Python requires `import math` for `math.pi`, R has `pi` built-in
- R excels at statistical functions: `mean()`, `sd()`, `median()`, `rnorm()`, etc.
- R uses `<-` for assignment in context lines
- R is vectorized by default

#### Variable Default Values

Variables can specify default values using the `${var~default}` syntax:

```text
# Configuration template
Host: ${host~localhost}
Port: ${port~8080}
Debug: ${debug~false}
Workers: ${workers~4}
```

**Behavior**:
- If variable is provided in `input_variables`, its value is used
- If variable is NOT provided but has default, default is used (with warning)
- If variable is NOT provided and has NO default, it remains unchanged

**Example**:
```python
from fz.interpreter import replace_variables_in_content

content = "Server: ${host~localhost}:${port~8080}"
input_variables = {"host": "example.com"}  # port not provided

result = replace_variables_in_content(content, input_variables)
# Result: "Server: example.com:8080"
# Warning: Variable 'port' not found in input_variables, using default value: '8080'
```

**Use cases**:
- Configuration templates with sensible defaults
- Environment-specific deployments
- Optional parameters in parametric studies

See `examples/variable_substitution.md` for comprehensive documentation.

**Features**:
- Python or R expression evaluation
- Multi-line function definitions
- Variable substitution in formulas
- Default values for variables
- Nested formula evaluation

## Calculator Types

### Local Shell Execution

Execute calculations locally:

```python
# Basic shell command
calculators = "sh://bash script.sh"

# With multiple arguments
calculators = "sh://python calculate.py --verbose"

# Multiple calculators (tries in order, parallel execution)
calculators = [
    "sh://bash method1.sh",
    "sh://bash method2.sh",
    "sh://python method3.py"
]
```

**How it works**:
1. Input files copied to temporary directory
2. Command executed in that directory with input files as arguments
3. Outputs parsed from result directory
4. Temporary files cleaned up (preserved in DEBUG mode)

### SSH Remote Execution

Execute calculations on remote servers:

```python
# SSH with password
calculators = "ssh://user:password@server.com:22/bash /absolutepath/to/calc.sh"

# SSH with key-based auth (recommended)
calculators = "ssh://user@server.com/bash /absolutepath/to/calc.sh"

# SSH with custom port
calculators = "ssh://user@server.com:2222/bash /absolutepath/to/calc.sh"
```

**Features**:
- Automatic file transfer (SFTP)
- Remote execution with timeout
- Result retrieval
- SSH key-based or password authentication
- Host key verification

**Security**:
- Interactive host key acceptance
- Warning for password-based auth
- Environment variable for auto-accepting host keys: `FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1`

### Cache Calculator

Reuse previous calculation results:

```python
# Check single cache directory
calculators = "cache://previous_results"

# Check multiple cache locations
calculators = [
    "cache://run1",
    "cache://run2/results",
    "sh://bash calculate.sh"  # Fallback to actual calculation
]

# Use glob patterns
calculators = "cache://archive/*/results"
```

**Cache Matching**:
- Based on MD5 hash of input files (`.fz_hash`)
- Validates outputs are not None
- Falls through to next calculator on miss
- No recalculation if cache hit

### Calculator Aliases

Store calculator configurations in `.fz/calculators/`:

**`.fz/calculators/cluster.json`**:
```json
{
    "uri": "ssh://user@cluster.university.edu",
    "models": {
        "perfectgas": "bash /home/user/codes/perfectgas/run.sh",
        "navier-stokes": "bash /home/user/codes/cfd/run.sh"
    }
}
```

Use by name:
```python
results = fz.fzr("input.txt", input_variables, "perfectgas", calculators="cluster")
```

## Advanced Features

### Parallel Execution

FZ automatically parallelizes when you have multiple cases and calculators:

```python
# Sequential: 1 calculator, 10 cases → runs one at a time
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators="sh://bash calc.sh"
)

# Parallel: 3 calculators, 10 cases → 3 concurrent
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ]
)

# Control parallelism with environment variable
import os
os.environ['FZ_MAX_WORKERS'] = '4'

# Or use duplicate calculator URIs
calculators = ["sh://bash calc.sh"] * 4  # 4 parallel workers
```

**Load Balancing**:
- Round-robin distribution of cases to calculators
- Thread-safe calculator locking
- Automatic retry on failures
- Progress tracking with ETA

### Retry Mechanism

Automatic retry on calculation failures:

```python
import os
os.environ['FZ_MAX_RETRIES'] = '3'  # Try each case up to 3 times

results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators=[
        "sh://unreliable_calc.sh",  # Might fail
        "sh://backup_calc.sh"        # Backup method
    ]
)
```

**Retry Strategy**:
1. Try first available calculator
2. On failure, try next calculator
3. Repeat up to `FZ_MAX_RETRIES` times
4. Report all attempts in logs

### Caching Strategy

Intelligent result reuse:

```python
# First run
results1 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30]},
    model,
    calculators="sh://expensive_calc.sh",
    results_dir="run1"
)

# Add more cases - reuse previous results
results2 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30, 40, 50]},  # 2 new cases
    model,
    calculators=[
        "cache://run1",              # Check cache first
        "sh://expensive_calc.sh"     # Only run new cases
    ],
    results_dir="run2"
)
# Only runs calculations for temp=40 and temp=50
```

### Output Type Casting

Automatic type conversion:

```python
model = {
    "output": {
        "scalar_int": "echo 42",
        "scalar_float": "echo 3.14159",
        "array": "echo '[1, 2, 3, 4, 5]'",
        "single_array": "echo '[42]'",  # → 42 (simplified)
        "json_object": "echo '{\"key\": \"value\"}'",
        "string": "echo 'hello world'"
    }
}

results = fz.fzo("output_dir", model)
# Values automatically cast to int, float, list, dict, or str
```

**Casting Rules**:
1. Try JSON parsing
2. Try Python literal evaluation
3. Try numeric conversion (int/float)
4. Keep as string
5. Single-element arrays → scalar

## Complete Examples

### Example 1: Perfect Gas Pressure Study

**Input file (`input.txt`)**:
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@{L_to_m3($V_L)}
```

**Calculation script (`PerfectGazPressure.sh`)**:
```bash
#!/bin/bash

# read input file
source $1

sleep 5 # simulate a calculation time

echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt

echo 'Done'
```

**Python script (`run_perfectgas.py`)**:
```python
import fz
import matplotlib.pyplot as plt

# Define model
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

# Parametric study
results = fz.fzr(
    "input.txt",
    {
        "n_mol": [1, 2, 3],
        "T_celsius": [10, 20, 30],
        "V_L": [5, 10]
    },
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="perfectgas_results"
)

print(results)

# Plot results: pressure vs temperature for different volumes
for volume in results['V_L'].unique():
    for n in results['n_mol'].unique():
        data = results[(results['V_L'] == volume) & (results['n_mol'] == n)]
        plt.plot(data['T_celsius'], data['pressure'],
                 marker='o', label=f'n={n} mol, V={volume} L')

plt.xlabel('Temperature (°C)')
plt.ylabel('Pressure (Pa)')
plt.title('Ideal Gas: Pressure vs Temperature')
plt.legend()
plt.grid(True)
plt.savefig('perfectgas_results.png')
print("Plot saved to perfectgas_results.png")
```

### Example 2: Remote HPC Calculation

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "energy": "grep 'Total Energy' output.log | awk '{print $4}'",
        "time": "grep 'CPU time' output.log | awk '{print $4}'"
    }
}

# Run on HPC cluster
results = fz.fzr(
    "simulation_input/",
    {
        "mesh_size": [100, 200, 400, 800],
        "timestep": [0.001, 0.01, 0.1],
        "iterations": 1000
    },
    model,
    calculators=[
        "cache://previous_runs/*",  # Check cache first
        "ssh://user@hpc.university.edu/sbatch /path/to/submit.sh"
    ],
    results_dir="hpc_results"
)

# Analyze convergence
import pandas as pd
summary = results.groupby('mesh_size').agg({
    'energy': ['mean', 'std'],
    'time': 'sum'
})
print(summary)
```

### Example 3: Multi-Calculator with Failover

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat result.txt"}
}

results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://previous_results",           # 1. Check cache
        "sh://bash fast_but_unstable.sh",    # 2. Try fast method
        "sh://bash robust_method.sh",        # 3. Fallback to robust
        "ssh://user@server/bash remote.sh"   # 4. Last resort: remote
    ],
    results_dir="results"
)

# Check which calculator was used for each case
print(results[['param', 'calculator', 'status']].head(10))
```

### Example 4: Design of Experiments with Adaptive Sampling

```python
import fz
import matplotlib.pyplot as plt

# Input template with perfect gas law
# (same as Example 1, but using fzd for adaptive design)

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

# Run Monte Carlo sampling to explore pressure distribution
results = fz.fzd(
    input_file="input.txt",
    input_variables={
        "T_celsius": "[10;50]",  # Range: 10 to 50°C
        "V_L": "[1;10]",         # Range: 1 to 10 L
        "n_mol": "1.0"           # Fixed: 1 mole
    },
    model=model,
    output_expression="pressure",
    algorithm="examples/algorithms/montecarlo_uniform.py",
    calculators=["sh://bash PerfectGazPressure.sh"],
    algorithm_options={
        "batch_sample_size": 20,  # 20 samples per iteration
        "max_iterations": 10       # 10 iterations
    },
    analysis_dir="monte_carlo_results"
)

# Results DataFrame has all sampled points
print(f"Total evaluations: {results['total_evaluations']}")
print(f"Iterations: {results['iterations']}")
print(results['summary'])

# Access the data
df = results['XY']
print(df.head())

# Plot the sampled points
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Scatter plot: Temperature vs Volume colored by Pressure
scatter = ax1.scatter(df['T_celsius'], df['V_L'], c=df['pressure'],
                      cmap='viridis', s=50, alpha=0.6)
ax1.set_xlabel('Temperature (°C)')
ax1.set_ylabel('Volume (L)')
ax1.set_title('Sampled Design Space')
plt.colorbar(scatter, ax=ax1, label='Pressure (Pa)')

# Histogram of pressure values
ax2.hist(df['pressure'], bins=20, edgecolor='black')
ax2.set_xlabel('Pressure (Pa)')
ax2.set_ylabel('Frequency')
ax2.set_title('Pressure Distribution')

plt.tight_layout()
plt.savefig('monte_carlo_analysis.png')
print("Analysis plot saved to monte_carlo_analysis.png")
```

### Example 5: Optimization with BFGS

```python
import fz

# Find temperature and volume that minimize pressure

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

results = fz.fzd(
    input_file="input.txt",
    input_variables={
        "T_celsius": "[10;50]",  # Search range
        "V_L": "[1;10]",         # Search range
        "n_mol": "1.0"           # Fixed
    },
    model=model,
    output_expression="pressure",
    algorithm="examples/algorithms/bfgs.py",
    calculators=["sh://bash PerfectGazPressure.sh"],
    algorithm_options={
        "minimize": True,        # Minimize pressure
        "max_iterations": 50
    },
    analysis_dir="optimization_results"
)

# Get optimal point
df = results['XY']
optimal_idx = df['pressure'].idxmin()
optimal = df.loc[optimal_idx]

print(f"Optimal temperature: {optimal['T_celsius']:.2f}°C")
print(f"Optimal volume: {optimal['V_L']:.2f} L")
print(f"Minimum pressure: {optimal['pressure']:.2f} Pa")
print(f"Total evaluations: {results['total_evaluations']}")

# Plot optimization path
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
plt.scatter(df['T_celsius'], df['V_L'], c=df['pressure'],
            cmap='coolwarm', s=100, edgecolor='black')
plt.plot(df['T_celsius'], df['V_L'], 'k--', alpha=0.3, label='Optimization path')
plt.scatter(optimal['T_celsius'], optimal['V_L'],
            color='red', s=300, marker='*',
            edgecolor='black', label='Optimum')
plt.xlabel('Temperature (°C)')
plt.ylabel('Volume (L)')
plt.title('BFGS Optimization Path')
plt.colorbar(label='Pressure (Pa)')
plt.legend()
plt.savefig('optimization_path.png')
print("Optimization path saved to optimization_path.png")
```

## Writing Custom Algorithms for fzd

FZ provides an extensible framework for implementing adaptive algorithms. Each algorithm is a Python class with specific methods.

### Algorithm Interface

Create a Python file with a class implementing these methods:

```python
class MyAlgorithm:
    """Custom algorithm for design of experiments"""

    def __init__(self, **options):
        """
        Initialize algorithm with options passed from algorithm_options.

        Args:
            **options: Algorithm-specific parameters (e.g., batch_size, max_iter)
        """
        self.batch_size = options.get('batch_size', 10)
        self.max_iterations = options.get('max_iterations', 100)
        self.iteration = 0

    def get_initial_design(self, input_vars, output_vars):
        """
        Return initial design points to evaluate.

        Args:
            input_vars: Dict[str, tuple] - {var_name: (min, max)}
                       e.g., {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
            output_vars: List[str] - Output variable names

        Returns:
            List[Dict[str, float]] - Initial points to evaluate
                                    e.g., [{"x": 0.5, "y": 0.0}, {"x": 7.5, "y": 2.3}]
        """
        # Generate initial sample points
        import random
        points = []
        for _ in range(self.batch_size):
            point = {
                var: random.uniform(bounds[0], bounds[1])
                for var, bounds in input_vars.items()
            }
            points.append(point)
        return points

    def get_next_design(self, previous_input_vars, previous_output_values):
        """
        Return next design points based on previous results.

        Args:
            previous_input_vars: List[Dict[str, float]] - All previous input combinations
            previous_output_values: List[float] - Corresponding outputs (may contain None)

        Returns:
            List[Dict[str, float]] - Next points to evaluate
                                    Empty list [] signals algorithm is finished
        """
        self.iteration += 1

        # Stop if max iterations reached
        if self.iteration >= self.max_iterations:
            return []  # Empty list = finished

        # Generate next batch based on results
        # ... your adaptive logic here ...

        return next_points

    def get_analysis(self, input_vars, output_values):
        """
        Return final analysis results.

        Args:
            input_vars: List[Dict[str, float]] - All evaluated inputs
            output_values: List[float] - All outputs (may contain None)

        Returns:
            Dict with analysis information (can include 'text', 'data', etc.)
        """
        # Filter out failed evaluations (None values)
        valid_results = [(x, y) for x, y in zip(input_vars, output_values) if y is not None]

        return {
            'text': f"Algorithm completed: {len(valid_results)} successful evaluations",
            'data': {'mean': sum(y for _, y in valid_results) / len(valid_results)}
        }

    def get_analysis_tmp(self, input_vars, output_values):
        """
        [OPTIONAL] Return intermediate results at each iteration.

        Args:
            input_vars: List[Dict[str, float]] - All inputs so far
            output_values: List[float] - All outputs so far

        Returns:
            Dict with intermediate analysis information
        """
        valid_count = sum(1 for y in output_values if y is not None)
        return {
            'text': f"Iteration {self.iteration}: {valid_count} valid samples"
        }
```

### Algorithm Examples

#### 1. Monte Carlo Sampling

See `examples/algorithms/montecarlo_uniform.py`:

```python
import fz

results = fz.fzd(
    input_file="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="examples/algorithms/montecarlo_uniform.py",
    calculators=["sh://bash calc.sh"],
    algorithm_options={"batch_sample_size": 20, "max_iterations": 10}
)
```

#### 2. BFGS Optimization

See `examples/algorithms/bfgs.py` (requires scipy):

```python
results = fz.fzd(
    input_file="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="energy",
    algorithm="examples/algorithms/bfgs.py",
    calculators=["sh://bash calc.sh"],
    algorithm_options={"minimize": True, "max_iterations": 50}
)
```

#### 3. Brent's Method (1D Optimization)

See `examples/algorithms/brent.py` (requires scipy):

```python
results = fz.fzd(
    input_file="input.txt",
    input_variables={"temperature": "[0;100]"},  # Single variable
    model="mymodel",
    output_expression="efficiency",
    algorithm="examples/algorithms/brent.py",
    calculators=["sh://bash calc.sh"],
    algorithm_options={"minimize": False}  # Maximize efficiency
)
```

### Algorithm Features

#### Content Format Detection

Algorithms can return analysis results in multiple formats:

```python
def get_analysis(self, input_vars, output_values):
    # Return HTML
    return {
        'text': '<html><body><h1>Results</h1><p>Mean: 42.5</p></body></html>',
        'data': {'mean': 42.5}
    }
    # Saved to: analysis_<iteration>.html

    # Return JSON
    return {
        'text': '{"mean": 42.5, "std": 3.2}',
        'data': {}
    }
    # Saved to: analysis_<iteration>.json

    # Return Markdown
    return {
        'text': '# Results\n\n**Mean**: 42.5\n**Std**: 3.2',
        'data': {}
    }
    # Saved to: analysis_<iteration>.md

    # Return key-value format
    return {
        'text': 'mean=42.5\nstd=3.2\nsamples=100',
        'data': {}
    }
    # Saved to: analysis_<iteration>.txt
```

See `docs/FZD_CONTENT_FORMATS.md` for detailed format documentation.

#### Dependency Management

Specify required packages using `__require__`:

```python
__require__ = ["numpy", "scipy", "matplotlib"]

class MyAlgorithm:
    def __init__(self, **options):
        import numpy as np
        import scipy.optimize
        # ...
```

FZ will check dependencies at load time and warn if packages are missing.

## Configuration

### Environment Variables

```bash
# Logging level (DEBUG, INFO, WARNING, ERROR)
export FZ_LOG_LEVEL=INFO

# Maximum retry attempts per case
export FZ_MAX_RETRIES=5

# Thread pool size for parallel execution
export FZ_MAX_WORKERS=8

# SSH keepalive interval (seconds)
export FZ_SSH_KEEPALIVE=300

# Auto-accept SSH host keys (use with caution!)
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=0

# Default formula interpreter (python or R)
export FZ_INTERPRETER=python

# Custom shell binary search path (for Windows, overrides system PATH)
# Use semicolon separator on Windows, colon on Unix/Linux
export FZ_SHELL_PATH="C:\msys64\usr\bin;C:\msys64\mingw64\bin"  # Windows
export FZ_SHELL_PATH="/opt/custom/bin:/usr/local/bin"           # Unix/Linux
```

### Python Configuration

```python
from fz import get_config

# Get current config
config = get_config()
print(f"Max retries: {config.max_retries}")
print(f"Max workers: {config.max_workers}")

# Modify configuration
config.max_retries = 10
config.max_workers = 4
```

### Directory Structure

FZ uses the following directory structure:

```
your_project/
├── input.txt                 # Your input template
├── calculate.sh              # Your calculation script
├── run_study.py             # Your Python script
├── .fz/                     # FZ configuration (optional)
│   ├── models/              # Model aliases
│   │   └── mymodel.json
│   ├── calculators/         # Calculator aliases
│   │   └── mycluster.json
│   └── tmp/                 # Temporary files (auto-created)
│       └── fz_temp_*/       # Per-run temp directories
└── results/                 # Results directory
    ├── case1/               # One directory per case
    │   ├── input.txt        # Compiled input
    │   ├── output.txt       # Calculation output
    │   ├── log.txt          # Execution metadata
    │   ├── out.txt          # Standard output
    │   ├── err.txt          # Standard error
    │   └── .fz_hash         # File checksums (for caching)
    └── case2/
        └── ...
```

## Interrupt Handling

FZ supports graceful interrupt handling for long-running calculations:

### How to Interrupt

Press **Ctrl+C** during execution:

```bash
python run_study.py
# ... calculations running ...
# Press Ctrl+C
⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
⚠️  Press Ctrl+C again to force quit (not recommended)
```

### What Happens

1. **First Ctrl+C**:
   - Currently running calculations complete
   - No new calculations start
   - Partial results are saved
   - Resources are cleaned up
   - Signal handlers restored

2. **Second Ctrl+C** (not recommended):
   - Immediate termination
   - May leave resources in inconsistent state

### Resuming After Interrupt

Use caching to resume from where you left off:

```python
# First run (interrupted after 50/100 cases)
results1 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
print(f"Completed {len(results1)} cases before interrupt")

# Resume using cache
results2 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://results",      # Reuse completed cases
        "sh://bash calc.sh"     # Run remaining cases
    ],
    results_dir="results_resumed"
)
print(f"Total completed: {len(results2)} cases")
```

### Example with Interrupt Handling

```python
import fz
import signal
import sys

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

def main():
    try:
        results = fz.fzr(
            "input.txt",
            {"param": list(range(1000))},  # Many cases
            model,
            calculators="sh://bash slow_calculation.sh",
            results_dir="results"
        )

        print(f"\n✅ Completed {len(results)} calculations")
        return results

    except KeyboardInterrupt:
        # This should rarely happen (graceful shutdown handles it)
        print("\n❌ Forcefully terminated")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Output File Structure

Each case creates a directory with complete execution metadata:

### `log.txt` - Execution Metadata
```
Command: bash calculate.sh input.txt
Exit code: 0
Time start: 2024-03-15T10:30:45.123456
Time end: 2024-03-15T10:32:12.654321
Execution time: 87.531 seconds
User: john_doe
Hostname: compute-01
Operating system: Linux
Platform: Linux-5.15.0-x86_64
Working directory: /tmp/fz_temp_abc123/case1
Original directory: /home/john/project
```

### `.fz_hash` - Input File Checksums
```
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

Used for cache matching.

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_examples_perfectgaz.py -v

# Run with debug output
FZ_LOG_LEVEL=DEBUG python -m pytest tests/test_parallel.py -v

# Run tests matching pattern
python -m pytest tests/ -k "parallel" -v

# Test interrupt handling
python -m pytest tests/test_interrupt_handling.py -v

# Run examples
python example_usage.py
python example_interrupt.py  # Interactive interrupt demo
```

### Project Structure

```
fz/
├── fz/                          # Main package
│   ├── __init__.py              # Public API exports
│   ├── core.py                  # Core functions (fzi, fzc, fzo, fzr, fzd)
│   ├── interpreter.py           # Variable parsing, formula evaluation
│   ├── runners.py               # Calculation execution (sh, ssh, cache)
│   ├── helpers.py               # Parallel execution, retry logic
│   ├── io.py                    # File I/O, caching, hashing
│   ├── algorithms.py            # Algorithm framework for fzd
│   ├── shell.py                 # Shell utilities, binary path resolution
│   ├── logging.py               # Logging configuration
│   ├── cli.py                   # Command-line interface
│   └── config.py                # Configuration management
├── examples/                    # Example files
│   └── algorithms/              # Example algorithms for fzd
│       ├── montecarlo_uniform.py  # Monte Carlo sampling
│       ├── randomsampling.py      # Simple random sampling
│       ├── bfgs.py                # BFGS optimization
│       └── brent.py               # Brent's 1D optimization
├── tests/                       # Test suite
│   ├── test_parallel.py         # Parallel execution tests
│   ├── test_interrupt_handling.py  # Interrupt handling tests
│   ├── test_fzd.py              # Design of experiments tests
│   ├── test_examples_*.py       # Example-based tests
│   └── ...
├── docs/                        # Documentation
│   └── FZD_CONTENT_FORMATS.md  # fzd content format documentation
├── README.md                    # This file
└── setup.py                     # Package configuration
```

### Testing Your Own Models

Create a test following this pattern:

```python
import fz
import tempfile
from pathlib import Path

def test_my_model():
    # Create input
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("Parameter: $param\n")

        # Create calculator script
        calc_script = Path(tmpdir) / "calc.sh"
        calc_script.write_text("""#!/bin/bash
source $1
echo "result=$param" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "output": {
                "result": "grep 'result=' output.txt | cut -d= -f2"
            }
        }

        # Run test
        results = fz.fzr(
            str(input_file),
            {"param": [1, 2, 3]},
            model,
            calculators=f"sh://bash {calc_script}",
            results_dir=str(Path(tmpdir) / "results")
        )

        # Verify
        assert len(results) == 3
        assert list(results['result']) == [1, 2, 3]
        assert all(results['status'] == 'done')

        print("✅ Test passed!")

if __name__ == "__main__":
    test_my_model()
```

## Troubleshooting

### Common Issues

**Problem**: Calculations fail with "command not found"
```bash
# Solution: Use absolute paths in calculator URIs
calculators = "sh://bash /full/path/to/script.sh"
```

**Problem**: SSH calculations hang
```bash
# Solution: Increase timeout or check SSH connectivity
calculators = "ssh://user@host/bash script.sh"
# Test manually: ssh user@host "bash script.sh"
```

**Problem**: Cache not working
```bash
# Solution: Check .fz_hash files exist in cache directories
# Enable debug logging to see cache matching process
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'
```

**Problem**: Out of memory with many parallel cases
```bash
# Solution: Limit parallel workers
export FZ_MAX_WORKERS=2
```

### Debug Mode

Enable detailed logging:

```python
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

results = fz.fzr(...)  # Will show detailed execution logs
```

Debug output includes:
- Calculator selection and locking
- File operations
- Command execution
- Cache matching
- Thread pool management
- Temporary directory preservation

## Performance Tips

1. **Use caching**: Reuse previous results when possible
2. **Limit parallelism**: Don't exceed your CPU/memory limits
3. **Optimize calculators**: Fast calculators first in the list
4. **Batch similar cases**: Group cases that use the same calculator
5. **Use SSH keepalive**: For long-running remote calculations
6. **Clean old results**: Remove old result directories to save disk space

## License

BSD 3-Clause License. See `LICENSE` file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## Citation

If you use FZ in your research, please cite:

```bibtex
@software{fz,
  title = {FZ: Parametric Scientific Computing Framework},
  designers = {[Yann Richet]},
  authors = {[Claude Sonnet, Yann Richet]},
  year = {2025},
  url = {https://github.com/Funz/fz}
}
```

## Support

- **Issues**: https://github.com/Funz/fz/issues
- **Documentation**: https://fz.github.io
- **Examples**: See `tests/test_examples_*.py` for working examples
