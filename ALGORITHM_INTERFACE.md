# fzd Algorithm Interface

This document clarifies the interface for custom algorithms used with `fzd`.

## Data Types

### Input Format (to algorithms)

- **`input_vars` in `get_initial_design()`**: `Dict[str, Tuple[float, float]]`
  - Format: `{"variable_name": (min_value, max_value)}`
  - Example: `{"x": (0.0, 1.0), "y": (-5.0, 5.0)}`

- **`previous_input_vars` in `get_next_design()` and `input_vars` in `get_analysis()`**: `List[Dict[str, float]]`
  - Format: List of dictionaries, each representing one evaluated point
  - Example: `[{"x": 0.5, "y": 0.3}, {"x": 0.7, "y": 0.2}, {"x": 0.1, "y": 0.9}]`

- **`previous_output_values` in `get_next_design()` and `output_values` in `get_analysis()`**: `List[float]`
  - Format: List of float values (may contain `None` for failed evaluations)
  - Example: `[1.5, 2.3, None, 0.8, 1.2]`

### Output Format (from algorithms)

- **Return value from `get_initial_design()` and `get_next_design()`**: `List[Dict[str, float]]`
  - Format: List of dictionaries, each representing a point to evaluate
  - Example: `[{"x": 0.5, "y": 0.3}, {"x": 0.7, "y": 0.2}]`
  - Return empty list `[]` when algorithm is finished

- **Return value from `get_analysis()`**: `Dict[str, Any]`
  - Must contain at least `'text'` and `'data'` keys
  - Example: `{'text': 'Best result: ...', 'data': {'best_input': {...}, 'best_output': 1.5}}`

## Working with Numpy Arrays

While the interface uses **Python lists**, algorithms can convert to numpy arrays internally for numerical computation:

```python
import numpy as np

def get_next_design(self, previous_input_vars, previous_output_values):
    # Convert outputs to numpy array (filter out None values)
    Y_valid = np.array([y for y in previous_output_values if y is not None])

    # Extract specific input variables to numpy arrays
    x_vals = np.array([inp['x'] for inp in previous_input_vars])
    y_vals = np.array([inp['y'] for inp in previous_input_vars])

    # Or convert all inputs to a 2D matrix (if all have same keys)
    # Get variable names
    var_names = list(previous_input_vars[0].keys())

    # Create 2D matrix: rows = points, columns = variables
    X_matrix = np.array([[inp[var] for var in var_names]
                         for inp in previous_input_vars])

    # Perform numerical computations
    mean = np.mean(Y_valid)
    std = np.std(Y_valid)
    # ...

    # Return results as list of dicts
    return [{"x": next_x, "y": next_y}]
```

## Complete Example

Here's a complete algorithm showing proper handling of data types:

```python
#title: Example Algorithm
#author: Your Name
#options: max_iter=100
#require: numpy;scipy

import numpy as np
from scipy import stats

class ExampleAlgorithm:
    def __init__(self, **options):
        self.max_iter = int(options.get('max_iter', 100))
        self.iteration = 0
        self.var_names = []

    def get_initial_design(self, input_vars, output_vars):
        """
        Args:
            input_vars: Dict[str, Tuple[float, float]]
                       e.g., {"x": (0.0, 1.0), "y": (-5.0, 5.0)}
            output_vars: List[str]
                        e.g., ["result"]

        Returns:
            List[Dict[str, float]]
            e.g., [{"x": 0.5, "y": 0.0}, {"x": 0.7, "y": 2.3}]
        """
        # Store variable names for later use
        self.var_names = list(input_vars.keys())

        # Generate initial points (center + corners)
        points = []

        # Center point
        center = {var: (bounds[0] + bounds[1]) / 2
                 for var, bounds in input_vars.items()}
        points.append(center)

        # Corner points (simplified - just 2 corners for demo)
        corner1 = {var: bounds[0] for var, bounds in input_vars.items()}
        corner2 = {var: bounds[1] for var, bounds in input_vars.items()}
        points.extend([corner1, corner2])

        return points

    def get_next_design(self, previous_input_vars, previous_output_values):
        """
        Args:
            previous_input_vars: List[Dict[str, float]]
                                e.g., [{"x": 0.5, "y": 0.3}, {"x": 0.7, "y": 0.2}]
            previous_output_values: List[float]
                                   e.g., [1.5, None, 2.3, 0.8]

        Returns:
            List[Dict[str, float]] or []
        """
        self.iteration += 1

        # Check termination
        if self.iteration >= self.max_iter:
            return []

        # Filter out None values and create valid dataset
        valid_data = [(inp, out)
                     for inp, out in zip(previous_input_vars, previous_output_values)
                     if out is not None]

        if len(valid_data) < 2:
            return []  # Not enough data

        # Separate inputs and outputs
        valid_inputs, valid_outputs = zip(*valid_data)

        # Convert to numpy for computation
        Y = np.array(valid_outputs)

        # Convert inputs to matrix form
        X = np.array([[inp[var] for var in self.var_names]
                     for inp in valid_inputs])

        # Find best point
        best_idx = np.argmin(Y)
        best_point = valid_inputs[best_idx]

        # Generate next point near the best one (simple random perturbation)
        next_point = {}
        for var in self.var_names:
            # Add small random perturbation
            next_point[var] = best_point[var] + np.random.normal(0, 0.1)

        return [next_point]

    def get_analysis(self, input_vars, output_values):
        """
        Args:
            input_vars: List[Dict[str, float]]
            output_values: List[float] (may contain None)

        Returns:
            Dict with 'text' and 'data' keys
        """
        # Filter out None values
        valid_data = [(inp, out)
                     for inp, out in zip(input_vars, output_values)
                     if out is not None]

        if not valid_data:
            return {
                'text': 'No valid results',
                'data': {'valid_samples': 0}
            }

        valid_inputs, valid_outputs = zip(*valid_data)
        Y = np.array(valid_outputs)

        # Find best
        best_idx = np.argmin(Y)
        best_input = valid_inputs[best_idx]
        best_output = Y[best_idx]

        # Compute statistics
        mean_output = np.mean(Y)
        std_output = np.std(Y)

        text = f"""Algorithm Results:
  Iterations: {self.iteration}
  Valid evaluations: {len(valid_data)}
  Best output: {best_output:.6f}
  Best input: {best_input}
  Mean output: {mean_output:.6f}
  Std output: {std_output:.6f}
"""

        return {
            'text': text,
            'data': {
                'iterations': self.iteration,
                'valid_samples': len(valid_data),
                'best_output': float(best_output),
                'best_input': best_input,
                'mean_output': float(mean_output),
                'std_output': float(std_output),
            }
        }
```

## Key Points

1. **Interface uses Python lists and dicts** - not numpy arrays directly
2. **Convert to numpy internally** when needed for numerical operations
3. **Handle None values** in `output_values` (failed evaluations)
4. **Return format must match** the expected types (list of dicts)
5. **Empty list `[]` signals completion** in `get_next_design()`

## Common Patterns

### Filtering None values
```python
valid_outputs = [y for y in output_values if y is not None]
valid_pairs = [(x, y) for x, y in zip(input_vars, output_values) if y is not None]
```

### Converting to numpy
```python
Y = np.array([y for y in output_values if y is not None])
X = np.array([[inp[var] for var in var_names] for inp in input_vars])
```

### Extracting specific variables
```python
x_values = [inp['x'] for inp in input_vars]
y_values = [inp['y'] for inp in input_vars]
```
