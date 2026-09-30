# Writing Custom Algorithms for fzd

<!-- counterpart-note -->
> Guide page (from the former README). Reference counterpart in `doc/`: [`fzd_content_format.md`](../fzd_content_format.md). When behaviour changes, update both.


FZ provides an extensible framework for implementing adaptive algorithms. Each algorithm is a Python class with specific methods.

## Algorithm Interface

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

## Algorithm Examples

### 1. Monte Carlo Sampling

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

### 2. BFGS Optimization

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

### 3. Brent's Method (1D Optimization)

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

## Algorithm Features

### Content Format Detection

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

See `doc/fzd_content_format.md` for detailed format documentation.

### Dependency Management

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
