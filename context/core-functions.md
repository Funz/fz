# FZ Core Functions

## The Four Core Functions

FZ provides four main functions for parametric computing:

1. **`fzi`** - Parse **I**nput files to identify variables
2. **`fzc`** - **C**ompile input files by substituting variables
3. **`fzo`** - Parse **O**utput files from calculations
4. **`fzr`** - **R**un complete parametric calculations end-to-end

## fzi - Parse Input Variables

**Purpose**: Identify all variables in an input file or directory.

### Function Signature

```python
import fz

variables = fz.fzi(input_path, model)
```

**Parameters**:
- `input_path` (str): Path to input file or directory
- `model` (dict or str): Model definition or alias

**Returns**: Dictionary with variable names as keys (values are None)

### Examples

**Example 1: Parse single file**

```python
import fz

model = {"varprefix": "$", "delim": "{}"}

# input.txt contains: Temperature: ${temp}, Pressure: ${pressure}
variables = fz.fzi("input.txt", model)
print(variables)
# Output: {'temp': None, 'pressure': None}
```

**Example 2: Parse directory**

```python
# Scans all files in directory
variables = fz.fzi("input_dir/", model)
# Returns all unique variables found across all files
```

**Example 3: Variables with formulas**

```python
# input.txt:
# n_mol=$n_mol
# T_celsius=$T_celsius
# #@ T_kelvin = $T_celsius + 273.15
# T_kelvin=@{T_kelvin}

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}

variables = fz.fzi("input.txt", model)
print(variables)
# Output: {'n_mol': None, 'T_celsius': None}
# Note: T_kelvin is not a variable, it's a formula
```

### Use Cases

- **Discovery**: Find all parameters in legacy input files
- **Validation**: Check what variables are expected before running
- **Documentation**: Generate parameter lists automatically

## fzc - Compile Input Files

**Purpose**: Substitute variable values and evaluate formulas to create compiled input files.

### Function Signature

```python
import fz

fz.fzc(input_path, input_variables, model, output_dir)
```

**Parameters**:
- `input_path` (str): Path to input file or directory
- `input_variables` (dict): Variable values (scalar or list)
- `model` (dict or str): Model definition or alias
- `output_dir` (str): Output directory path

**Returns**: None (writes files to output_dir)

### Examples

**Example 1: Single compilation**

```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}

input_variables = {
    "temp": 25,
    "pressure": 101.3,
    "volume": 1.0
}

fz.fzc("input.txt", input_variables, model, "compiled/")
# Creates: compiled/input.txt with values substituted
```

**Example 2: Multiple compilations (Cartesian product)**

```python
input_variables = {
    "temp": [10, 20, 30],      # 3 values
    "pressure": [1, 10],        # 2 values
    "volume": 1.0               # 1 value (fixed)
}

fz.fzc("input.txt", input_variables, model, "compiled_grid/")

# Creates 6 subdirectories:
# compiled_grid/temp=10,pressure=1/input.txt
# compiled_grid/temp=10,pressure=10/input.txt
# compiled_grid/temp=20,pressure=1/input.txt
# compiled_grid/temp=20,pressure=10/input.txt
# compiled_grid/temp=30,pressure=1/input.txt
# compiled_grid/temp=30,pressure=10/input.txt
```

**Example 3: With formula evaluation**

```python
# input.txt:
# Temperature: $T_celsius C
# #@ T_kelvin = $T_celsius + 273.15
# Temperature (K): @{T_kelvin}

input_variables = {"T_celsius": 25}

fz.fzc("input.txt", input_variables, model, "compiled/")

# compiled/input.txt:
# Temperature: 25 C
# Temperature (K): 298.15
```

### Use Cases

- **Batch preparation**: Create many input files for manual runs
- **Testing**: Verify variable substitution before full runs
- **Integration**: Pre-generate inputs for external tools

## fzo - Read Output Files

**Purpose**: Parse calculation results from output directories.

### Function Signature

```python
import fz

results_df = fz.fzo(results_path, model)
```

**Parameters**:
- `results_path` (str): Path to results directory (supports glob patterns)
- `model` (dict or str): Model definition with output commands

**Returns**: pandas DataFrame with parsed results

### Examples

**Example 1: Parse single directory**

```python
import fz

model = {
    "output": {
        "pressure": "grep 'Pressure:' output.txt | awk '{print $2}'",
        "temperature": "grep 'Temperature:' output.txt | awk '{print $2}'"
    }
}

results = fz.fzo("results/case1/", model)
print(results)
#                path  pressure  temperature
# 0  results/case1/     101.3         25.0
```

**Example 2: Parse multiple directories with glob**

```python
# results/
#   temp=10,pressure=1/output.txt
#   temp=10,pressure=10/output.txt
#   temp=20,pressure=1/output.txt

results = fz.fzo("results/*", model)
print(results)
#                      path  pressure  temp  pressure_var
# 0  temp=10,pressure=1     50.0      10.0  1
# 1  temp=10,pressure=10    500.0     10.0  10
# 2  temp=20,pressure=1     100.0     20.0  1

# Note: Variables automatically extracted from directory names
```

**Example 3: Complex output extraction**

```python
model = {
    "output": {
        "max_velocity": "grep 'Max velocity' log.txt | tail -1 | awk '{print $3}'",
        "cpu_time": "grep 'CPU time' log.txt | awk '{print $4}'",
        "converged": "grep -q 'CONVERGED' log.txt && echo 1 || echo 0"
    }
}

results = fz.fzo("simulation_results/*", model)
```

### Automatic Variable Extraction

