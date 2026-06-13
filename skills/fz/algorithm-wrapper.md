# Writing and packaging fzd algorithms

An fzd algorithm is a Python (or R) file containing one class that proposes points to
evaluate, receives results, and decides when to stop. Pass its path as `algorithm=` to
`fz.fzd` (or `--algorithm` on the CLI). Built-in examples live in `examples/algorithms/`
(`randomsampling.py`, `montecarlo_uniform.py`, `bfgs.py`, `brent.py`).

This is the algorithm analog of [code-wrapper.md](code-wrapper.md): the two kinds of
reusable, installable `fz-<name>` packages are **code wrappers** (bind a simulation code)
and **algorithm packages** (a `fzd` design-of-experiments / optimization strategy). This
guide covers both writing one (below) and publishing it (last two sections).

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

## Metadata headers

The leading `#key: value` comment lines (before the first code line) are parsed by fz:

- **`#title`** / **`#author`** — descriptive metadata, shown when listing algorithms.
- **`#options: key=value;key2=value2`** — default constructor options. They arrive in
  `__init__(**options)` as **strings** (cast them yourself). A user overrides any of them
  via `algorithm_options=` on `fz.fzd` (`--options '{"max_iter": 50}'` / `-o` on the CLI,
  taking inline JSON or a JSON file path).
- **`#require: pkg1;pkg2`** — Python packages the algorithm imports. On load, fz imports
  each and, **if missing, pip-installs it automatically** into the current environment.
  List only what you actually need, and prefer widely available packages.

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

## Packaging as an installable `fz-<name>` algorithm

To make an algorithm installable with `fz install algorithm <name>`, ship it in a GitHub
repo named `fz-<name>` (lowercase) with the file under `.fz/algorithms/`:

```
fz-myalgo/                         # GitHub repo named fz-<name>
├── .fz/
│   └── algorithms/
│       └── myalgo.py             # the algorithm file (or .R)
├── tests/                        # recommended: a tiny end-to-end fzd case
└── README.md
```

- A bare name resolves to `https://github.com/Funz/fz-<name>` (official algorithms live
  under the Funz organization); any git URL or local zip also works.
- On install, the file lands in the project's `./.fz/algorithms/` (or, with `--global`,
  `~/.fz/algorithms/`). `fzd` then accepts `--algorithm myalgo` without a full path.
- Both `.py` and `.R` algorithm files are supported (the installer globs
  `.fz/algorithms/*.py` and `*.R`).

## Test it like a user would

From a scratch directory, install and run a known problem whose answer you can check:

```bash
fz install algorithm ./fz-myalgo.zip     # or the repo path / URL
fz list                                   # algorithm available?

# drive it through fzd on a simple input (see code-wrapper.md for wrapping the code)
fzd --input_path tests/input.txt --model MyCode \
    --input_variables '{"x": "[0;10]"}' --output_expression "result" \
    --algorithm myalgo --options '{"max_iter": 20}' --format json
```

Ship that as `tests/test.sh` in the repo. Publish conventions match code wrappers: repo
named `fz-<name>`, default branch `main` (the installer fetches
`archive/refs/heads/main.zip`), and a README stating the options, what the algorithm
optimizes/samples, and a copy-paste quickstart. See [code-wrapper.md](code-wrapper.md)
for the shared `fz-<X>` packaging conventions.
