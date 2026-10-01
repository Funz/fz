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

Install: `pip install 'funz-fz>=1.2'` (CLI commands `fz`, `fzi`, `fzc`, `fzo`, `fzr`, `fzl`,
`fzd` plus the `fz` Python package). 1.2 is recommended — on top of the 1.1 fixes (`fzd`
on the CLI, calculator auto-discovery for `fzd`, directory-tree inputs staged intact) it
adds shell-free output extraction (`python://`/`jq://`/`yq://`/`xpath://`), vector outputs,
multi-objective `fzd`, shared `input_static` files, and configurable `case_naming`.
On PEP 668 externally-managed systems
(`error: externally-managed-environment`), use a venv:
`python3 -m venv .venv && .venv/bin/pip install 'funz-fz>=1.2'`.

## The workflow

Wrapping a simulation always follows the same steps. Do them in order and verify each one
before moving to the next — this isolates errors cheaply instead of debugging a full run.

0. **Check for an official wrapper**: `fz install model <code>` may give you steps 1–2
   for free.
1. **Parameterize the input file(s)**: replace numerical values with `$var` markers.
2. **Define the model**: a small dict/JSON saying how to recognize variables and how to
   parse outputs — only if step 0 found no wrapper.
3. **Verify parsing**: `fzi` must report exactly the variables you expect.
4. **Verify compilation**: `fzc` with one set of values; inspect the compiled file.
5. **Run one case manually**: execute the simulation command on the compiled file.
6. **Verify output parsing**: `fzo` on the directory containing the outputs.
7. **Run the study**: `fzr` with the full variable grid and calculator(s).

**Single file vs. a case directory.** `input_path` can be one file or a whole directory
tree. Codes like OpenFOAM or Telemac take a *case directory* (`system/`, `constant/`, `0/`,
…); point `input_path` at the directory, parameterize whichever file(s) hold the values,
and the calculator runs inside the per-case copy with the tree intact. Authoring such a
wrapper has extra gotchas (prefix collisions, directory I/O, locale) — see
[code-wrapper.md](code-wrapper.md). (Recursive staging of case subdirectories requires
fz ≥ 1.1; fz 1.0 stages only top-level files.)

### 0. Check for an existing wrapper first

Funz publishes ready-made wrappers for common simulation codes (Modelica, MORET, …) as
GitHub repos named `fz-<code>` under the Funz organization — browse
<https://github.com/orgs/Funz/repositories?q=fz-> for the list. Install one with:

```bash
fz install model modelica        # name → https://github.com/Funz/fz-modelica
fz list --check --format json    # verify what got installed
```

This drops into the project's `.fz/` directory (add `--global` for `~/.fz/`; the alias's
`.fz/...` script path is resolved against the `.fz/` it was loaded from, so a global
install works from any directory):

- `.fz/models/<Code>.json` — the model definition (variable syntax + output parsers);
  refer to it by bare alias, e.g. `--model Modelica`.
- `.fz/calculators/<Code>.sh` — a runner script that executes the simulation code.
- `.fz/calculators/localhost_<Code>.json` — a local calculator alias wired to that script.
  In both `fzr` and `fzd` (fz ≥ 1.1) it is auto-discovered: omit `calculators` and the
  installed alias matching the model id is used; `--calculators <alias>` also accepts a bare
  alias name. **On fz 1.0** neither held — bare alias names were rejected by `--calculators`
  and `fzd` did not auto-discover (omitting `calculators` ran an empty `sh://` and every
  case failed), so on 1.0 you must pass `fzd` calculators explicitly, e.g. a URI with an
  absolute script path: `calculators="sh://bash /abs/path/.fz/calculators/<Code>.sh"`
  (absolute, because calculator commands run inside each case directory).

With a wrapper installed, skip to step 1 just to add `$var` markers to your input file,
then verify with steps 3–6 as usual. Write a custom model (step 2) only when no wrapper
exists for your code — and if it should be reusable or published as `fz-<code>`, follow
[code-wrapper.md](code-wrapper.md).

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

Syntax (with the default model settings `varprefix="$"`, `formulaprefix="@"`,
`commentline="#"`, no `delim`):

- `$name` or `${name}` — a variable to substitute.
- `${name~default}` — variable with a default value used when not provided.
- `@{expr}` — a formula evaluated at compile time by the interpreter (Python by default,
  R optional). Formulas may reference variables: `@{$T_celsius + 273.15}`.
- Lines starting with `#@` (commentline + formulaprefix) define context for formulas:
  imports, constants, function definitions. Multi-line functions are supported.
