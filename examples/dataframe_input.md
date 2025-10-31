# DataFrame Input for Non-Factorial Designs

This document explains how to use pandas DataFrames as input to FZ for non-factorial parametric studies.

## Overview

FZ supports two types of parametric study designs:

1. **Factorial Design (Dict)**: Creates all possible combinations (Cartesian product)
2. **Non-Factorial Design (DataFrame)**: Runs only specified combinations

## When to Use DataFrames

Use DataFrame input when:
- Variables have constraints or dependencies
- You need specific combinations, not all combinations
- You're importing a design from another tool (DOE software, optimization)
- You want specialized sampling (Latin Hypercube, Sobol sequences, etc.)
- You have an irregular or optimized design space

## Basic Example

### Factorial (Dict) - ALL Combinations

```python
from fz import fzr

# Dict creates Cartesian product (factorial design)
input_variables = {
    "temp": [100, 200],
    "pressure": [1.0, 2.0]
}
# Creates 4 cases: 2 × 2 = 4
# (100, 1.0), (100, 2.0), (200, 1.0), (200, 2.0)

results = fzr(input_file, input_variables, model, calculators)
```

### Non-Factorial (DataFrame) - SPECIFIC Combinations

```python
import pandas as pd
from fz import fzr

# DataFrame: each row is one case
input_variables = pd.DataFrame({
    "temp":     [100, 200, 100],
    "pressure": [1.0, 1.0, 2.0]
})
# Creates 3 cases ONLY:
# (100, 1.0), (200, 1.0), (100, 2.0)
# Note: (200, 2.0) is NOT included

results = fzr(input_file, input_variables, model, calculators)
```

## Practical Examples

### 1. Constraint-Based Design

When variables have physical or logical constraints:

```python
import pandas as pd
from fz import fzr

# Engine RPM and Load have constraints:
# - Low RPM → Low Load (avoid stalling)
# - High RPM → Higher Load possible
input_variables = pd.DataFrame({
    "rpm":  [1000, 1500, 2000, 2500, 3000],
    "load": [10,   20,   30,   40,   50]    # Load increases with RPM
})

# This pattern CANNOT be created with a dict
# Dict would create all 25 combinations (5×5), including invalid ones like:
# (1000 RPM, 50 Load) - would stall the engine

results = fzr("engine_input.txt", input_variables, model, calculators)
```

### 2. Latin Hypercube Sampling (LHS)

For efficient design space exploration with fewer samples:

```python
import pandas as pd
from scipy.stats import qmc
from fz import fzr

# Create Latin Hypercube sample in 3 dimensions
sampler = qmc.LatinHypercube(d=3, seed=42)
sample = sampler.random(n=20)  # 20 samples instead of full factorial

# Scale to actual variable ranges
input_variables = pd.DataFrame({
    "temperature": 100 + sample[:, 0] * 200,   # [100, 300]
    "pressure":    1.0 + sample[:, 1] * 4.0,   # [1.0, 5.0]
    "flow_rate":   10 + sample[:, 2] * 40      # [10, 50]
})

# Compare: Full factorial with [100,150,200,250,300] × [1,2,3,4,5] × [10,20,30,40,50]
#          would be 5×5×5 = 125 cases
# LHS: Only 20 cases, but covers the design space well

results = fzr("simulation.txt", input_variables, model, calculators)
```

### 3. Sobol Sequence Sampling

For low-discrepancy quasi-random sampling:

```python
import pandas as pd
from scipy.stats import qmc
from fz import fzr

# Generate Sobol sequence
sampler = qmc.Sobol(d=2, scramble=True, seed=42)
sample = sampler.random(n=32)  # Power of 2 recommended for Sobol

input_variables = pd.DataFrame({
    "x": sample[:, 0] * 100,  # [0, 100]
    "y": sample[:, 1] * 50    # [0, 50]
})

results = fzr("input.txt", input_variables, model, calculators)
```

### 4. Imported Design from DOE Software

Import designs from external tools:

```python
import pandas as pd
from fz import fzr

# Design created in R (DoE.base), MODDE, JMP, etc.
input_variables = pd.read_csv("central_composite_design.csv")

# Or Excel file
input_variables = pd.read_excel("doe_design.xlsx", sheet_name="Design")

# Or from a previous FZ run
previous_results = pd.read_csv("results.csv")
# Re-run with different settings
input_variables = previous_results[["temp", "pressure", "flow"]]

results = fzr("input.txt", input_variables, model, calculators)
```

### 5. Sensitivity Analysis (One-at-a-Time)

Test effect of each variable independently:

```python
import pandas as pd
from fz import fzr

# Baseline case
baseline = {"temp": 150, "pressure": 2.5, "flow": 30}

# One-at-a-time variations
oat_cases = []

# Vary temperature
for temp in [100, 125, 150, 175, 200]:
    oat_cases.append({"temp": temp, "pressure": baseline["pressure"], "flow": baseline["flow"]})

# Vary pressure
for pressure in [1.0, 1.5, 2.0, 2.5, 3.0]:
    oat_cases.append({"temp": baseline["temp"], "pressure": pressure, "flow": baseline["flow"]})

# Vary flow
for flow in [10, 20, 30, 40, 50]:
    oat_cases.append({"temp": baseline["temp"], "pressure": baseline["pressure"], "flow": flow})

input_variables = pd.DataFrame(oat_cases)
# Creates 13 cases instead of full factorial (5×5×5 = 125)

results = fzr("input.txt", input_variables, model, calculators)
```

### 6. Custom Optimization Samples

Run calculations at specific points from an optimization algorithm:

