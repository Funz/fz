# FZ Quick Examples and Common Patterns

## Quick Start Examples

### Example 1: Minimal Parametric Study

**Input template** (`input.txt`):
```text
param1=$x
param2=$y
```

**Calculator script** (`calc.sh`):
```bash
#!/bin/bash
source $1
echo "result=$((x * y))" > output.txt
```

**Python script**:
```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "grep result= output.txt | cut -d= -f2"}
}

results = fz.fzr(
    "input.txt",
    {"x": [1, 2, 3], "y": [10, 20]},  # 6 cases
    model,
    "sh://bash calc.sh",
    "results"
)

print(results)
#    x   y  result  status
# 0  1  10      10    done
# 1  1  20      20    done
# 2  2  10      20    done
# 3  2  20      40    done
# 4  3  10      30    done
# 5  3  20      60    done
```

### Example 2: With Formulas

**Input template**:
```text
temp_C=$T_celsius

#@ def C_to_K(celsius):
#@     return celsius + 273.15

temp_K=@{C_to_K($T_celsius)}
```

**Model and execution**:
```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {"final_temp": "grep temp_K output.txt | awk '{print $2}'"}
}

results = fz.fzr(
    "input.txt",
    {"T_celsius": [0, 25, 100]},
    model,
    "sh://bash calc.sh",
    "results"
)
```

### Example 3: Parallel Execution

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

# Run 100 cases with 4 parallel workers
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    ["sh://bash calc.sh"] * 4,  # 4 parallel calculators
    "results"
)

print(f"Completed {len(results)} calculations")
```

### Example 4: Remote SSH Execution

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "energy": "grep Energy output.log | awk '{print $2}'",
        "time": "grep 'CPU time' output.log | awk '{print $3}'"
    }
}

results = fz.fzr(
    "input.txt",
    {"mesh_size": [100, 200, 400, 800]},
    model,
    "ssh://user@cluster.edu/bash /path/to/submit.sh",
    "hpc_results"
)
```

### Example 5: Cache and Resume

```python
import fz

# First run (may be interrupted)
results1 = fz.fzr(
    "input.txt",
    {"param": list(range(50))},
    model,
    "sh://bash slow_calc.sh",
    "run1"
)

# Resume with cache
results2 = fz.fzr(
    "input.txt",
    {"param": list(range(50))},
    model,
    ["cache://run1", "sh://bash slow_calc.sh"],  # Cache first
    "run2"
)
```

## Common Patterns by Use Case

### Pattern 1: Temperature Sweep

```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {"result": "cat result.txt"}
}

# Sweep temperature from 0 to 100°C in steps of 10
results = fz.fzr(
    "input.txt",
    {"temperature": list(range(0, 101, 10))},  # [0, 10, 20, ..., 100]
    model,
    "sh://bash thermal_analysis.sh",
    "temp_sweep"
)

# Plot results
import matplotlib.pyplot as plt
plt.plot(results['temperature'], results['result'], 'o-')
plt.xlabel('Temperature (°C)')
plt.ylabel('Result')
plt.grid(True)
plt.savefig('temp_sweep.png')
```

### Pattern 2: Grid Search (2D Parameter Space)

```python
import fz
import numpy as np

# 2D parameter grid
temps = np.linspace(10, 100, 10)      # 10 temperatures
pressures = np.linspace(1, 10, 10)    # 10 pressures

results = fz.fzr(
    "input.txt",
    {
        "temp": temps.tolist(),
        "pressure": pressures.tolist()
    },  # 10×10 = 100 cases
    model,
    ["sh://bash calc.sh"] * 4,  # 4 parallel workers
    "grid_search"
)

# Create heatmap
import matplotlib.pyplot as plt
pivot = results.pivot_table(values='result', index='pressure', columns='temp')
plt.imshow(pivot, aspect='auto', origin='lower')
plt.colorbar(label='Result')
plt.xlabel('Temperature')
plt.ylabel('Pressure')
plt.savefig('heatmap.png')
```

### Pattern 3: Sensitivity Analysis

```python
import fz

# Baseline values
baseline = {
    "param1": 10,
    "param2": 20,
    "param3": 30
}

# Vary each parameter ±20% around baseline
variations = []
for param in baseline:
    for factor in [0.8, 1.0, 1.2]:  # -20%, baseline, +20%
        case = baseline.copy()
        case[param] = baseline[param] * factor
        case['varied_param'] = param
        case['variation'] = factor
        variations.append(case)

# Run all variations
results = fz.fzr(
    "input.txt",
    variations,
    model,
    "sh://bash calc.sh",
    "sensitivity"
)

# Analyze sensitivity
import pandas as pd
sensitivity = results.groupby('varied_param').agg({
    'result': ['min', 'max', 'mean', 'std']
})
print(sensitivity)
```

### Pattern 4: Monte Carlo Simulation

