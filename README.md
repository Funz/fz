# FZ - Parametric Scientific Computing Framework

[![CI](https://github.com/Funz/fz/workflows/CI/badge.svg)](https://github.com/Funz/fz/actions/workflows/ci.yml)
<!--
[![Python Version](https://img.shields.io/pypi/pyversions/funz.svg)](https://pypi.org/project/funz/)
-->
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Version](https://img.shields.io/badge/version-0.9.1-blue.svg)](https://github.com/Funz/fz/releases)

A powerful Python package for parametric simulations and computational experiments. FZ wraps your simulation codes to automatically run parametric studies, manage input/output files, handle parallel execution, and collect results in structured DataFrames.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
  - [Argument Formats](#argument-formats)
  - [fzi - Parse Input Variables](#fzi---parse-input-variables)
  - [fzc - Compile Input Files](#fzc---compile-input-files)
  - [fzo - Read Output Files](#fzo---read-output-files)
  - [fzl - List and Validate Models/Calculators](#fzl---list-and-validate-modelscalculators)
  - [fzr - Run Parametric Calculations](#fzr---run-parametric-calculations)
  - [fzd - Design of Experiments](#fzd---design-of-experiments)
  - [fz install / uninstall](#fz-install--uninstall)
- [Core Functions](#core-functions)
- [Model Definition](#model-definition)
  - [Variable Default Values](#variable-default-values)
  - [Old Funz Syntax Compatibility](#old-funz-syntax-compatibility)
  - [Formula Evaluation](#formula-evaluation)
- [Calculator Types](#calculator-types)
  - [Local Shell Execution](#local-shell-execution)
  - [SSH Remote Execution](#ssh-remote-execution)
  - [SLURM Workload Manager](#slurm-workload-manager)
  - [Funz Server Execution](#funz-server-execution)
  - [Cache Calculator](#cache-calculator)
  - [Calculator-Model Compatibility](#calculator-model-compatibility)
- [Advanced Features](#advanced-features)
  - [Parallel Execution](#parallel-execution)
  - [Retry Mechanism](#retry-mechanism)
  - [Caching Strategy](#caching-strategy)
  - [Output Type Casting](#output-type-casting)
  - [Progress Callbacks](#progress-callbacks)
- [Complete Examples](#complete-examples)
- [Writing Custom Algorithms for fzd](#writing-custom-algorithms-for-fzd)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Shell Path Configuration](#shell-path-configuration-fz_shell_path)
  - [Timeout Configuration](#timeout-configuration)
- [Interrupt Handling](#interrupt-handling)
- [Breaking Changes](#breaking-changes)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Performance Tips](#performance-tips)
- [Documentation](#documentation)
- [Support](#support)

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
- **⚠️ Error Reporting**: Protocol-specific error classification with descriptive messages recorded in results
- **🖥️ Cross-Platform**: Works on Linux, macOS, and Windows (MSYS2/Git Bash) with configurable shell paths

### Six Core Functions

1. **`fzi`** - Parse **I**nput files to identify variables
2. **`fzc`** - **C**ompile input files by substituting variable values
3. **`fzo`** - Parse **O**utput files from calculations
4. **`fzr`** - **R**un complete parametric calculations end-to-end
5. **`fzd`** - Run iterative **D**esign of experiments with adaptive algorithms
6. **`fzl`** - **L**ist and validate installed models and calculators

## Installation

### Using pip

```bash
pip install funz-fz
```

### Using pipx (recommended for CLI tools)

```bash
pipx install funz-fz
```

[pipx](https://pypa.github.io/pipx/) installs the package in an isolated environment while making the CLI commands (`fz`, `fzi`, `fzc`, `fzo`, `fzr`, `fzl`, `fzd`) available globally.

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
- `fzl` - List and validate installed models and calculators
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

### fzl - List and Validate Models/Calculators

List installed models and calculators with optional validation:

```bash
# List all models and calculators
fzl

# List with validation checks
fzl --check

# Filter by pattern
fzl --models "perfect*" --calculators "ssh*"

# Different output formats
fzl --format json
fzl --format table
fzl --format markdown  # default
```

**Example output:**

```bash
$ fzl --check --format table

=== MODELS ===

Model: perfectgas ✓
  Path: /home/user/project/.fz/models/perfectgas.json
  Supported Calculators: 2
    - local
    - ssh_cluster

Model: navier-stokes ✗
  Path: /home/user/.fz/models/navier-stokes.json
  Error: Missing required field 'output'
  Supported Calculators: 0

=== CALCULATORS ===

Calculator: local ✓
  Path: /home/user/project/.fz/calculators/local.json
  URI: sh://
  Models: 1
    - perfectgas

Calculator: ssh_cluster ✓
  Path: /home/user/.fz/calculators/ssh_cluster.json
  URI: ssh://user@cluster.edu
  Models: 2
    - perfectgas
    - navier-stokes
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

### fzd - Design of Experiments

Run iterative design of experiments with adaptive algorithms:

```bash
# Basic usage with random sampling
fzd --input_dir input/ \
  --model perfectgas \
  --input_vars '{"x": "[-2;2]", "y": "[-2;2]"}' \
  --output_expression "result" \
  --algorithm examples/algorithms/randomsampling.py \
  --options '{"nvalues": 20, "seed": 42}'

# With multiple calculators for parallel evaluation
fzd --input_dir input/ \
  --model perfectgas \
  --input_vars '{"x": "[-2;2]", "y": "[-2;2]"}' \
  --output_expression "result" \
  --algorithm examples/algorithms/bfgs.py \
  --calculators '["sh://bash calc.sh", "sh://bash calc.sh"]' \
  --options '{"max_iter": 20, "tol": 1e-4}' \
  --results_dir optimization_results/
```

**Algorithm options from file:**

```bash
# Store options in a JSON file
cat > algo_config.json << 'EOF'
{"nvalues": 50, "seed": 42}
EOF

fzd -i input/ -m perfectgas \
  -v '{"x": "[-2;2]", "y": "[-2;2]"}' \
  -e "result" \
  -a examples/algorithms/randomsampling.py \
  -o algo_config.json
```

Also available as subcommand: `fz design ...`

### fz install / uninstall

Install models or algorithms from GitHub or local zip files:

```bash
# Install a model (to .fz/models/ in current project)
fz install model perfectgas
fz install model https://github.com/user/model-repo.git

# Install globally (to ~/.fz/models/)
fz install model perfectgas --global

# Install an algorithm
fz install algorithm https://github.com/user/algo-repo.git

# Uninstall
fz uninstall model perfectgas
fz uninstall algorithm myalgo
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

#### Argument Formats

FZ CLI commands support three flexible formats for specifying models, calculators, and variables:

**1. Inline JSON** - Direct JSON string:
```bash
fzr input.txt \
  --model '{"varprefix": "$", "output": {"result": "cat output.txt"}}' \
  --variables '{"temp": [10, 20, 30], "pressure": 1}' \
  --calculator "sh://bash calc.sh"
```

**2. JSON File** - Path to JSON file:
```bash
# Create model file
cat > mymodel.json << 'EOF'
{
  "varprefix": "$",
  "formulaprefix": "@",
  "delim": "{}",
  "output": {
    "result": "cat output.txt"
  }
}
EOF

# Use file path
fzr input.txt --model mymodel.json --variables vars.json --calculator "sh://calc.sh"
```

**3. Alias** - Named configuration from `.fz/` directory:
```bash
# Uses .fz/models/perfectgas.json
fzr input.txt --model perfectgas --calculator local
```

**Automatic Detection**:
- FZ automatically detects which format you're using
- Tries formats in order: Alias → JSON File → Inline JSON
- Provides helpful error messages if parsing fails
- Works for `--model`, `--calculator`, and `--variables` arguments

**Format Detection Logic**:
```python
# Examples of automatic detection
"perfectgas"                          # → Alias (no .json, no braces)
"model.json"                          # → File (ends with .json)
'{"varprefix": "$"}'                  # → Inline JSON (starts with {)
```

**Mixing Formats**:
```bash
# Mix different formats in the same command
fzr input.txt \
  --model perfectgas \                              # Alias
  --variables '{"temp": [10, 20, 30]}' \           # Inline JSON
  --calculator cluster                              # Alias
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
    input_path="input.txt",
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

#### Old Funz Syntax Compatibility

For backward compatibility with legacy Java Funz users, FZ supports the old `?var` variable syntax:

```text
# Legacy Funz syntax (still supported)
Temperature: ?T_celsius
Pressure: ?P_bar

# Equivalent modern FZ syntax
Temperature: $T_celsius
Pressure: $P_bar
```

**Behavior**:
- `?variable` is automatically converted to `$variable`
- No configuration needed - works transparently
- Useful for migrating existing Funz projects to Python
- Can mix both syntaxes in the same file

**Example**:
```python
import fz

# Input file with old Funz syntax
content = """
n_mol=?n_mol
T_celsius=?T_celsius
"""

model = {"varprefix": "$"}  # Standard FZ configuration

# Works automatically - ?n_mol treated as $n_mol
variables = fz.fzi("input.txt", model)
# Returns: {'n_mol': None, 'T_celsius': None}
```

See `examples/java_funz_syntax_example.py` for more examples.

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

### SLURM Workload Manager

Execute calculations on SLURM clusters (local or remote):

```python
# Local SLURM execution
calculators = "slurm://:compute/bash script.sh"

# Remote SLURM execution via SSH
calculators = "slurm://user@cluster.edu:gpu/bash script.sh"

# With custom SSH port
calculators = "slurm://user@cluster.edu:2222:gpu/bash script.sh"

# Multiple partitions for parallel execution
calculators = [
    "slurm://user@hpc.edu:compute/bash calc.sh",
    "slurm://user@hpc.edu:gpu/bash calc.sh"
]
```

**URI Format**: `slurm://[user@host[:port]]:partition/script`

Note: For local execution, the partition must be prefixed with a colon (`:partition`), e.g., `slurm://:compute/script.sh`

**How it works**:
1. Local execution: Uses `srun --partition=<partition> <script>` directly
2. Remote execution: Connects via SSH, transfers files, runs `srun` on remote cluster
3. Automatically handles SLURM partition scheduling
4. Supports interrupt handling (Ctrl+C terminates SLURM jobs)

**Features**:
- Local or remote SLURM execution
- Automatic file transfer for remote execution (via SFTP)
- SLURM partition specification
- Timeout and interrupt handling
- Compatible with all SLURM schedulers

**Requirements**:
- Local: SLURM installed (`srun` command available)
- Remote: SSH access to SLURM cluster + `paramiko` library

### Funz Server Execution

Execute calculations using the Funz server protocol (compatible with legacy Java Funz servers):

```python
# Connect to local Funz server
calculators = "funz://:5555/R"

# Connect to remote Funz server
calculators = "funz://server.example.com:5555/Python"

# Multiple Funz servers for parallel execution
calculators = [
    "funz://:5555/R",
    "funz://:5556/R",
    "funz://:5557/R"
]
```

**Features**:
- Compatible with legacy Java Funz calculator servers
- Automatic file upload to server
- Remote execution with the Funz protocol
- Result download and extraction
- Support for interrupt handling
- UDP discovery for automatic server detection

**UDP Discovery**:

FZ supports automatic Funz server discovery via UDP broadcast:

```python
from fz.runners import discover_funz_servers

# Discover all available Funz servers on the network
servers = discover_funz_servers(timeout=5)

# Returns list of discovered servers:
# [
#   {'host': '192.168.1.100', 'port': 5555, 'code': 'R'},
#   {'host': '192.168.1.101', 'port': 5555, 'code': 'Python'},
#   ...
# ]

# Use discovered servers
calculators = [f"funz://{s['host']}:{s['port']}/{s['code']}" for s in servers]
results = fz.fzr("input.txt", input_variables, model, calculators=calculators)
```

**Discovery Protocol**:
- Broadcasts UDP message on port 19001
- Servers respond with their host, port, and supported codes
- Useful for dynamic calculator allocation in cluster environments
- See `context/funz-protocol.md` for detailed protocol documentation

**Protocol**:
- Text-based TCP socket communication
- Calculator reservation with authentication
- Automatic cleanup and unreservation

**URI Format**: `funz://[host]:<port>/<code>`
- `host`: Server hostname (default: localhost)
- `port`: Server port (required)
- `code`: Calculator code/model name (e.g., "R", "Python", "Modelica")

**Example**:
```python
import fz

model = {
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300]},
    model,
    calculators="funz://:5555/R"
)
```

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

### Calculator-Model Compatibility

FZ automatically validates that calculators support the specified model to prevent incompatible combinations:

```python
# .fz/calculators/cluster.json
{
    "uri": "ssh://user@cluster.edu",
    "models": {
        "perfectgas": "bash /path/to/perfectgas.sh",
        "cfd": "bash /path/to/cfd.sh"
    }
}
```

**Validation**:

```python
# This works - perfectgas is supported
results = fz.fzr("input.txt", input_variables, "perfectgas", calculators="cluster")

# This fails with clear error - unsupported_model not in calculator's models
results = fz.fzr("input.txt", input_variables, "unsupported_model", calculators="cluster")
# Error: Calculator 'cluster' does not support model 'unsupported_model'
#        Supported models: perfectgas, cfd
```

**Automatic Resolution**:
- Model and calculator aliases are resolved from `.fz/` directories
- Compatibility check happens before execution
- Clear error messages indicate which models are supported
- Prevents wasted computation on incompatible setups

**Direct URIs (No Validation)**:

When using direct calculator URIs (not aliases), no validation occurs:

```python
# No validation - you're responsible for compatibility
results = fz.fzr(
    "input.txt",
    input_variables,
    "anymodel",
    calculators="sh://bash any_script.sh"
)
```

**Best Practice**:
- Use calculator aliases for complex setups
- Document model compatibility in calculator JSON files
- Use `fzl --check` to validate configurations

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

### Progress Callbacks

Monitor execution progress in real-time with custom callback functions:

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

# Define callback function
def progress_callback(event_type, case_info):
    """
    Called during execution for each case event.

    Args:
        event_type: One of "case_start", "case_complete", "case_failed"
        case_info: Dict with case details (case_name, calculator, etc.)
    """
    if event_type == "case_start":
        print(f"⏳ Starting: {case_info['case_name']}")
    elif event_type == "case_complete":
        print(f"✅ Completed: {case_info['case_name']}")
    elif event_type == "case_failed":
        print(f"❌ Failed: {case_info['case_name']} - {case_info.get('error', 'Unknown error')}")

# Run with callback
results = fz.fzr(
    "input.txt",
    {"param": [1, 2, 3, 4, 5]},
    model,
    calculators="sh://bash calc.sh",
    results_dir="results",
    callbacks=[progress_callback]
)
```

**Use Cases**:
- Custom progress bars
- Real-time logging and monitoring
- Integration with external monitoring systems
- UI updates for long-running calculations
- Performance profiling

**Multiple Callbacks**:
```python
def logger_callback(event_type, case_info):
    # Log to file
    with open("execution.log", "a") as f:
        f.write(f"{event_type}: {case_info}\n")

def metrics_callback(event_type, case_info):
    # Send to monitoring system
    send_to_prometheus(event_type, case_info)

results = fz.fzr(..., callbacks=[logger_callback, metrics_callback])
```

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
    input_path="input.txt",
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
    input_path="input.txt",
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
    input_path="input.txt",
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
    input_path="input.txt",
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
    input_path="input.txt",
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

# Custom shell binary search path (overrides system PATH)
# Windows example: SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\Program Files\Git\usr\bin
# Linux/macOS example: export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin
export FZ_SHELL_PATH=/usr/local/bin:/usr/bin

# Run timeout in seconds (default: 600 = 10 minutes)
export FZ_RUN_TIMEOUT=3600
```

### Shell Path Configuration (FZ_SHELL_PATH)

The `FZ_SHELL_PATH` environment variable allows you to specify custom locations for shell binaries (grep, awk, sed, etc.) used in model output expressions and calculator commands. This is particularly important on Windows where Unix-like tools may be installed in non-standard locations.

**Why use FZ_SHELL_PATH?**
- **Windows compatibility**: Locate tools in MSYS2, Git Bash, Cygwin, or WSL
- **Custom installations**: Use specific versions of tools from custom directories
- **Priority control**: Override system PATH to ensure correct tool versions
- **Performance**: Cached binary paths for faster resolution

**Usage examples:**

```bash
# Windows with MSYS2 (use semicolon separator)
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin

# Windows with Git Bash
SET FZ_SHELL_PATH=C:\Program Files\Git\usr\bin;C:\Program Files\Git\bin

# Linux/macOS (use colon separator)
export FZ_SHELL_PATH=/opt/homebrew/bin:/usr/local/bin

# Priority: FZ_SHELL_PATH paths are checked BEFORE system PATH
```

**How it works:**
1. Commands in model `output` dictionaries are parsed for binary names (grep, awk, etc.)
2. Binary names are resolved to absolute paths using FZ_SHELL_PATH
3. Commands in `sh://` calculators are similarly resolved
4. Windows: Automatically tries both `command` and `command.exe`
5. Resolved paths are cached for performance

**Example in model:**
```python
model = {
    "output": {
        "pressure": "grep 'pressure' output.txt | awk '{print $2}'"
    }
}
# With FZ_SHELL_PATH=C:\msys64\usr\bin, executes:
# C:\msys64\usr\bin\grep.exe 'pressure' output.txt | C:\msys64\usr\bin\awk.exe '{print $2}'
```

See `context/shell-path.md` and `examples/shell_path_example.md` for detailed documentation.

### Timeout Configuration

FZ provides flexible timeout settings at multiple levels for controlling calculation execution time:

#### 1. Environment Variable (Global Default)

```bash
# Set default timeout for all calculations (in seconds)
export FZ_RUN_TIMEOUT=3600  # 1 hour (default: 600 seconds = 10 minutes)
```

#### 2. Model Configuration (Per-Model)

```python
model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"},
    "timeout": 1800  # 30 minutes for this model
}

results = fz.fzr("input.txt", input_variables, model, calculators="sh://calc.sh")
```

#### 3. Calculator URI Parameter (Per-Calculator)

```python
# Set timeout directly in calculator URI
calculators = [
    "sh://bash quick_calc.sh?timeout=300",      # 5 minutes
    "sh://bash slow_calc.sh?timeout=7200",       # 2 hours
    "ssh://user@hpc.edu/sbatch job.sh?timeout=86400"  # 24 hours
]

results = fz.fzr("input.txt", input_variables, model, calculators=calculators)
```

#### Priority Order (highest to lowest)

1. **Calculator URI parameter** (`?timeout=300`)
2. **Model configuration** (`model["timeout"]`)
3. **Environment variable** (`FZ_RUN_TIMEOUT`)
4. **Default** (600 seconds = 10 minutes)

**Example combining multiple levels**:

```python
import os

# Global default: 1 hour
os.environ['FZ_RUN_TIMEOUT'] = '3600'

# Model-specific: 30 minutes
model = {
    "timeout": 1800,
    "output": {"result": "cat output.txt"}
}

# Override for specific calculator: 2 hours
calculators = [
    "cache://previous_results",
    "sh://bash calc.sh?timeout=7200",  # Uses 2 hours (URI overrides)
    "sh://bash calc.sh"                 # Uses 30 minutes (model timeout)
]

results = fz.fzr("input.txt", input_variables, model, calculators=calculators)
```

**Timeout Behavior**:
- Calculation terminates after timeout expires
- Marked as "failed" with timeout error
- Retry mechanism may attempt with next calculator
- Partial results preserved for debugging

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
│   ├── algorithms/          # Algorithm plugins
│   │   ├── myalgo.py
│   │   └── myalgo.R
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

## Installing Plugins

FZ supports installing models and algorithms as plugins from GitHub repositories, local zip files, or URLs.

### Installing Algorithm Plugins

Algorithm plugins enable design of experiments and optimization workflows. Install algorithms from GitHub repositories in the `fz-<algorithm>` format:

#### From GitHub Repository Name

```bash
# Install from Funz organization (convention: fz-<algorithm>)
fz install algorithm montecarlo

# This installs from: https://github.com/Funz/fz-montecarlo
```

```python
# Python API
import fz

# Install locally (.fz/algorithms/)
fz.install_algorithm("montecarlo")

# Install globally (~/.fz/algorithms/)
fz.install_algorithm("montecarlo", global_install=True)
```

#### From GitHub URL

```bash
# Install from full URL
fz install algorithm https://github.com/YourOrg/fz-custom-algo
```

```python
fz.install_algorithm("https://github.com/YourOrg/fz-custom-algo")
```

#### From Local Zip File

```bash
# Install from downloaded zip
fz install algorithm ./fz-myalgo.zip
```

```python
fz.install_algorithm("./fz-myalgo.zip")
```

#### Using Installed Algorithms

Once installed, algorithms can be referenced by name:

```python
import fz

# Use installed algorithm plugin
results = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[-5;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",  # Plugin name (no path or extension)
    calculators=["sh://bash calc.sh"],
    algorithm_options={"batch_sample_size": 20}
)
```

### Installing Model Plugins

Model plugins define input parsing and output extraction patterns. Install models from GitHub:

#### From GitHub Repository Name

```bash
# Install from Funz organization (convention: fz-<model>)
fz install model moret

# This installs from: https://github.com/Funz/fz-moret
```

```python
# Python API
import fz

# Install locally (.fz/models/)
fz.install("moret")

# Install globally (~/.fz/models/)
fz.install("moret", global_install=True)
```

#### From GitHub URL or Local Zip

```bash
fz install model https://github.com/Funz/fz-moret
fz install model ./fz-moret.zip
```

### Listing Installed Plugins

```bash
# List installed algorithms
fz list algorithms

# List only global algorithms
fz list algorithms --global

# List installed models
fz list models

# List only global models
fz list models --global
```

```python
# Python API
import fz

# List algorithms
algorithms = fz.list_algorithms()
for name, info in algorithms.items():
    print(f"{name} ({info['type']}) - {info['file']}")

# List models
models = fz.list_models()
for name, model in models.items():
    print(f"{name}: {model.get('id', 'N/A')}")
```

### Uninstalling Plugins

```bash
# Uninstall algorithm
fz uninstall algorithm montecarlo

# Uninstall from global location
fz uninstall algorithm montecarlo --global

# Uninstall model
fz uninstall model moret
```

```python
# Python API
import fz

# Uninstall algorithm
fz.uninstall_algorithm("montecarlo")

# Uninstall model
fz.uninstall("moret")
```

### Plugin Priority

When the same plugin exists in multiple locations, FZ uses the following priority:

1. **Project-level** (`.fz/algorithms/` or `.fz/models/`) - Highest priority
2. **Global** (`~/.fz/algorithms/` or `~/.fz/models/`) - Fallback

This allows project-specific customization while maintaining a personal library of reusable plugins.

### Creating Algorithm Plugins

To create your own algorithm plugin repository (for sharing or distribution):

1. **Create repository** named `fz-<algorithm>` (e.g., `fz-montecarlo`)

2. **Add algorithm file** as `<algorithm>.py` or `<algorithm>.R` in repository root or `.fz/algorithms/`:

```python
# montecarlo.py
class MonteCarlo:
    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 100)

    def get_initial_design(self, input_vars, output_vars):
        import random
        samples = []
        for _ in range(self.n_samples):
            sample = {}
            for var, (min_val, max_val) in input_vars.items():
                sample[var] = random.uniform(min_val, max_val)
            samples.append(sample)
        return samples

    def get_next_design(self, X, Y):
        return []  # One-shot sampling

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        mean = sum(valid_Y) / len(valid_Y) if valid_Y else 0
        return {"text": f"Mean: {mean:.2f}", "data": {"mean": mean}}
```

3. **Push to GitHub** and share repository URL

4. **Install** using `fz install algorithm <name>` or `fz install algorithm <url>`

See `examples/algorithms/PLUGIN_SYSTEM.md` for complete documentation on the algorithm plugin system.

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

## Breaking Changes

### Version 0.9.1

#### fzr Directory Structure Change

**Previous behavior** (< 0.9.1):
- `fzr` created subdirectories only when multiple values were provided for variables
- Single values resulted in flat directory structure

**New behavior** (>= 0.9.1):
- `fzr` creates subdirectories in `results_dir` as long as **any** `input_variable` is provided
- No subdirectories only when `input_variables={}` (empty dict)
- More consistent and predictable behavior

**Example**:

```python
import fz

model = {"output": {"result": "cat output.txt"}}

# Single value - OLD: flat directory, NEW: subdirectory
results = fz.fzr(
    "input.txt",
    {"temp": 25},  # Single value
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)

# OLD (< 0.9.1):
#   results/input.txt, results/output.txt, ...
#
# NEW (>= 0.9.1):
#   results/temp=25/input.txt, results/temp=25/output.txt, ...

# Only flat when explicitly empty
results = fz.fzr(
    "input.txt",
    {},  # Empty - no variables
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
# Both versions: results/input.txt, results/output.txt, ... (flat)
```

**Migration**:
- Update scripts expecting flat directory structure for single-value cases
- Use path parsing from `fzo` to handle subdirectory names
- Benefits: Better organization, consistent with parametric study expectations

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

### Windows / Cross-Platform

**Problem**: Shell commands fail on Windows
```bash
# Solution: Install MSYS2 and set FZ_SHELL_PATH to point to its binaries
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
# See examples/shell_path_example.md for details
```

**Problem**: Line ending issues on Windows
```bash
# Solution: Write input files with Unix line endings (newline='\n')
# FZ templates and shell scripts expect LF, not CRLF
with open("input.txt", "w", newline='\n') as f:
    f.write(content)
```

**Problem**: `chmod` has no effect on Windows
```bash
# This is expected — Windows does not support Unix file permissions.
# Shell scripts run via sh:// do not need chmod on Windows.
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

## Documentation

### Main Documentation

- **README.md** (this file) - Complete user guide with examples
- **NEWS.md** - Release notes and changelog (version 0.9.1 and later)
- **context/funz-protocol.md** - Funz protocol and UDP discovery documentation
- **context/shell-path.md** - FZ_SHELL_PATH configuration details
- **claude/** - Developer documentation and session notes

### Context Documentation

Modular documentation in the `context/` directory:

- **context/INDEX.md** - Documentation overview and navigation
- **context/overview.md** - High-level FZ concepts and design
- **context/core-functions.md** - API reference for fzi, fzc, fzo, fzr, fzl, fzd
- **context/calculators.md** - Calculator types, URIs, and configuration
- **context/model-definition.md** - Model structure, aliases, and output parsing
- **context/formulas-and-interpreters.md** - Formula evaluation (Python/R)
- **context/syntax-guide.md** - Input template syntax reference
- **context/parallel-and-caching.md** - Performance optimization strategies
- **context/quick-examples.md** - Common usage patterns and snippets

### Examples

Practical examples in the `examples/` directory:

- **examples/examples.md** - Overview of all examples
- **examples/fzd_example.md** - Iterative design of experiments (fzd) examples
- **examples/dataframe_input.md** - DataFrame input for non-factorial designs
- **examples/algorithm_options_example.md** - Algorithm options format guide
- **examples/r_interpreter_example.md** - R interpreter setup and usage
- **examples/shell_path_example.md** - FZ_SHELL_PATH configuration examples
- **examples/java_funz_syntax_example.py** - Legacy Funz syntax compatibility
- **examples/fzi_formulas_example.py** - Formula evaluation examples
- **examples/fzi_static_objects_example.py** - Static object handling

### Test Examples

Working examples in test files:

- `tests/test_examples_*.py` - Comprehensive integration tests
- `tests/test_parallel.py` - Parallel execution examples
- `tests/test_interrupt_handling.py` - Interrupt handling demonstrations
- `tests/test_funz_protocol.py` - Funz server protocol examples
- `tests/test_slurm_runner.py` - SLURM workload manager examples

## Support

- **Issues**: https://github.com/Funz/fz/issues
- **Documentation**: https://fz.github.io
- **Repository**: https://github.com/Funz/fz
