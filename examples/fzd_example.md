# FZD - Iterative Design of Experiments Examples

This guide demonstrates how to use `fzd()` with different algorithms for iterative design of experiments and optimization.

## Overview

The `fzd()` function enables **adaptive sampling** where algorithms intelligently choose which points to evaluate next based on previous results. This is much more efficient than grid search for optimization and root-finding problems.

## Prerequisites

**Required:**
- Python 3.7+
- FZ framework: `pip install git+https://github.com/Funz/fz.git`
- `bc` calculator:
  - Debian/Ubuntu: `sudo apt install bc`
  - macOS: `brew install bc`

**Optional algorithms** (installed as needed):
- `randomsampling.py` - Simple random sampling
- `brent.py` - 1D optimization (Brent's method)
- `bfgs.py` - Multi-dimensional optimization (BFGS method)

## Test Model

All examples use a simple mathematical model to demonstrate the concepts:

**Model:** Computes `x² + y²` (distance from origin)
- **Minimum:** at (0, 0) with value 0
- **Variables:** x and y in range [-2, 2]

### Model Definition

```python
model = {
    "varprefix": "$",
    "delim": "()",
    "run": "bash -c 'source input.txt && result=$(echo \"scale=6; $x * $x + $y * $y\" | bc) && echo \"result = $result\" > output.txt'",
    "output": {
        "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
    }
}
```

---

## Example 1: Random Sampling

Explores the parameter space using random sampling. Good for:
- Initial exploration
- Understanding the response surface
- Baseline for comparison with optimization algorithms

### Code

```python
import fz

# Run fzd with random sampling algorithm
result = fz.fzd(
    input_path="input/",
    input_variables={"x": "[-2;2]", "y": "[-2;2]"},
    model=model,
    output_expression="result",
    algorithm="examples/algorithms/randomsampling.py",
    algorithm_options={"nvalues": 10, "seed": 42}
)

print(f"Algorithm: {result['algorithm']}")
print(f"Total evaluations: {result['total_evaluations']}")
print(f"Summary: {result['summary']}")

# Find best result
df = result['XY']
best_idx = df['result'].idxmin()
print(f"\nBest result found:")
print(f"  x = {df.loc[best_idx, 'x']:.6f}")
print(f"  y = {df.loc[best_idx, 'y']:.6f}")
print(f"  result = {df.loc[best_idx, 'result']:.6f}")
```

### Key Parameters

- **`nvalues`**: Number of random samples to evaluate
- **`seed`**: Random seed for reproducibility

### Expected Output

```
Algorithm: examples/algorithms/randomsampling.py
Total evaluations: 10

Best result found:
  x = -0.123456
  y = 0.234567
  result = 0.070123
```

---

## Example 2: Brent's Method (1D Optimization)

Uses Brent's method to find the minimum of a 1D function. This is a **root-finding algorithm** adapted for optimization.

**Problem:** Find minimum of `(x - 0.7)²`
- **Expected minimum:** x = 0.7, output ≈ 0

### Code

```python
import fz

# Modified model for 1D problem: (x - 0.7)^2
model_1d = {
    "varprefix": "$",
    "delim": "()",
    "run": "bash -c 'source input.txt && result=$(echo \"scale=6; ($x - 0.7) * ($x - 0.7)\" | bc) && echo \"result = $result\" > output.txt'",
    "output": {
        "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
    }
}

# Run fzd with Brent's method
result = fz.fzd(
    input_path="input/",
    input_variables={"x": "[0;2]"},  # Only x variable (1D)
    model=model_1d,
    output_expression="result",
    algorithm="examples/algorithms/brent.py",
    algorithm_options={"max_iter": 20, "tol": 1e-3}
)

print(f"Iterations: {result['iterations']}")
print(f"Total evaluations: {result['total_evaluations']}")

# Get optimal result
df = result['XY']
best_idx = df['result'].idxmin()
print(f"\nOptimal result:")
print(f"  x = {df.loc[best_idx, 'x']:.6f} (expected: 0.7)")
print(f"  result = {df.loc[best_idx, 'result']:.6f} (expected: ~0.0)")
```

### Key Parameters

- **`max_iter`**: Maximum number of iterations
- **`tol`**: Convergence tolerance

### Algorithm Characteristics

- **Type:** 1D root finding/optimization
- **Method:** Combines bisection, secant, and inverse quadratic interpolation
- **Convergence:** Superlinear
- **Robustness:** Very robust, guaranteed to converge
- **Evaluations:** Typically 5-15 for good precision

### Expected Output

```
Iterations: 12
Total evaluations: 12

Optimal result:
  x = 0.700023 (expected: 0.7)
  result = 0.000001 (expected: ~0.0)
```

---

## Example 3: BFGS (Multi-dimensional Optimization)

Uses BFGS (Broyden-Fletcher-Goldfarb-Shanno) for multi-dimensional optimization. This is a **quasi-Newton method** that approximates the Hessian matrix.

**Problem:** Find minimum of `x² + y²`
- **Expected minimum:** (0, 0) with output = 0

### Code

```python
import fz

# Run fzd with BFGS algorithm
result = fz.fzd(
    input_path="input/",
    input_variables={"x": "[-2;2]", "y": "[-2;2]"},
    model=model,
    output_expression="result",
    algorithm="examples/algorithms/bfgs.py",
    algorithm_options={"max_iter": 20, "tol": 1e-4}
)

print(f"Algorithm: {result['algorithm']}")
print(f"Iterations: {result['iterations']}")
print(f"Total evaluations: {result['total_evaluations']}")

# Get optimal result
df = result['XY']
best_idx = df['result'].idxmin()
print(f"\nOptimal result:")
print(f"  x = {df.loc[best_idx, 'x']:.6f} (expected: 0.0)")
print(f"  y = {df.loc[best_idx, 'y']:.6f} (expected: 0.0)")
print(f"  result = {df.loc[best_idx, 'result']:.6f} (expected: ~0.0)")
```

### Key Parameters

- **`max_iter`**: Maximum number of iterations
- **`tol`**: Convergence tolerance for gradient norm

### Algorithm Characteristics

- **Type:** Multi-dimensional gradient-based optimization
- **Method:** Quasi-Newton (approximates second derivatives)
- **Convergence:** Superlinear
- **Best for:** Smooth, differentiable functions
- **Evaluations:** Typically 10-30 for good precision
- **Scales:** Works well for 2-50 dimensions

### Expected Output

```
Iterations: 8
Total evaluations: 18

Optimal result:
  x = 0.000012 (expected: 0.0)
  y = -0.000008 (expected: 0.0)
  result = 0.000000 (expected: ~0.0)
```

---

## Example 4: Custom Output Expression

Demonstrates using mathematical expressions to combine multiple model outputs.

**Model outputs:**
- `r1 = x²`
- `r2 = y²`

**Output expression:** `r1 + r2 * 2` (minimize x² + 2y²)

### Code

```python
import fz

# Model with two separate outputs
model_multi = {
    "varprefix": "$",
    "delim": "()",
    "run": "bash -c 'source input.txt && r1=$(echo \"scale=6; $x * $x\" | bc) && r2=$(echo \"scale=6; $y * $y\" | bc) && echo \"r1 = $r1\" > output.txt && echo \"r2 = $r2\" >> output.txt'",
    "output": {
        "r1": "grep 'r1 = ' output.txt | cut -d '=' -f2 | tr -d ' '",
        "r2": "grep 'r2 = ' output.txt | cut -d '=' -f2 | tr -d ' '"
    }
}

# Run fzd with custom expression combining r1 and r2
result = fz.fzd(
    input_path="input/",
    input_variables={"x": "[-2;2]", "y": "[-2;2]"},
    model=model_multi,
    output_expression="r1 + r2 * 2",  # Custom expression
    algorithm="examples/algorithms/randomsampling.py",
    algorithm_options={"nvalues": 10, "seed": 42}
)

print(f"Output expression: r1 + r2 * 2")
print(f"Total evaluations: {result['total_evaluations']}")

# Get best result
df = result['XY']
best_idx = df['r1 + r2 * 2'].idxmin()
print(f"\nBest result:")
print(f"  x = {df.loc[best_idx, 'x']:.6f}")
print(f"  y = {df.loc[best_idx, 'y']:.6f}")
print(f"  r1 = {df.loc[best_idx, 'r1']:.6f}")
print(f"  r2 = {df.loc[best_idx, 'r2']:.6f}")
print(f"  r1 + r2 * 2 = {df.loc[best_idx, 'r1 + r2 * 2']:.6f}")
```

### Available Expression Operators

The output expression supports:
- **Arithmetic:** `+`, `-`, `*`, `/`, `**` (power)
- **Functions:** `abs()`, `min()`, `max()`, `sqrt()`, `exp()`, `log()`, etc.
- **Math constants:** `pi`, `e`
- **Model outputs:** Any variable from `model["output"]`

### Example Expressions

```python
# Simple sum
output_expression = "output1 + output2"

# Weighted sum
output_expression = "0.7 * pressure + 0.3 * temperature"

# Constraint violation penalty
output_expression = "cost + 1000 * max(0, temperature - 100)"

# Root mean square
output_expression = "sqrt((x1**2 + x2**2 + x3**2) / 3)"

# Array indexing (for trajectory data)
output_expression = "res_x[-1]"  # Last element
```

---

## Complete Running Example

Here's a complete, self-contained example you can run:

```python
#!/usr/bin/env python3
"""Complete fzd example"""

import fz
import tempfile
import shutil
from pathlib import Path

# Create temporary directory
tmpdir = Path(tempfile.mkdtemp())

try:
    # Create input directory
    input_dir = tmpdir / "input"
    input_dir.mkdir()

    # Create input file
    (input_dir / "input.txt").write_text("x = $x\ny = $y\n")

    # Define model
    model = {
        "varprefix": "$",
        "delim": "()",
        "run": "bash -c 'source input.txt && result=$(echo \"scale=6; $x * $x + $y * $y\" | bc) && echo \"result = $result\" > output.txt'",
        "output": {
            "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
        }
    }

    # Run optimization
    result = fz.fzd(
        input_path=str(input_dir),
        input_variables={"x": "[-2;2]", "y": "[-2;2]"},
        model=model,
        output_expression="result",
        algorithm="examples/algorithms/randomsampling.py",
        algorithm_options={"nvalues": 10, "seed": 42}
    )

    # Display results
    print(f"Total evaluations: {result['total_evaluations']}")
    df = result['XY']
    best_idx = df['result'].idxmin()
    print(f"Best: x={df.loc[best_idx, 'x']:.4f}, y={df.loc[best_idx, 'y']:.4f}, result={df.loc[best_idx, 'result']:.6f}")

finally:
    shutil.rmtree(tmpdir)
```

---

## Algorithm Comparison

| Algorithm | Type | Dimensions | Evaluations | Best For |
|-----------|------|------------|-------------|----------|
| **Random Sampling** | Exploration | Any | High (10-100+) | Exploration, baselines |
| **Brent** | Optimization | 1D only | Low (5-15) | 1D root finding, precise 1D optim |
| **BFGS** | Optimization | 2-50 | Medium (10-30) | Smooth multi-D optimization |
| **Gradient Descent** | Optimization | Any | Medium (10-50) | Large-scale, simple implementation |
| **Monte Carlo** | Integration | Any | High (100-10000) | Uncertainty quantification |

---

## Tips and Best Practices

### 1. Choose the Right Algorithm

- **1D problems:** Use Brent's method
- **2-10D smooth problems:** Use BFGS
- **10-50D smooth problems:** Use gradient descent
- **Non-smooth or exploratory:** Use random sampling
- **Global optimization:** Combine random sampling → local optimization

### 2. Set Appropriate Tolerances

```python
# High precision (more evaluations)
algorithm_options={"tol": 1e-6, "max_iter": 100}

# Fast exploration (fewer evaluations)
algorithm_options={"tol": 1e-2, "max_iter": 20}
```

### 3. Use Fixed Variables

```python
# Optimize angle, keep velocity fixed
input_variables={
    "angle": "[20;80]",  # Variable (search range)
    "velocity": "45.0"    # Fixed value
}
```

### 4. Monitor Progress

All algorithms support `get_analysis_tmp()` for intermediate results:

```python
# Results saved after each iteration
# Check: analysis_dir/results_1.html, results_2.html, etc.
```

### 5. Combine Approaches

```python
# 1. Explore with random sampling
explore = fz.fzd(..., algorithm="randomsampling", nvalues=20)

# 2. Refine with BFGS starting near best point
# Use best result from exploration as initial guess
refine = fz.fzd(..., algorithm="bfgs", x0=best_from_explore)
```

---

## Troubleshooting

### Issue: Algorithm not found

```python
# ✗ Wrong
algorithm="bfgs"  # Looks for installed plugin

# ✓ Correct
algorithm="examples/algorithms/bfgs.py"  # Full path
```

### Issue: Output expression fails

Check available variables and use proper syntax:

```python
# See what's available
print(result['XY'].columns)

# Use correct variable names
output_expression="pressure"  # Must match model output key
```

### Issue: Slow convergence

Try adjusting algorithm parameters:

```python
# Increase step size (gradient descent)
algorithm_options={"step_size": 2.0}

# Relax tolerance
algorithm_options={"tol": 1e-3}
```

---

## See Also

- **FZ Documentation:** https://github.com/Funz/fz
- **Algorithm Development:** See `examples/algorithms/` for templates
- **Modelica Integration:** See `examples/fz_modelica_projectile.ipynb`
- **API Reference:** Run `python -c "import fz; help(fz.fzd)"`

---

## Summary

The `fzd()` function provides a unified interface for iterative design of experiments:

1. **Define your problem:** Input variables, model, output expression
2. **Choose an algorithm:** Based on problem type and dimensionality
3. **Set options:** Tolerance, iterations, algorithm-specific parameters
4. **Run optimization:** `fz.fzd()` handles the iterative sampling
5. **Analyze results:** DataFrame with all evaluations + algorithm analysis

**Key advantage:** Adaptive algorithms are 2-10× more efficient than grid search while achieving better precision!