```python
import fz
import numpy as np

# Generate random parameter samples
np.random.seed(42)
n_samples = 1000

# Random sampling from distributions
samples = {
    "param1": np.random.uniform(10, 20, n_samples).tolist(),
    "param2": np.random.normal(100, 10, n_samples).tolist(),
    "param3": np.random.lognormal(0, 0.5, n_samples).tolist()
}

# Run Monte Carlo simulation
results = fz.fzr(
    "input.txt",
    samples,
    model,
    ["sh://bash calc.sh"] * 8,  # 8 parallel workers
    "monte_carlo"
)

# Statistical analysis
print(f"Mean result: {results['result'].mean():.2f}")
print(f"Std dev: {results['result'].std():.2f}")
print(f"95% confidence interval: {results['result'].quantile([0.025, 0.975]).tolist()}")
```

### Pattern 5: Design of Experiments (DOE)

```python
import fz
from itertools import product

# Full factorial design
factors = {
    "material": ["steel", "aluminum", "titanium"],
    "thickness": [1, 2, 3, 5],
    "temperature": [20, 100, 200]
}

# Generate all combinations
cases = []
for combination in product(*factors.values()):
    case = dict(zip(factors.keys(), combination))
    cases.append(case)

print(f"Total experiments: {len(cases)}")  # 3×4×3 = 36

# Run DOE
results = fz.fzr(
    "input.txt",
    cases,
    model,
    ["sh://bash experiment.sh"] * 4,
    "doe_results"
)

# ANOVA or regression analysis
# (use statsmodels or scipy)
```

### Pattern 6: Convergence Study

```python
import fz

# Mesh refinement study
mesh_sizes = [10, 20, 40, 80, 160, 320]

results = fz.fzr(
    "input.txt",
    {"mesh": mesh_sizes},
    model,
    "sh://bash simulation.sh",
    "convergence"
)

# Check convergence
import numpy as np
diffs = np.diff(results['result'])
rel_change = np.abs(diffs / results['result'][1:]) * 100

print("Mesh size | Result | % Change")
for i, mesh in enumerate(mesh_sizes):
    result = results.iloc[i]['result']
    change = rel_change[i-1] if i > 0 else None
    print(f"{mesh:9d} | {result:6.3f} | {change if change else 'N/A'}")
```

### Pattern 7: Multi-Method Comparison

```python
import fz

variables = {"param": [1, 2, 3, 4, 5]}

# Run with different methods
methods = {
    "fast": "sh://bash method_fast.sh",
    "accurate": "sh://bash method_accurate.sh",
    "robust": "sh://bash method_robust.sh"
}

all_results = []
for method_name, calculator in methods.items():
    results = fz.fzr(
        "input.txt",
        variables,
        model,
        calculator,
        f"results_{method_name}"
    )
    results['method'] = method_name
    all_results.append(results)

# Compare methods
import pandas as pd
comparison = pd.concat(all_results)
pivot = comparison.pivot_table(
    values='result',
    index='param',
    columns='method'
)
print(pivot)

# Statistical comparison
from scipy import stats
fast = comparison[comparison['method'] == 'fast']['result']
accurate = comparison[comparison['method'] == 'accurate']['result']
t_stat, p_value = stats.ttest_rel(fast, accurate)
print(f"T-test p-value: {p_value:.4f}")
```

### Pattern 8: Optimization Loop

```python
import fz
import numpy as np
from scipy.optimize import minimize

def objective(params):
    """Run simulation and return objective value."""
    results = fz.fzr(
        "input.txt",
        {"x": params[0], "y": params[1]},
        model,
        "sh://bash calc.sh",
        "optimization"
    )
    return results.iloc[0]['result']

# Optimization
initial_guess = [5, 5]
result = minimize(
    objective,
    initial_guess,
    method='Nelder-Mead',
    options={'maxiter': 100}
)

print(f"Optimal parameters: x={result.x[0]:.2f}, y={result.x[1]:.2f}")
print(f"Optimal result: {result.fun:.2f}")
```

## CLI Quick Examples

### Example 1: Quick Variable Check

```bash
# Check what variables are in input file
fzi input.txt --varprefix '$' --format table

# Output:
# ┌──────────┬───────┐
# │ Variable │ Value │
# ├──────────┼───────┤
# │ temp     │ None  │
# │ pressure │ None  │
# └──────────┴───────┘
```

### Example 2: Compile and Verify

```bash
# Compile input with variables
fzc input.txt \
  --varprefix '$' \
  --variables '{"temp": 25, "pressure": 101}' \
  --output compiled/

# Check compiled result
cat compiled/input.txt
```

### Example 3: Run Parametric Study from CLI

