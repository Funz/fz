---
name: fz
description: >-
  Run parametric simulation studies with the fz Python package (Funz). Use when
  the user wants to wrap a simulation code to run parameter sweeps, sensitivity
  studies, design of experiments, or optimization over input files; when they
  mention fz, Funz, or the fzi/fzc/fzo/fzr/fzl/fzd commands; or when they need
  to run many cases of a computation locally, over SSH, or on SLURM and collect
  results into a DataFrame.
license: BSD-3-Clause
metadata:
  source: https://github.com/Funz/fz
---

# fz — parametric scientific computing

fz wraps any simulation code that reads input files and writes output files, so it can be
run as a parametric study: variables in input files are substituted for each case, cases run
in parallel (locally, SSH, SLURM), and outputs are parsed back into a pandas DataFrame.

Install: `pip install funz-fz` (CLI commands `fz`, `fzi`, `fzc`, `fzo`, `fzr`, `fzl`, `fzd`
plus the `fz` Python package).

## The workflow

Wrapping a simulation always follows the same steps. Do them in order and verify each one
before moving to the next — this isolates errors cheaply instead of debugging a full run.

1. **Parameterize the input file(s)**: replace numerical values with `$var` markers.
2. **Define the model**: a small dict/JSON saying how to recognize variables and how to
   parse outputs.
3. **Verify parsing**: `fzi` must report exactly the variables you expect.
4. **Verify compilation**: `fzc` with one set of values; inspect the compiled file.
5. **Run one case manually**: execute the simulation command on the compiled file.
6. **Verify output parsing**: `fzo` on the directory containing the outputs.
7. **Run the study**: `fzr` with the full variable grid and calculator(s).

### 1. Parameterize input files

In any text input file, mark values to vary with the variable prefix (default `$`):

```text
# input file for Perfect Gas Pressure
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@{L_to_m3($V_L)}
```

Syntax (with default model settings `varprefix="$"`, `formulaprefix="@"`, `delim="{}"`,
`commentline="#"`):

- `$name` or `${name}` — a variable to substitute.
- `${name~default}` — variable with a default value used when not provided.
- `@{expr}` — a formula evaluated at compile time by the interpreter (Python by default,
  R optional). Formulas may reference variables: `@{$T_celsius + 273.15}`.
- Lines starting with `#@` (commentline + formulaprefix) define context for formulas:
  imports, constants, function definitions. Multi-line functions are supported.
- Legacy Java-Funz `?name` syntax is accepted transparently.

If `$`, `@`, `{}`, or `#` collide with the simulation code's own syntax, change them in the
model (e.g. `varprefix="%"`, `commentline="//"`).

### 2. Define the model

A model is a dict (Python) or JSON file describing the parameterization syntax and how to
extract each output of interest with a shell command run inside each case's result directory:

```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    },
    "id": "perfectgas"   # optional; links the model to calculator aliases
}
```

Output command results are auto-cast to Python literals (int, float, list, dict) when
possible. For reusability, save as `.fz/models/perfectgas.json` (project) or
`~/.fz/models/perfectgas.json` (global) and refer to it by alias: `model="perfectgas"`.

### 3–6. Verify each step before the full run

```bash
# 3. Variables found? (returns variables as keys, None values)
fzi input.txt --model perfectgas --format json

# 4. Compilation correct for one case?
fzc input.txt --model perfectgas \
    --variables '{"n_mol": 1, "T_celsius": 20, "V_L": 10}' --output compiled/
cat compiled/input.txt

# 5. Simulation runs on the compiled input?
(cd compiled && bash /path/to/PerfectGazPressure.sh input.txt)

# 6. Outputs parse correctly?
fzo compiled/ --model perfectgas --format json
```

Python equivalents: `fz.fzi(input_path, model)`, `fz.fzc(input_path, input_variables,
model, output_dir)`, `fz.fzo(output_path, model)`.

### 7. Run the parametric study

```python
import fz

results = fz.fzr(
    "input.txt",
    {"T_celsius": [10, 20, 30, 40], "V_L": [1, 2, 5], "n_mol": 1.0},  # 4×3 = 12 cases
    model,                                  # dict, alias, or path to JSON
    results_dir="results",
    calculators="sh://bash PerfectGazPressure.sh",
)
```

