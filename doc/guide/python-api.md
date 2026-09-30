# Core Functions

<!-- counterpart-note -->
> Guide page (from the former README). Reference counterpart in `doc/`: [`core-functions.md`](../core-functions.md). When behaviour changes, update both.


## fzi - Parse Input Variables

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

## fzc - Compile Input Files

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
- `input_variables`: Dictionary of variable values (scalar or list). Optional (default
  `None`) when the input files declare no variables (non-parametric dataset) — omit it
  and pass `model` as a keyword argument: `fz.fzc(input_path, model=model)`. If the
  input files do declare variables and it's omitted, `fzc` raises a `ValueError` naming
  them.
- `model`: Model definition (dict or alias name)
- `output_dir`: Output directory path

## fzo - Read Output Files

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

If subdirectories were instead named with `case_naming="hash"` or `"index"` (see below),
`fzo` recovers the variable columns from `cases.csv`, a single manifest `fzr` writes
at the results root mapping each case directory to its variables (falling back to
each case's own `info.txt`, which always has `input.<var>=<value>` lines, if the
manifest is missing or incomplete).

## fzr - Run Parametric Calculations

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
- `input_variables`: Variable values - dict (factorial) or DataFrame (non-factorial).
  Optional (default `None`) when the input files declare no variables (non-parametric
  dataset) — omit it and pass `model` as a keyword argument: `fz.fzr(input_path,
  model=model, calculators=calculators)`. If the input files do declare variables and
  it's omitted, `fzr` raises a `ValueError` naming them.
- `model`: Model definition (dict or alias)
- `calculators`: Calculator URI(s) - string or list
- `results_dir`: Results directory path
- `case_naming`: How each case's result/temp subdirectory is named (default `"path"`):
  - `"path"`: `var1=val1,var2=val2,...` - human-readable, but can exceed filesystem
    filename length limits (~255 chars) with many variables. Each key/value is
    percent-encoded (`/ \ : * ? " < > | %`, control characters, and a value that
    would otherwise be exactly `.`/`..`) so a variable value can never create an
    extra path segment or escape the results directory - the *directory name* only;
    `info.txt`/`cases.csv` always keep the original, un-encoded value.
  - `"hash"`: short content hash of the variable combination - always short and stable
  - `"index"`: `case_<i>` - shortest, order-dependent

  With `"hash"`/`"index"`, a single `cases.csv` manifest is written at the results
  root mapping each case directory to its variables, and `fzo()` reads it back when
  the directory name isn't a `key=val,...` pattern (falling back to each case's own
  `info.txt` if the manifest is missing or incomplete). Defaults to the
  `FZ_CASE_NAMING` env var, or `"path"`.

- `input_static`: Files identical across every case (a shared weather CSV, a large
  reference dataset) that are never templated and never duplicated per case — see
  `doc/core-functions.md` ("fzr" → `input_static`) for the full write-up. If a large
  variable-free file is left in `input_path` instead, `fzr()` logs a one-time warning
  suggesting `input_static` (threshold: `FZ_STATIC_CANDIDATE_MIN_SIZE`, default 1 MiB,
  `0` disables it).

**Returns**: pandas DataFrame with all results

## fzd - Run Design of Experiments

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
- `input_path`: Input file or directory path
- `input_variables`: Dict where `"[min;max]"` entries are varied by the algorithm and plain `"value"` entries are fixed at that value for every evaluation
- `model`: Model definition (dict or alias)
- `output_expression`: Expression to evaluate from outputs (e.g., `"pressure"` or `"out1 + out2 * 2"`)
- `algorithm`: Algorithm name (`randomsampling`, `brent`, `bfgs`, ...) or path to `.py` file
- `calculators`: Calculator URI(s) - string or list
- `algorithm_options`: Dict, JSON string, or JSON file path with algorithm-specific options
- `analysis_dir`: Analysis results directory (default: `"analysis"`); if it already exists it is renamed with a timestamp and its cached results are still reused automatically

**Returns**: Dict with:
- `XY`: pandas DataFrame with all input and output values
- `analysis`: Processed analysis results (HTML files, plots, metrics)
- `algorithm`: Algorithm path
- `iterations`: Number of iterations completed
- `total_evaluations`: Total number of function evaluations
- `summary`: Human-readable summary text

**Automatic behaviors**:
- **Batch deduplication**: duplicate points proposed by the algorithm in the same iteration are evaluated only once; results are re-mapped to all occurrences
- **Cross-iteration caching**: results from previous iterations are automatically reused — a point evaluated in iteration 2 is never re-run in iteration 5
- **Re-run resume**: if `analysis_dir` already exists it is renamed with a timestamp; all its iteration subdirectories are still consulted as cache, so a re-run with different options benefits from all prior computations

**Vector-valued outputs as objectives**: a case's model output can be a
vector (list) — see the "Vector (array) Outputs" section. `fzd`'s algorithms
always need a single scalar objective, so `output_expression` is where
such a vector gets reduced: on top of `abs()`/`min()`/`max()`/`sqrt()`/...
and indexing/slicing (`series[-1]`), the reduction functions `sum()`,
`len()`, `sorted()`, `mean()`, `median()`, `stdev()`, `variance()` are
available, e.g. `output_expression="mean(T_series)"`. Two different vector
outputs can be combined too: plain `+` concatenates them before reducing
(`mean(a + b)`), and `zip()` combines them element-wise, e.g.
`output_expression="sqrt(sum((x - y) ** 2 for x, y in zip(sim, ref)) / len(sim))"`
for an RMSE between a simulated and a reference series. Referencing a
vector-valued output without reducing it raises a clear error naming the
output and suggesting a fix; that point is simply reported as a failed
evaluation, it does not stop the run. See `examples/fzd_example.md`,
"Vector-valued outputs as objectives".

## Input Variables: Factorial vs Non-Factorial Designs

FZ supports two types of parametric study designs through different `input_variables` formats:

### Factorial Design (Dict)

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

### Non-Factorial Design (DataFrame)

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