```bash
# Run parametric study
fzr input.txt \
  --varprefix '$' \
  --variables '{"temp": [10, 20, 30], "pressure": [1, 10]}' \
  --output-cmd result="cat output.txt" \
  --calculator "sh://bash calc.sh" \
  --results results/ \
  --format table

# Output:
# ┌──────┬──────────┬────────┬────────┐
# │ temp │ pressure │ result │ status │
# ├──────┼──────────┼────────┼────────┤
# │   10 │        1 │   10.5 │   done │
# │   10 │       10 │  105.0 │   done │
# │   20 │        1 │   20.5 │   done │
# │   20 │       10 │  210.0 │   done │
# │   30 │        1 │   30.5 │   done │
# │   30 │       10 │  315.0 │   done │
# └──────┴──────────┴────────┴────────┘
```

### Example 4: Parse Existing Results

```bash
# Parse results from previous run
fzo results/ \
  --output-cmd energy="grep Energy log.txt | awk '{print \$2}'" \
  --output-cmd time="grep Time log.txt | awk '{print \$2}'" \
  --format csv > analysis.csv
```

## Troubleshooting Examples

### Example: Debug Single Case

```python
import fz
import os

# Enable debug logging
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

# Run single case
results = fz.fzr(
    "input.txt",
    {"param": 1},  # Single case
    model,
    "sh://bash calc.sh",
    "debug_test"
)

# Check debug directory
print(f"Results saved in: debug_test/")
print(f"Input: debug_test/param=1/input.txt")
print(f"Output: debug_test/param=1/output.txt")
print(f"Logs: debug_test/param=1/log.txt")
```

### Example: Test Calculator Manually

```bash
# Create test input
echo "param=42" > test_input.txt

# Test calculator manually
bash calc.sh test_input.txt

# Check output
cat output.txt
```

### Example: Verify Cache Matching

```python
import fz
import os

os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

# First run
fz.fzr("input.txt", {"param": 1}, model, "sh://bash calc.sh", "run1/")

# Second run with cache (check debug logs)
fz.fzr(
    "input.txt",
    {"param": 1},
    model,
    ["cache://run1", "sh://bash calc.sh"],
    "run2/"
)
# Debug logs will show: "Cache hit for case: ..."
```

## Integration Examples

### Example: Integration with Pandas

```python
import fz
import pandas as pd

# Run parametric study
results = fz.fzr("input.txt", variables, model, calculators, "results/")

# Advanced pandas operations
summary = results.groupby('temp').agg({
    'result': ['mean', 'std', 'min', 'max'],
    'status': 'count'
})

# Filter and analyze
successful = results[results['status'] == 'done']
high_results = successful[successful['result'] > threshold]

# Export to various formats
results.to_csv('results.csv', index=False)
results.to_excel('results.xlsx', index=False)
results.to_json('results.json', orient='records')
```

### Example: Integration with Matplotlib

```python
import fz
import matplotlib.pyplot as plt

results = fz.fzr("input.txt", variables, model, calculators, "results/")

# Create subplot for each parameter
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

axes[0, 0].scatter(results['temp'], results['result'])
axes[0, 0].set_xlabel('Temperature')
axes[0, 0].set_ylabel('Result')

axes[0, 1].hist(results['result'], bins=30)
axes[0, 1].set_xlabel('Result')
axes[0, 1].set_ylabel('Frequency')

# ... more plots ...

plt.tight_layout()
plt.savefig('analysis.png', dpi=300)
```

### Example: Integration with Jupyter Notebooks

```python
# In Jupyter notebook
import fz
from IPython.display import display

# Run study
results = fz.fzr("input.txt", variables, model, calculators, "results/")

# Interactive display
display(results.head())
display(results.describe())

# Interactive plots
%matplotlib inline
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.scatter(results['temp'], results['result'], c=results['pressure'], cmap='viridis')
plt.colorbar(label='Pressure')
plt.xlabel('Temperature')
plt.ylabel('Result')
plt.show()
```

## Best Practice Examples

### Example: Organized Project Structure

```
my_project/
├── input_templates/
│   ├── simulation.txt
│   └── config.txt
├── calculators/
│   ├── local_fast.sh
│   └── local_robust.sh
├── .fz/
│   ├── models/
│   │   └── my_model.json
│   └── calculators/
│       └── cluster.json
├── scripts/
│   ├── run_study.py
│   └── analyze_results.py
└── results/
    └── (generated by FZ)
```

**`scripts/run_study.py`**:
```python
import fz
from pathlib import Path

# Define paths
BASE_DIR = Path(__file__).parent.parent
INPUT = BASE_DIR / "input_templates" / "simulation.txt"
RESULTS = BASE_DIR / "results" / "study1"

# Run study using model alias
results = fz.fzr(
    str(INPUT),
    {"temp": [10, 20, 30], "pressure": [1, 10]},
    "my_model",  # Loads from .fz/models/my_model.json
    "cluster",   # Loads from .fz/calculators/cluster.json
    str(RESULTS)
)

# Save results
results.to_csv(RESULTS / "summary.csv", index=False)
print(f"Results saved to: {RESULTS}")
```

This completes the FZ context documentation for LLMs!