- Without `"delim"` in the model, variables may be `$x`, `$(x)` or `${x}` and formulas
  `@{...}` (CLI and Python alike). Set `"delim"` when the code's own syntax contains
  `${...}`/`$(...)` text that must not be read as variables. `?name` is only a variable
  with `varprefix="?"` (no automatic conversion).

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

**Prefer shell-free native outputs** when authoring new models: values prefixed with
`python://` are evaluated as Python expressions in the result directory (no bash, no
locale or quoting pitfalls, portable to Windows). Helpers available: `read(path)`,
`lines(path)`, `line(path, n)`, `grep(pattern, path, all=False)` (returns first capture
group, cast to number when possible), `json_file(path)`, `csv_file(path, column=None)`,
`hdf5_file(path, dataset=None)` (optional `h5py` dependency), plus `re`, `json`,
`math`, `statistics`, `np`, `pd`, `Path`:

```python
"output": {
    "pressure": "python://grep(r'pressure = (\\S+)', 'output.txt')",
    "T_max":    "python://max(csv_file('temps.csv', column='T'))"
}
```

For JSON results, `jq://` filters are also shell-free-ish: they only require the `jq`
executable (no bash), e.g. `"pressure": "jq://.pressure output.json"`. Same idea for
YAML/JSON/XML/TOML with `yq://` (requires `yq`, mikefarah/yq), e.g.
`"version": "yq://.metadata.version config.yaml"`, and for XML with `xpath://`
(requires `xmllint`), e.g. `"pressure": "xpath://'//pressure/text()' output.xml"`.

From the Python API, an output value can also be a callable taking the result directory
as a `pathlib.Path`. Legacy shell-command strings remain fully supported (implicit
default, or explicit `bash://` prefix) and can be mixed with `python://`/`jq://` outputs
in the same model.

> **A model never says how to *run* the code.** It declares only the input syntax and the
> output parsers. *Where and how* the simulation executes is the calculator's job (see
> "Calculators" below). There is no `run` field in a model. If you forget the calculator,
> fz falls back to `sh://` and tries to execute the input file itself — the tell-tale
> symptom is `Permission denied ... ./input.txt`.

### 3–6. Verify each step before the full run

```bash
# 3. Variables found? (returns variables as keys, None values)
fzi --input_path input.txt --model perfectgas --format json
# Must list EXACTLY your variables. Stray names (e.g. the code's own $-macros) mean your
# varprefix collides with the code's syntax — change it (e.g. varprefix="%") and re-check.

# 4. Compilation correct for one case? fzc writes ONE SUB-DIRECTORY PER CASE, named
#    after the values (here compiled/n_mol=1,T_celsius=20,V_L=10/), even for scalars.
fzc --input_path input.txt --model perfectgas \
    --input_variables '{"n_mol": 1, "T_celsius": 20, "V_L": 10}' --output_dir compiled/
cat compiled/*/input.txt

# 5. Simulation runs on the compiled input? (run it inside the case sub-directory)
(cd compiled/*/ && bash /path/to/PerfectGazPressure.sh input.txt)

# 6. Outputs parse correctly? Point fzo at the case directory (or a glob), not its parent:
#    `fzo compiled/` returns a single row of nulls.
fzo --output_path 'compiled/*' --model perfectgas --format json
```

Also: if `compiled/` already exists, fz renames it with a timestamp suffix and writes a
fresh one — remove it between attempts to keep the glob unambiguous.

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
fzr --input_path input.txt --model perfectgas \
    --input_variables '{"T_celsius": [10, 20, 30, 40], "V_L": [1, 2, 5], "n_mol": 1.0}' \
    --calculators "sh://bash PerfectGazPressure.sh" \
    --results_dir results/ --format json
```

- A **dict** of lists ⇒ full factorial design (Cartesian product of all values).
- A **pandas DataFrame** ⇒ non-factorial: each row is one case (use for LHS designs,
  constrained combinations, or designs imported from CSV).
- Returns a DataFrame with one row per case: variable columns, output columns, and
  metadata columns `status` (`done`/`failed`/`error`/`timeout`/`interrupted`; a cache hit
  is `done` with a `cache://...` calculator; `done` with `None` outputs and
  `Missing output: ...` in `error` means the run ended but nothing was parsed),
  `calculator`, `error`, `command`.
- List-valued outputs (e.g. time series) become list columns — one whole trajectory per
  row. The Modelica wrapper, for instance, yields `res_<Model>_time`, `res_<Model>_T`, …
  per case; plot directly with
  `for _, row in results.iterrows(): plt.plot(row["res_M_time"], row["res_M_T"])`.
- Each case directory under `results/` keeps compiled inputs, outputs, `out.txt`,
  `err.txt`, `log.txt` — read these to diagnose failed cases. These names (plus
  `info.txt`, `history.txt`, `.fz_hash`) are **reserved**: a code output called
  `out.txt` is overwritten by the captured stdout. The results root also gets
  `manifest.json` (+ `ro-crate-metadata.json`) for traceability.
