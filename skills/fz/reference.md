# fz reference

Condensed reference for the fz Python API, CLI, file formats, and configuration.
Workflow guidance is in [SKILL.md](SKILL.md).

## Python API

```python
import fz
```

### fz.fzi — parse input, discover variables

```python
fz.fzi(input_path: str, model: str | dict) -> dict
```

Returns a dict whose keys are the variables, formulas, and static objects found in
`input_path` (file or directory); variable values are `None` (or their `~default`).

### fz.fzc — compile input files

```python
fz.fzc(input_path: str, input_variables: dict, model: str | dict,
       output_dir: str = "output") -> None
```

Substitutes variables and evaluates formulas. Scalar values produce a single compiled
copy in `output_dir/`; list values produce one subdirectory per combination, named
`var1=val1,var2=val2,...`.

### fz.fzo — parse output files

```python
fz.fzo(output_path: str, model: str | dict) -> pandas.DataFrame
```

Runs each `model["output"]` command in every directory matched by `output_path` (plain
path or glob like `results/*`). Returns one row per directory. Directory names following
`key=val,key=val` are parsed back into variable columns. Results are auto-cast (int,
float, list, dict) when possible. An output entry may resolve to a **list** (vector
output: time series, per-node profile, ...) via `python://grep(..., all=True)`,
`csv_file(column=...)`, `hdf5_file(dataset=...)`, `jq://`/`yq://` filters selecting an
array, `xpath://` matching several nodes, or a plain shell command printing a JSON
array; `fzr`/`fzo` store the full list per case, unmodified (cases may have
different-length vectors). Note: the plain-shell-command form still simplifies a
single-element array to its scalar (`echo '[42]'` → `42`) for backward compatibility;
the other forms never do.

### fz.fzr — run a parametric study

```python
fz.fzr(input_path: str,
       input_variables: dict | pandas.DataFrame,
       model: str | dict,
       results_dir: str = "results",
       calculators: str | list[str] = None,   # default "sh://"
       callbacks: dict = None,
       timeout: int = None) -> pandas.DataFrame
```

- dict `input_variables` ⇒ factorial (Cartesian product); DataFrame ⇒ one case per row.
- Returns a DataFrame: variable columns + output columns + `status` ("done", "error",
  "cached"), `calculator`, `error`, `command`.
- `callbacks` supports `on_start(total_cases, calculators)`, plus per-case progress
  callbacks (see docstring of `fz.fzr`).
- Ctrl+C interrupts gracefully; completed cases stay in `results_dir` and can be reused
  with a `cache://results_dir` calculator.

### fz.fzd — adaptive design of experiments

```python
fz.fzd(input_path: str | None,
       input_variables: dict[str, str],     # "[min;max]" varied, "value" fixed
       model: str | dict | Callable,
       output_expression: str | None,       # e.g. "pressure" or "out1 + 2*out2"
       algorithm: str,                      # name or path to .py algorithm
       calculators: str | list[str] | int = None,
       algorithm_options: dict | str = None,  # dict, JSON string, or JSON file path
       analysis_dir: str = "analysis") -> dict   # CLI default: results_fzd
```

Returns `{"XY": DataFrame, "analysis": ..., "iterations": int,
"total_evaluations": int, "summary": str}`. Duplicate points within a batch are
deduplicated; previously evaluated points are cached across iterations and re-runs.

**Direct Python function model** (Python API only, no CLI equivalent): pass a
callable as `model` instead of a dict/alias. Then `input_path` must be `None`;
`input_variables` keys must match the function's parameters; `output_expression`
may be `None` (defaults to the first value of the function's return — scalar,
first list/tuple item, or first dict/namedtuple key); `calculators` must be an
`int` (default `1`), accepted for API compatibility — calls always run
sequentially in-process, never in parallel, so the model function is safe to
call even if it's only usable from the calling thread (e.g. an R function
bridged in via reticulate). Each iteration's directory then contains
only a `values.csv` of that iteration's function inputs/outputs (no case dirs).

### fz.fzl — list and validate models/calculators

```python
fz.fzl(models: str = "*", calculators: str = "*", check: bool = False) -> dict
```

### Configuration helpers

```python
fz.set_interpreter("R")        # formula interpreter: "python" (default) or "R"
```

## CLI