```python
import pandas as pd
import numpy as np
from fz import fzr

# Points suggested by optimization algorithm (e.g., Bayesian Optimization)
optimization_points = np.array([
    [120, 1.5],
    [180, 2.3],
    [150, 1.8],
    [200, 2.7],
    [110, 1.2]
])

input_variables = pd.DataFrame(
    optimization_points,
    columns=["temp", "pressure"]
)

results = fzr("input.txt", input_variables, model, calculators)

# Use results to inform next iteration of optimization
best_case = results.loc[results["efficiency"].idxmax()]
```

### 7. Time Series / Sequential Cases

When cases represent sequential states:

```python
import pandas as pd
import numpy as np
from fz import fzr

# Simulate a ramping process
time = np.linspace(0, 100, 50)
input_variables = pd.DataFrame({
    "time": time,
    "temperature": 100 + 2 * time,           # Linear ramp
    "pressure": 1.0 + 0.5 * np.sin(time/10)  # Oscillating pressure
})

results = fzr("input.txt", input_variables, model, calculators)
```

## DataFrame vs Dict Comparison

| Aspect | Dict (Factorial) | DataFrame (Non-Factorial) |
|--------|------------------|---------------------------|
| **Number of cases** | All combinations (product) | Exactly as many rows in DataFrame |
| **Design type** | Full factorial | Custom / irregular |
| **Use case** | Complete exploration | Specific combinations |
| **Example** | `{"x": [1,2], "y": [3,4]}` → 4 cases | `pd.DataFrame({"x":[1,2], "y":[3,4]})` → 2 cases |
| **Constraints** | Cannot handle constraints | Can handle constraints |
| **Sampling** | Grid-based | Any sampling method |

## Tips and Best Practices

### 1. Verify Your Design

Always check your DataFrame before running:

```python
# Check number of cases
print(f"Number of cases: {len(input_variables)}")

# Check for duplicates
duplicates = input_variables.duplicated()
if duplicates.any():
    print(f"Warning: {duplicates.sum()} duplicate cases found")
    input_variables = input_variables.drop_duplicates()

# Preview cases
print(input_variables.head())
```

### 2. Combine with Results

DataFrames make it easy to analyze results:

```python
import pandas as pd
from fz import fzr

input_variables = pd.DataFrame({
    "x": [1, 2, 3, 4, 5],
    "y": [10, 20, 15, 25, 30]
})

results = fzr("input.txt", input_variables, model, calculators)

# Results include all input variables
print(results[["x", "y", "output"]])

# Easy plotting
import matplotlib.pyplot as plt
plt.scatter(results["x"], results["output"], c=results["y"])
plt.xlabel("X")
plt.ylabel("Output")
plt.colorbar(label="Y")
plt.show()
```

### 3. Save and Load Designs

```python
import pandas as pd

# Save design for later
input_variables.to_csv("my_design.csv", index=False)

# Load and reuse
input_variables = pd.read_csv("my_design.csv")
results = fzr("input.txt", input_variables, model, calculators)
```

### 4. Append or Filter Cases

```python
import pandas as pd

# Start with a base design
base_design = pd.DataFrame({
    "temp": [100, 200, 300],
    "pressure": [1.0, 2.0, 3.0]
})

# Add edge cases
edge_cases = pd.DataFrame({
    "temp": [50, 350],
    "pressure": [0.5, 4.0]
})

input_variables = pd.concat([base_design, edge_cases], ignore_index=True)

# Or filter to specific range
input_variables = input_variables[
    (input_variables["temp"] >= 100) &
    (input_variables["temp"] <= 300)
]
```

## Common Patterns

### Design of Experiments (DOE)

```python
import pandas as pd
from itertools import product

# 2^k factorial design (k=3 factors, 2 levels)
factors = {
    "temp": [100, 200],
    "pressure": [1.0, 2.0],
    "flow": [10, 20]
}

# Create all combinations (this is what dict does automatically)
combinations = list(product(*factors.values()))
full_factorial = pd.DataFrame(combinations, columns=factors.keys())

# Add center points
center_point = pd.DataFrame({
    "temp": [150],
    "pressure": [1.5],
    "flow": [15]
})

# Central Composite Design = factorial + center + star points
star_points = pd.DataFrame({
    "temp": [50, 250, 150, 150, 150, 150],
    "pressure": [1.5, 1.5, 0.5, 2.5, 1.5, 1.5],
    "flow": [15, 15, 15, 15, 5, 25]
})

ccd_design = pd.concat([full_factorial, center_point, star_points], ignore_index=True)
```

### Sparse Grid / Adaptive Sampling

```python
import pandas as pd
import numpy as np

# Start with coarse grid
coarse_grid = pd.DataFrame({
    "x": [0, 50, 100],
    "y": [0, 50, 100]
})

results_coarse = fzr("input.txt", coarse_grid, model, calculators)

# Identify region of interest (e.g., high output)
threshold = results_coarse["output"].quantile(0.75)
interesting_cases = results_coarse[results_coarse["output"] > threshold]

# Refine around interesting region
refined_grid = pd.DataFrame({
    "x": np.linspace(40, 60, 10),
    "y": np.linspace(40, 60, 10)
})

results_refined = fzr("input.txt", refined_grid, model, calculators)
```

## Summary

DataFrames provide maximum flexibility for parametric studies:
- ✅ Support non-factorial designs
- ✅ Handle variable constraints
- ✅ Enable advanced sampling methods
- ✅ Easy integration with DOE tools
- ✅ Seamless result analysis

Use dicts for simple factorial designs, use DataFrames for everything else!