- Failed cases are retried automatically on another calculator (default 5 attempts,
  `FZ_MAX_RETRIES`).

## Calculators (where cases run)

Calculator URIs; pass one or a list. Each non-cache entry runs **one case at a time**, so
the number of entries is the number of parallel cases (`["sh://bash run.sh"] * 4` → 4):

| URI | Meaning |
|-----|---------|
| `sh://command` | Local shell, run in the case's temp directory; the compiled input file names are appended to the end of `command`. |
| `ssh://user[:password]@host[:port]/command` | Remote via SSH (files transferred automatically; prefer key auth; use absolute paths in `command`). No default timeout. |
| `slurm://[user@host[:port]]:partition/command` | SLURM via `srun` (local form: `slurm://:partition/...`); resources as `?cores=4&mem=8G&time=01:00:00`. No default timeout. |
| `slurm-array://:partition/command` | Local SLURM only: all cases batched into one sbatch job array (`?maxrunning=M` throttles). |
| `cache://path` | Reuse results from a previous results directory (match by input hash). Put it first in the list. |
| `funz://host:port/ModelName` | Legacy Java Funz server. |

> **`sh://` appends the input files to the whole command line.** `sh://cat input.txt >
> res.txt` runs `cat input.txt > res.txt input.txt`. Put any file handling in a script
> launched with `sh://bash run.sh`; inside it, relative paths are the case directory and
> `$1`… are the compiled input files. (Path resolution: see the tips below.)

Interrupt-and-resume / incremental extension of a study:

```bash
fzr --input_path input.txt --model m --input_variables '...' \
    --calculators '["cache://results_run1", "sh://bash calc.sh"]' \
    --results_dir results_run2/
# only cases absent from results_run1 are computed
```

To resume **in the same directory**, use the special entry `cache://_` (the previous
content of `--results_dir`, which fz renames with a timestamp before running):
`--calculators '["cache://_", "sh://bash calc.sh"]' --results_dir results/`.
`cache://results` with `--results_dir results` never hits.

Calculator aliases live in `.fz/calculators/<name>.json` with the command per model id:
`{"uri": "ssh://user@cluster", "models": {"perfectgas": "bash /path/calc.sh"}}`.
Run `fz list --check --format json` (alias `fzl`) to list and validate installed
models/calculators — prefer the `fz <subcommand>` forms, which survive stale or
partially-installed standalone scripts.
`fz list` shows calculator aliases by file name with their `uri`, and `--check` validates
each command of an alias's `models` map.

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

Like model wrappers, **algorithms can be installed** from the Funz GitHub organization —
prefer this over writing one when the question goes beyond a plain sweep (optimization,
calibration/inversion, uncertainty propagation, sensitivity analysis, adaptive sampling):

```bash
fz install algorithm brent        # name → https://github.com/Funz/fz-brent
```

Algorithm repos share the `fz-<name>` naming with model wrappers — browse
<https://github.com/orgs/Funz/repositories?q=fz-> for both (as of 2026-06: `fz-brent`,
`fz-gradientdescent`, `fz-PSO`; the `algorithm-*` repos are legacy Java-Funz). The fz repo
itself also ships ready-to-use algorithms in `examples/algorithms/` (`montecarlo_uniform`,
`randomsampling`, `bfgs`, `brent`) — copy one into `.fz/algorithms/`:

```bash
curl -s https://raw.githubusercontent.com/Funz/fz/main/examples/algorithms/montecarlo_uniform.py \
  -o .fz/algorithms/montecarlo_uniform.py
```

Installed algorithms land in `.fz/algorithms/` (`--global` for `~/.fz/`) and are referenced
by bare name (or glob): `algorithm="montecarlo_uniform"`. Check the `#options:` and
`#require:` header lines of the algorithm file for its options and Python dependencies
(e.g. montecarlo_uniform needs scipy).

Points already evaluated are cached across iterations and across re-runs. To write a custom
algorithm (a Python class with `get_initial_design` / `get_next_design` / `get_analysis`),
read [algorithm-wrapper.md](algorithm-wrapper.md).

## Tips for agents

- Always prefer `--format json` (or `csv`) on CLI commands for parseable output; default
  output is a human table. Data goes to stdout; logs, progress, and errors go to stderr.
  Exit codes are non-zero on errors, and `fzr` exits 1 when no case succeeded.
- Models, calculators (`sh://`, `ssh://` commands, `version_cmd`) and `output` commands are
  **executed code with the user's privileges**: never run an alias or model of unknown origin
  (`fz install <url>` prints a reminder). See "Threat Model" in the README.
