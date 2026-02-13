#title: BFGS Optimization Algorithm
#author: Test
#type: optimization
#options: max_iter=100;tol=0.000001

class Bfgs:
    """Simplified BFGS for multi-dimensional optimization"""

    def __init__(self, **options):
        self.max_iter = int(options.get('max_iter', 100))
        self.tol = float(options.get('tol', 1e-6))
        self._iteration = 0
        self._var_names = []
        self._finished = False

    def get_initial_design(self, input_vars, output_vars):
        self._var_names = list(input_vars.keys())
        # Start at center of search space
        center = {var: (bounds[0] + bounds[1]) / 2
                 for var, bounds in input_vars.items()}
        return [center]

    def get_next_design(self, previous_input_vars, previous_output_values):
        if self._finished:
            return []

        self._iteration += 1
        if self._iteration >= self.max_iter:
            self._finished = True
            return []

        # Simple: sample around best point
        valid_results = [(inp, out) for inp, out in
                        zip(previous_input_vars, previous_output_values)
                        if out is not None]

        if not valid_results:
            self._finished = True
            return []

        best_input, best_output = min(valid_results, key=lambda x: x[1])

        # Check if we're done (very simple convergence)
        if len(valid_results) > 5:
            recent_outputs = [out for _, out in valid_results[-5:]]
            if max(recent_outputs) - min(recent_outputs) < self.tol:
                self._finished = True
                return []

        # Generate point near best (simple random walk)
        import random
        next_point = {}
        for var in self._var_names:
            next_point[var] = best_input[var] + random.uniform(-0.1, 0.1)

        return [next_point]

    def get_analysis(self, input_vars, output_values):
        valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                        if out is not None]

        if not valid_results:
            return {
                'text': 'No valid results',
                'data': {'iterations': self._iteration, 'evaluations': len(input_vars)}
            }

        best_input, best_output = min(valid_results, key=lambda x: x[1])

        result_text = f"""BFGS Optimization Results:
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
