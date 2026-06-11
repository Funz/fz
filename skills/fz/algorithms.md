# Writing custom fzd algorithms

An fzd algorithm is a Python file containing one class that proposes points to evaluate,
receives results, and decides when to stop. Pass its path as `algorithm=` to `fz.fzd`
(or `--algorithm` on the CLI). Built-in examples live in `examples/algorithms/`
(`randomsampling.py`, `montecarlo_uniform.py`, `bfgs.py`, `brent.py`).

## File format

```python
#title: My Algorithm
#author: Name
#options: max_iter=100;tol=1e-6
#require: numpy;scipy

class MyAlgorithm:
    def __init__(self, **options):
        # options arrive as strings from #options defaults or user-provided
        # algorithm_options — cast them yourself
        self.max_iter = int(options.get("max_iter", 100))
        self.iteration = 0

    def get_initial_design(self, input_vars, output_vars):
        """First batch of points to evaluate.

        input_vars:  Dict[str, Tuple[float, float]] — {"x": (min, max), ...}
        output_vars: List[str] — output names, e.g. ["pressure"]
        returns:     List[Dict[str, float]] — points to evaluate
        """
        self.bounds = input_vars
        return [{v: (lo + hi) / 2 for v, (lo, hi) in input_vars.items()}]

    def get_next_design(self, previous_input_vars, previous_output_values):
        """Next batch, given all results so far.

        previous_input_vars:    List[Dict[str, float]] — all evaluated points
        previous_output_values: List[float] — corresponding outputs; None = failed case
        returns:                List[Dict[str, float]], or [] to stop
        """
        self.iteration += 1
        if self.iteration >= self.max_iter:
            return []
        ...
        return [next_point]

    def get_analysis(self, input_vars, output_values):
        """Final analysis once finished.

        returns: dict with at least "text" (human summary) and "data" (dict of values);
                 may include HTML/plot file paths.
        """
        best = min((y, x) for x, y in zip(input_vars, output_values) if y is not None)
        return {"text": f"best: {best}", "data": {"best_output": best[0],
                                                  "best_input": best[1]}}
```

## Rules

- The interface uses plain lists/dicts of floats, not numpy arrays — convert internally
  if needed: `X = np.array([[p[v] for v in var_names] for p in points])`.
- `previous_output_values` may contain `None` for failed cases — always filter:
  `valid = [(x, y) for x, y in zip(xs, ys) if y is not None]`.
- Returning `[]` from `get_next_design` ends the loop.
- Batches may contain several points: fz evaluates them in parallel on the available
  calculators and deduplicates repeated points automatically.
- fzd caches all evaluated points across iterations and re-runs, so proposing a
  previously seen point costs nothing.