- In an `sh://` command, a bare word (`script.sh`, `data.txt`) is turned into an absolute path
  in the launch directory **only if it exists there and not in the case directory** (compiled
  inputs win). Redirection targets (`> out.txt`) always stay in the case directory. A helper
  script that lives only next to the caller works (`sh://bash calc.sh`); anything the code
  reads or writes per case must be a bare name in the case directory. Earlier versions could
  silently read the un-substituted template from the launch directory (see NEWS.md, P0-8).
- fz requires bash: native on Linux/macOS; MSYS2/Git Bash on Windows (`FZ_SHELL_PATH`).
- Installed wrappers may invoke `python` (not `python3`) in their `output` commands and
  import pandas — if output parsing returns nothing, run fz with a suitable interpreter
  first on PATH: `PATH=$PWD/.venv/bin:$PATH fz output ...` (same for `fzr`).
- In `output` parsing commands, awk field references like `$3` must survive shell quoting:
  in JSON model files write them normally; inside a single-quoted inline `--model` JSON
  argument they are safe as-is, but never wrap them in double quotes on the shell.
- Make numeric `output` commands **locale-independent**: prefix with `LC_ALL=C`. On a
  non-English locale, tools like `sort -g` use a comma decimal and silently mis-order
  period/scientific-notation values (returning a wrong "max"); computing min/max in `awk`
  (one pass) is more robust than `sort | head/tail`.
- `fzr` argument order in Python is `(input_path, input_variables, model, results_dir=...,
  calculators=...)` — use keyword arguments to stay safe. `input_variables` (and `fzc`'s)
  default to `None`: for a non-parametric dataset (no variables in the input files) call
  `fzr(input_path, model=model, ...)` and omit it; if the input files do declare variables
  and it's omitted, fz raises a `ValueError` naming them.
- Concurrency: repeat the same calculator URI N times to run N cases in parallel.
  `FZ_MAX_WORKERS` only caps the worker count; it never adds workers.
- `FZ_*` environment variables are read at `import fz`: set them before starting Python,
  or call `fz.reload_config()` after changing `os.environ`.
- Timeouts: default 3600 s for `sh://`/`funz://`, none for `ssh://`/`slurm://`. `0` means
  no timeout (`timeout=0`, model `"timeout": 0`/`null`, `FZ_RUN_TIMEOUT=0`).
- Long studies: run `fzr` in the background, then monitor `results/*/log.txt` and the
  per-case `out.txt`/`err.txt`; on interrupt, partial results survive and `cache://` resumes.
- Full API and CLI details, environment variables, and the model/calculator JSON schemas:
  see [reference.md](reference.md).

## Common failures (read err.txt/log.txt in the case dir first)

| Symptom | Likely cause |
|---------|--------------|
| `Permission denied ... ./input.txt` | No calculator given; fz tried to execute the input. Add a calculator (`sh://bash runner.sh`). |
| All cases `failed`, `N calculator failures` | The calculator command itself errors — read the case's `err.txt`/`log.txt`. |
| Output column is `null` but case is `done` | Output command matched nothing: wrong path/field, missing subdir output (see directory codes), locale (`LC_ALL=C`), or `python` vs `python3`. |
| `fzi` lists extra/unexpected variables | `varprefix` collides with the code's own syntax — change it. |
| `ValueError: results_dir looks like a calculator URI` | Calculator URI passed as 4th positional arg of `fz.fzr` (that slot is `results_dir`) — use `calculators=`. |
| Output column holds the program's stdout instead of a file's content | The code writes a reserved name (`out.txt`, `err.txt`, `log.txt`, ...) that fz overwrites — rename it. |
| Case `done` but outputs `None`, `error` = `Missing output: ...` | No declared output could be parsed: wrong file name/pattern, output written elsewhere, or a reserved file name. |
| Output file holds its content twice / odd arguments | The compiled input names are appended to the end of the `sh://` command line — move the logic into a script. |
| `fzd` runs an empty `sh://` / every case fails | fz 1.0 only: `fzd` didn't auto-discover calculators — pass them explicitly, or upgrade to fz ≥ 1.1. |

## Worked examples

Two end-to-end walkthroughs (natural-language ask + the path the agent follows, with
checkable outcomes), one per archetype:

- [../examples/newton-cooling-calibration.md](../examples/newton-cooling-calibration.md) —
  **reuse ready-made packages**: discover the Modelica wrapper + brent algorithm to solve
  an inverse problem.
- [../examples/openfoam-dambreak-random-sampling.md](../examples/openfoam-dambreak-random-sampling.md) —
  **build from scratch**: author an OpenFOAM (directory-case) wrapper and a custom
  random-sampling algorithm when no `fz-*` package exists.
