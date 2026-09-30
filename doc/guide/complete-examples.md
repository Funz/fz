# Complete Examples

## Interactive Jupyter Notebooks

Explore fz features hands-on with these notebooks — open directly in Google Colab, no local install needed:

| Notebook | Topic | Colab |
|----------|-------|-------|
| 01 Getting Started | fzl, fzi, fzc, fzo, fzr — Perfect Gas PV=nRT | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Funz/fz/blob/main/examples/01_getting_started.ipynb) |
| 02 Variable Syntax & Formulas | All syntax styles, `@{}` formulas, `#@` context | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Funz/fz/blob/main/examples/02_variable_syntax_and_formulas.ipynb) |
| 03 Parametric Studies (fzr) | Grid inputs, DataFrame inputs, callbacks, parallel calculators | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Funz/fz/blob/main/examples/03_parametric_studies_fzr.ipynb) |
| 04 Design of Experiments (fzd) | Random sampling, Brent 1D minimization, BFGS 2D, Monte Carlo | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Funz/fz/blob/main/examples/04_design_of_experiments_fzd.ipynb) |
| 05 Caching & Advanced | Cache reuse, multi-output, logging, coarse-to-fine DOE | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Funz/fz/blob/main/examples/05_caching_and_advanced.ipynb) |

## Example 1: Perfect Gas Pressure Study

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

## Example 2: Remote HPC Calculation

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

## Example 3: Multi-Calculator with Failover

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

## Example 4: Design of Experiments with Adaptive Sampling

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

## Example 5: Optimization with BFGS

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