```bash
fzr input.txt --model perfectgas \
    --variables '{"T_celsius": [10, 20, 30, 40], "V_L": [1, 2, 5], "n_mol": 1.0}' \
    --calculator "sh://bash PerfectGazPressure.sh" \
    --results results/ --format json
```

- A **dict** of lists ⇒ full factorial design (Cartesian product of all values).
- A **pandas DataFrame** ⇒ non-factorial: each row is one case (use for LHS designs,
  constrained combinations, or designs imported from CSV).
- Returns a DataFrame with one row per case: variable columns, output columns, and
  metadata columns `status` (`done`/`error`/`cached`), `calculator`, `error`, `command`.
- Each case directory under `results/` keeps compiled inputs, outputs, `out.txt`,
  `err.txt`, `log.txt` — read these to diagnose failed cases.
- Failed cases are retried automatically on another calculator (default 5 attempts,
  `FZ_MAX_RETRIES`).

## Calculators (where cases run)

Calculator URIs; pass one or a list (a list runs cases in parallel, round-robin):

| URI | Meaning |
|-----|---------|
| `sh://command` | Local shell. `command` gets the compiled input file as first argument. |
| `ssh://user[:password]@host[:port]/command` | Remote via SSH (files transferred automatically; prefer key auth; use absolute paths in `command`). |
| `slurm://[user@host[:port]]:partition/command` | SLURM via `srun` (local form: `slurm://:partition/...`). |
| `cache://path` | Reuse results from a previous results directory (match by input hash). Put it first in the list. |
| `funz://host:port/ModelName` | Legacy Java Funz server. |

Interrupt-and-resume / incremental extension of a study:

```bash
fzr input.txt --model m --variables '...' \
    --calculator "cache://results_run1" \
    --calculator "sh://bash calc.sh" \
    --results results_run2/
# only cases absent from results_run1 are computed
```

Calculator aliases live in `.fz/calculators/<name>.json` with the command per model id:
`{"uri": "ssh://user@cluster", "models": {"perfectgas": "bash /path/calc.sh"}}`.
Run `fzl --check --format json` to list and validate installed models/calculators.

## Design of experiments / optimization (fzd)

When values should be chosen adaptively by an algorithm instead of a fixed grid:

```python
results = fz.fzd(
    "input.txt",
    {"T_celsius": "[10;50]", "V_L": "[1;10]", "n_mol": "1"},  # "[min;max]" = varied, "value" = fixed
    model,
    output_expression="pressure",            # any expression of the outputs
    algorithm="examples/algorithms/bfgs.py", # or randomsampling, montecarlo_uniform, brent...
    calculators="sh://bash PerfectGazPressure.sh",
    algorithm_options={"max_iterations": 50},
    analysis_dir="results_fzd",
)
results["XY"]       # DataFrame of all evaluated points
results["summary"]  # text summary (e.g. optimum found)
```

Points already evaluated are cached across iterations and across re-runs. To write a custom
algorithm (a Python class with `get_initial_design` / `get_next_design` / `get_analysis`),
read [algorithms.md](algorithms.md).

## Tips for agents

- Always prefer `--format json` (or `csv`) on CLI commands for parseable output; default
  output is a human table. Data goes to stdout; logs, progress, and errors go to stderr.
  Exit codes are non-zero on errors, and `fzr` exits 1 when no case succeeded.
- fz requires bash: native on Linux/macOS; MSYS2/Git Bash on Windows (`FZ_SHELL_PATH`).
- In `output` parsing commands, awk field references like `$3` must survive shell quoting:
  in JSON model files write them normally; in inline `--output-cmd` arguments escape as `\$3`.
- `fzr` argument order in Python is `(input_path, input_variables, model, results_dir=...,
  calculators=...)` — use keyword arguments to stay safe.
- Concurrency: repeat the same calculator URI N times (or set `FZ_MAX_WORKERS`) to run N
  cases in parallel.
- Long studies: run `fzr` in the background, then monitor `results/*/log.txt` and the
  per-case `out.txt`/`err.txt`; on interrupt, partial results survive and `cache://` resumes.
- Full API and CLI details, environment variables, and the model/calculator JSON schemas:
  see [reference.md](reference.md).
