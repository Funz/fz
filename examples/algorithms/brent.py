#title: Brent's Method for 1D Optimization
#author: Test
#type: optimization
#options: max_iter=50;tol=0.00001;initial_points=3

import math

class Brent:
    """Brent's method for 1D optimization"""

    def __init__(self, **options):
        self.max_iter = int(options.get('max_iter', 50))
        self.tol = float(options.get('tol', 1e-5))
        self.initial_points = int(options.get('initial_points', 3))
        self.golden_ratio = (3.0 - math.sqrt(5.0)) / 2.0
        self._iteration = 0
        self._input_var_name = None
        self._var_bounds = None
        self._evaluated_points = []
        self._finished = False

    def get_initial_design(self, input_vars, output_vars):
        if len(input_vars) != 1:
            raise ValueError(
                f"Brent's method only works for 1D optimization. "
                f"Got {len(input_vars)} variables: {list(input_vars.keys())}"
            )

        self._input_var_name = list(input_vars.keys())[0]
        self._var_bounds = input_vars[self._input_var_name]
        min_val, max_val = self._var_bounds

        points = []
        for i in range(self.initial_points):
            x = min_val + (max_val - min_val) * i / (self.initial_points - 1)
            points.append({self._input_var_name: x})
        return points

    def get_next_design(self, previous_input_vars, previous_output_values):
        if self._finished:
            return []

        # Add new results
        for inp, out in zip(previous_input_vars, previous_output_values):
            if out is not None:
                x = inp[self._input_var_name]
                self._evaluated_points.append((x, out))

        if len(self._evaluated_points) < self.initial_points:
            return []

        self._evaluated_points.sort(key=lambda p: p[0])

        self._iteration += 1
        if self._iteration >= self.max_iter:
            self._finished = True
            return []

        # Find best three consecutive points
        best_idx = min(range(len(self._evaluated_points)),
                      key=lambda i: self._evaluated_points[i][1])

        # Simple convergence check
        if best_idx > 0 and best_idx < len(self._evaluated_points) - 1:
            a_x = self._evaluated_points[best_idx - 1][0]
            c_x = self._evaluated_points[best_idx + 1][0]
            if abs(c_x - a_x) < self.tol:
                self._finished = True
                return []

        # Golden section search
        min_val, max_val = self._var_bounds
        x_vals = [x for x, f in self._evaluated_points]

        # Find largest gap
        all_x = sorted([min_val] + x_vals + [max_val])
        max_gap = 0
        max_gap_mid = None
        for i in range(len(all_x) - 1):
            gap = all_x[i + 1] - all_x[i]
            if gap > max_gap:
                max_gap = gap
                max_gap_mid = (all_x[i] + all_x[i + 1]) / 2.0

        if max_gap < self.tol or max_gap_mid is None:
            self._finished = True
            return []

        return [{self._input_var_name: max_gap_mid}]

    def get_analysis(self, input_vars, output_values):
        valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                        if out is not None]

        if not valid_results:
            return {
                'text': 'No valid results',
                'data': {'iterations': self._iteration, 'evaluations': len(input_vars)}
            }

        best_input, best_output = min(valid_results, key=lambda x: x[1])

        result_text = f"""Brent Optimization Results:
  Iterations: {self._iteration}
  Function evaluations: {len(valid_results)}
  Optimal output: {best_output:.6g}
  Optimal input: {best_input}
  Convergence: {'Yes' if self._finished else 'No (max iterations)'}
"""

        return {
            'text': result_text,
            'data': {
                'iterations': self._iteration,
                'evaluations': len(valid_results),
                'optimal_output': best_output,
                'optimal_input': best_input,
                'converged': self._finished,
            }
        }