If subdirectory names follow the pattern `key1=val1,key2=val2,...`, variables are automatically extracted as DataFrame columns:

```python
# Directory: results/mesh=100,dt=0.01,solver=fast/
# Automatically creates columns: mesh=100, dt=0.01, solver="fast"
```

### Output Type Casting

Values are automatically cast to appropriate types:

```python
# "42" → 42 (int)
# "3.14" → 3.14 (float)
# "[1, 2, 3]" → [1, 2, 3] (list)
# '{"key": "value"}' → {"key": "value"} (dict)
# "[42]" → 42 (single-element list simplified)
```

### Use Cases

- **Post-processing**: Extract results from existing calculations
- **Analysis**: Collect results into DataFrame for plotting/statistics
- **Validation**: Check outputs without re-running calculations

## fzr - Run Parametric Calculations

**Purpose**: Execute complete parametric study end-to-end with automatic parallelization.

### Function Signature

```python
import fz

results_df = fz.fzr(
    input_path,
    input_variables,
    model,
    calculators,
    results_dir="results"
)
```

**Parameters**:
- `input_path` (str): Input file or directory path
- `input_variables` (dict): Variable values (creates Cartesian product of lists)
- `model` (dict or str): Model definition or alias
- `calculators` (str or list): Calculator URI(s)
- `results_dir` (str): Results directory path (default: "results")

**Returns**: pandas DataFrame with all results and metadata

### Examples

**Example 1: Basic parametric study**

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300], "pressure": [1, 10]},  # 6 cases
    model,
    calculators="sh://bash calculate.sh",
    results_dir="results"
)

print(results)
#    temp  pressure  result  status calculator  error  command
# 0   100         1   100.5    done     sh://    None  bash ...
# 1   100        10  1005.0    done     sh://    None  bash ...
# 2   200         1   200.5    done     sh://    None  bash ...
# 3   200        10  2010.0    done     sh://    None  bash ...
# 4   300         1   300.5    done     sh://    None  bash ...
# 5   300        10  3015.0    done     sh://    None  bash ...
```

**Example 2: Parallel execution**

```python
# 3 parallel workers for faster execution
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},  # 100 cases
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ],  # 3 parallel workers
    results_dir="results"
)
```

**Example 3: With cache and fallback**

```python
results = fz.fzr(
    "input.txt",
    {"mesh": [100, 200, 400, 800]},
    model,
    calculators=[
        "cache://previous_run",      # Try cache first
        "sh://bash fast_method.sh",  # Fast but may fail
        "sh://bash robust_method.sh" # Robust fallback
    ],
    results_dir="new_run"
)
```

**Example 4: Remote SSH execution**

```python
results = fz.fzr(
    "input.txt",
    {"mesh_size": [100, 200, 400]},
    model,
    calculators="ssh://user@cluster.edu/bash /path/to/submit.sh",
    results_dir="hpc_results"
)
```

**Example 5: With formulas**

```python
# input.txt:
# n_mol=$n_mol
# T_celsius=$T_celsius
# V_L=$V_L
# #@ T_kelvin = $T_celsius + 273.15
# #@ V_m3 = $V_L / 1000
# T_K=@{T_kelvin}
# V=@{V_m3}

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

results = fz.fzr(
    "input.txt",
    {
        "n_mol": 1.0,
        "T_celsius": [10, 20, 30, 40],
        "V_L": [1, 2, 5]
    },  # 4×3 = 12 cases
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="perfectgas_results"
)
```

### Result DataFrame Columns

The returned DataFrame includes:

**Variable columns**: All input variables (`temp`, `pressure`, etc.)
**Output columns**: All outputs defined in model (`result`, `energy`, etc.)
**Metadata columns**:
- `status`: "done", "failed", or "interrupted"
- `calculator`: Which calculator was used
- `error`: Error message if failed (None if successful)
- `command`: Full command that was executed
- `path`: Path to result directory

### Use Cases

- **Parametric studies**: Main function for running parameter sweeps
- **Design of experiments**: Test multiple design configurations
- **Sensitivity analysis**: Vary parameters to study effects
- **Optimization**: Generate data for optimization algorithms
- **Validation**: Compare multiple methods or configurations

## Function Comparison

| Function | Input | Output | Use Case |
|----------|-------|--------|----------|
| `fzi` | Template file | Variable dict | Discover parameters |
| `fzc` | Template + values | Compiled files | Batch file generation |
| `fzo` | Result directories | DataFrame | Parse existing results |
| `fzr` | Template + values + calculator | DataFrame | Complete parametric run |

## Typical Workflows

### Workflow 1: Quick Discovery and Run

```python
# 1. Discover variables
vars = fz.fzi("input.txt", model)
print(f"Found variables: {list(vars.keys())}")

# 2. Run parametric study
results = fz.fzr(
    "input.txt",
    {var: [1, 2, 3] for var in vars},  # Use discovered variables
    model,
    "sh://bash calc.sh"
)
```

### Workflow 2: Prepare, Run, Analyze

```python
# 1. Compile inputs
fz.fzc("input.txt", variables, model, "compiled/")

# 2. Run calculations (manual or external)
# ... run calculations externally ...

# 3. Parse results
results = fz.fzo("results/*", model)
```

### Workflow 3: Iterative Development

```python
# 1. Test single case
fz.fzc("input.txt", {"temp": 25}, model, "test/")

# 2. Verify output parsing
test_results = fz.fzo("test_results/", model)
print(test_results)

# 3. Run full study
results = fz.fzr("input.txt", variables, model, calculators, "results/")
```