Every Python function has a CLI twin: `fzi`, `fzc`, `fzo`, `fzr`, `fzl`, `fzd`
(also available as subcommands: `fz run ...`, `fz design ...`). `fz install model|algorithm
<name|git-url>` installs aliases into `.fz/` (`--global` for `~/.fz/`): a bare name resolves
to `https://github.com/Funz/fz-<name>` (official wrappers, e.g. `fz-modelica`; browse
<https://github.com/orgs/Funz/repositories?q=fz->), and the install provides the model JSON
plus calculator script/alias. `fz uninstall model|algorithm <name>` removes them.

Flags per command:

```
fzi  [input_path]  --input_path/-i  --model/-m  --format/-f
fzc  [input_path]  --input_path/-i  --model/-m  --input_variables/-v  --output_dir/-o
fzo  [output_path] --output_path/-o --model/-m  --format/-f
fzr  [input_path]  --input_path/-i  --model/-m  --input_variables/-v  --results_dir/-r
     --calculators/-c  --format/-f
fzl  --models/-m  --calculators/-c  --check  --format/-f
fzd  --input_dir/-i  --input_vars/-v  --model/-m  --output_expression/-e
     --algorithm/-a  --results_dir/-r  --calculators/-c  --options/-o
```

> **`fzd` flag divergence (easy to trip on):** `fzd`'s canonical input flags are
> `--input_dir`/`-i` and `--input_vars`/`-v` (fz ≥ 1.1 also accepts the `fzi`/`fzc`/`fzr`
> names `--input_path` and `--input_variables` as aliases; fz 1.0 took only the canonical
> names). It takes algorithm options via `--options`/`-o`, and has **no `--format`** — it
> prints a convergence summary and writes the design/analysis under `--results_dir`.
> `--input_dir` accepts a single file as well as a directory.

- Paths can be given positionally (`fzi input.txt -m mymodel`) or via flag
  (`fzi --input_path input.txt -m mymodel`), and these aliases work: `--variables` =
  `--input_variables`, `--calculator` = `--calculators` (repeatable), `--results` =
  `--results_dir`, `--output` = `--output_dir`. (fz 1.0 required the canonical flag names
  and had no positional form; the canonical flags work everywhere — prefer them.)
- `--format` accepts: `json`, `csv`, `html`, `markdown`, `table`.
- `--model` and `--input_variables` auto-detect their format: alias (bare name) → JSON
  file path (ends in `.json`) → inline JSON. `--calculators` takes a URI, JSON file path,
  a bare alias name, or an inline JSON list (`'["cache://run1", "sh://bash calc.sh"]'`);
  omit it entirely to auto-discover installed calculator aliases matching the model id
  (both `fzr` and `fzd` in fz ≥ 1.1). (fz 1.0: `--calculators` rejected bare alias names
  and `fzd` did not auto-discover — pass `fzd` calculators explicitly there.)
- Inline model definition (instead of, or overriding, `--model`): `--varprefix`,
  `--formulaprefix`, `--delim`, `--commentline`, `--interpreter`, and repeatable
  `--output-cmd NAME=COMMAND` for output parsers.
- `--input_vars` (fzd) takes JSON with `"[min;max]"` range strings for varied variables.

Stream discipline: results go to stdout; logs (`FZ_LOG_LEVEL`), progress bar, and error
messages go to stderr (the progress bar is disabled when stderr is not a TTY). Exit codes:
non-zero on failure, and `fzr` exits 1 when no case reached status `done`. Use
`--format json` for machine-readable output.

## Model JSON schema

```json
{
    "id": "mymodel",
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python",
    "output": {
        "name": "shell command run in each case directory, stdout is the value"
    }
}
```

All fields optional except `output` (required to parse results). `id` links the model to
calculator alias files. Search path for aliases: `./.fz/models/<alias>.json` then
`~/.fz/models/<alias>.json`.

## Calculator JSON schema

```json
{
    "uri": "ssh://user@cluster.edu",
    "models": {
        "mymodel": "bash /absolute/path/run_mymodel.sh"
    }
}
```

`models` maps model `id` → command on that machine (compiled input file/dir is passed as
first argument). Search path: `./.fz/calculators/<alias>.json` then `~/.fz/calculators/`.

## Calculator URI grammar

```
sh://command                                  local shell (default when omitted)
ssh://user[:password]@host[:port]/command     remote SSH (paramiko, SFTP transfer)
slurm://[user@host[:port]]:partition/command  SLURM srun; local form slurm://:partition/cmd
cache://path                                  reuse prior results by input-file hash
funz://[host]:port/ModelName                  legacy Java Funz server protocol
```

## Per-case execution lifecycle

For each case, fz: compiles inputs into `results_dir/<case>/`; copies them to a temp dir
on the calculator (under `.fz/tmp/`); runs the command with the input file as first
argument; captures `out.txt` (stdout), `err.txt` (stderr), `log.txt` (command, host, env,
timings, exit status); copies everything back; runs the `output` parsing commands; sets
`status` to `done` or `error`. Failed cases are retried on another calculator
(default 5 attempts).

## Environment variables

```
FZ_LOG_LEVEL                 DEBUG | INFO | WARNING | ERROR
FZ_MAX_WORKERS               max parallel cases
FZ_MAX_RETRIES               attempts for failed cases (default 5)
FZ_SSH_AUTO_ACCEPT_HOSTKEYS  1 to skip interactive host-key prompt (CI; use with care)
FZ_SSH_KEEPALIVE             SSH keepalive seconds
FZ_SHELL_PATH                bash location on Windows (MSYS2/Git Bash bin dirs)
```

## Variable syntax in input files

```
$name             variable
${name}           variable, explicit delimiters
${name~default}   variable with default value
@{expr}           formula, evaluated at compile time (may reference $vars)
#@ code           interpreter context line (imports, constants, function defs)
?name             legacy Java-Funz syntax, auto-converted to $name
```
