# CLI Usage

FZ provides command-line tools for quick operations without writing Python scripts. All four core functions are available as CLI commands.

## Installation of CLI Tools

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

## fzi - Parse Input Variables

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

## fzc - Compile Input Files

Substitute variables and create compiled input files:

```bash
# Basic usage (writes compiled/T_celsius=25,V_L=10,n_mol=1/input.txt:
# one sub-directory per case, even for scalar values)
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
├── T_celsius=10,V_L=1,n_mol=1/
│   └── input.txt
├── T_celsius=10,V_L=2,n_mol=1/
│   └── input.txt
├── T_celsius=20,V_L=1,n_mol=1/
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

## fzo - Read Output Files

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

## fzl - List and Validate Models/Calculators

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

## fzr - Run Parametric Calculations

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

## fzd - Design of Experiments

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

# Monte Carlo sampling of the perfect-gas study, several batches
fzd --input_dir input/ \
  --model perfectgas \
  --input_vars '{"T_celsius": "[10;50]", "V_L": "[1;10]", "n_mol": "1"}' \
  --calculators "sh://bash PerfectGazPressure.sh" \
  --output_expression "pressure" \
  --algorithm examples/algorithms/montecarlo_uniform.py \
  --options '{"batch_sample_size": 20, "max_iterations": 10}' \
  --results_dir fzd_results/

# Fixed and variable inputs (V_L fixed at 5.0, T_celsius explored by algorithm)
fzd --input_dir input/ \
  --model perfectgas \
  --input_vars '{"T_celsius": "[10;50]", "V_L": "5.0", "n_mol": "1"}' \
  --calculators "sh://bash calc.sh" \
  --output_expression "pressure" \
  --algorithm examples/algorithms/brent.py \
  --results_dir brent_results/
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

Short form: `fzd -i input/ -m perfectgas -v '...' -e "pressure" -a algo.py -o options.json`.
Also available as subcommand: `fz design --input_dir input/ ...`.

**Key differences from fzr**:
- `--input_vars` uses `"[min;max]"` for ranges (the algorithm decides the values) or `"value"` (a string) for fixed values
- Requires `--algorithm`: an algorithm name (`randomsampling`, `brent`, `bfgs`, ...) or the path to a `.py` file
- Algorithm options via `--options` (JSON dict or file)
- Results directory via `--results_dir` (default: `results_fzd`); if it already exists it is renamed with a timestamp and its cached results are still reused
- Duplicate design points within a batch are automatically deduplicated and their results reused

## fz install / uninstall

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

## CLI Options Reference

### Common Options (all commands)

```
--help, -h                Show help message
--version                 Show version
--model MODEL             Model alias or inline definition
--varprefix PREFIX        Variable prefix (default: $)
--delim DELIMITERS        Variable and formula delimiters ({} when --model is absent;
                          a --model without "delim" keeps () for variables)
--formulaprefix PREFIX    Formula prefix (default: @)
--commentline CHAR        Comment character (default: #)
--format FORMAT           Output format: json, table, csv, markdown, html
```

### Exit Codes and Output Streams

CLI commands are script-friendly: results are printed to **stdout**, while log messages
(`FZ_LOG_LEVEL`), the progress bar, and error messages go to **stderr**. The progress bar
is automatically disabled when stderr is not a terminal (piped/redirected output or CI).

```bash
# stdout contains only the JSON results; logs and progress stay on stderr
fzr input.txt --model perfectgas --variables '{"x": [1, 2]}' \
    --calculator "sh://bash calc.sh" --format json > results.json 2> run.log
```

Exit codes: `0` on success, non-zero on errors (invalid arguments, missing files, ...).
`fzr` also exits with `1` when **no case succeeded**; partial success exits `0` with
per-case details in the `status` column.

### Argument Formats

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

### Model Definition Options

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

### fzr-Specific Options

```
--calculator URI          Calculator URI (can be specified multiple times)
--results DIR             Results directory (default: results)
--case_naming SCHEME      Case directory naming: path (default), hash, or index
```

## Complete CLI Examples

### Example 1: Quick Variable Discovery

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

### Example 2: Quick Compilation Test

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

### Example 3: Parse Existing Results

```bash
# Extract results from previous calculations
$ fzo old_results/ \
  --output-cmd energy="grep 'Total Energy' log.txt | awk '{print \$3}'" \
  --output-cmd time="grep 'CPU Time' log.txt | awk '{print \$3}'" \
  --format csv > analysis.csv
```

### Example 4: End-to-End Parametric Study

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

### Example 5: Using Model and Calculator Aliases

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

### Example 6: Interrupt and Resume

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

## Environment Variables for CLI

The `FZ_*` environment variables (logging, workers, retries, timeouts, SSH, shell path, caching,
...) apply to the CLI exactly as to the Python API; they are listed in [Configuration](configuration.md).
For example:

```bash
FZ_LOG_LEVEL=DEBUG FZ_MAX_WORKERS=4 fzr input.txt --model perfectgas --calculators "sh://bash calc.sh" ...
```
