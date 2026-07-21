# Vector (array) outputs with fzr and fzo

Simulation outputs are not always a single number: a time series, a spatial
profile, per-node results, a spectrum... fz already lets an `output` entry
evaluate to a Python **list** instead of a scalar. This example shows the
supported ways to produce a vector output, and how it flows through `fzr`
(one full list per case, in one DataFrame cell) and `fzo` (reading the same
results back).

`fzd` (design of experiments / optimization) still expects a single scalar
objective per case for now — vector output support there is a separate,
follow-up piece of work.

## The toy model

A "simulation" that prints an exponential decay time series to `series.json`,
run for `n_steps` steps starting at `T0`:

```python
import os

# input.txt and run_case.sh live side by side in the working directory fzr
# is called from -- the same layout used throughout fz's own examples/tests.
with open("input.txt", "w") as f:
    f.write("n_steps=${n_steps}\nT0=${T0}\n")

with open("run_case.sh", "w", newline="\n") as f:
    f.write("#!/bin/bash\n")
    f.write("source input.txt\n")
    f.write(
        "python3 -c \"\n"
        "import json\n"
        "n = int($n_steps)\n"
        "T0 = float($T0)\n"
        "series = [round(T0 * (0.9 ** i), 3) for i in range(n)]\n"
        "print(json.dumps(series))\n"
        "with open(\'series.txt\', \'w\') as fh:\n"
        "    fh.write(chr(10).join(str(v) for v in series))\n"
        "\" > series.json\n"
    )
os.chmod("run_case.sh", 0o755)
```

## Four ways to extract the same vector

```python
model_python_json = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        # Whole JSON array file -> plain Python list, no shell involved
        "T_series": "python://json_file('series.json')",
    },
}

model_python_grep_all = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        # One value per line in series.txt -> list, via grep(..., all=True)
        "T_series": "python://grep(r'(\\S+)', 'series.txt', all=True)",
    },
}

model_jq = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        # jq filter selecting the whole array (requires the jq executable)
        "T_series": "jq://. series.json",
    },
}

model_bash = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        # Legacy shell command: cast_output() parses JSON arrays too
        "T_series": "cat series.json",
    },
}
```

All four are equivalent for this file, and all four return `T_series` as a
Python list — pick whichever matches the rest of your output-extraction
tooling (`csv_file(path, column=...)` and `hdf5_file(path, dataset=...)` work
the same way for CSV/HDF5 vector results, and `xpath://` returns a list when
the expression matches more than one XML node).

## Running fzr across several cases

```python
import fz

result = fz.fzr(
    "input.txt",
    {"n_steps": 5, "T0": [50.0, 100.0, 200.0]},   # 3 cases
    model_python_json,
    calculators="sh://bash run_case.sh",
    results_dir="vector_demo_results",
)

for i in range(len(result)):
    print(result["T0"].iloc[i], "->", result["T_series"].iloc[i])
# 50.0  -> [50.0, 45.0, 40.5, 36.45, 32.805]
# 100.0 -> [100.0, 90.0, 81.0, 72.9, 65.61]
# 200.0 -> [200.0, 180.0, 162.0, 145.8, 131.22]
```

Each `T_series` cell holds the *full* list for that case — `fzr` does not
flatten, truncate or otherwise reshape vector outputs. Cases are free to
produce vectors of different lengths (e.g. an iterative solver that
converges after a variable number of steps); each row simply keeps its own
list, no padding is applied.

## Reading the same results back with fzo

```python
fzo_result = fz.fzo("vector_demo_results/*", model_python_json)

# fzo() and fzr() may not list cases in the same order (fzo() sorts by
# matched directory), so compare per case via the T0 column rather than
# raw row position.
by_t0 = dict(zip(result["T0"], result["T_series"]))
fzo_by_t0 = dict(zip(fzo_result["T0"], fzo_result["T_series"]))
assert by_t0 == fzo_by_t0
```

## A note on single-element vectors

The legacy plain-shell-command form (no `python://`/`jq://`/`yq://`/`xpath://`
prefix) applies a backward-compatible simplification: a single-element JSON
array is unwrapped to its scalar element (`"echo '[42]'"` -> `42`, not
`[42]`). This can silently turn one row of a vector-output column into a bare
scalar if that particular case happens to produce a length-1 result. The
`python://`, `jq://`, `yq://` and `xpath://` forms never do this: a
single-element result stays a one-element list. Prefer one of those forms
when a vector output's length can legitimately be 1.

## Persisting results with vectors

`fzr`/`fzo` results are plain pandas DataFrames, so list-valued cells behave
like any other Python object column:

- `results.to_dict(orient="records")` / `json.dumps(..., default=str)` (or
  the CLI's `--format json`) round-trip vectors as native JSON arrays.
- `results.to_csv(...)` (or `--format csv`) stringifies each list
  (`"[1, 2, 3]"`); reload with `ast.literal_eval` or `json.loads` per cell,
  or prefer `to_pickle`/`to_parquet` for a lossless round trip.
