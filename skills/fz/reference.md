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
float, list, dict) when possible.

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
fz.fzd(input_path: str,
       input_variables: dict[str, str],     # "[min;max]" varied, "value" fixed
       model: str | dict,
       output_expression: str,              # e.g. "pressure" or "out1 + 2*out2"
       algorithm: str,                      # name or path to .py algorithm
       calculators: str | list[str] = None,
       algorithm_options: dict | str = None,  # dict, JSON string, or JSON file path
       analysis_dir: str = "analysis") -> dict   # CLI default: results_fzd
```

Returns `{"XY": DataFrame, "analysis": ..., "iterations": int,
"total_evaluations": int, "summary": str}`. Duplicate points within a batch are
deduplicated; previously evaluated points are cached across iterations and re-runs.

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
<name|git-url>` installs aliases into `.fz/` (`--global` for `~/.fz/`).

Common options:

```
--model M                 model alias | path to .json | inline JSON
--variables V             inline JSON | path to .json file
--calculator URI          repeatable; alias | URI | inline JSON
--format F                json | csv | table | markdown | html
--varprefix / --formulaprefix / --delim / --commentline    inline model definition
--output-cmd name="cmd"   inline output parser (repeatable)
--results DIR             (fzr) results directory
```

`--model`, `--variables`, `--calculator` auto-detect their format: alias (bare name) →
JSON file (ends in `.json`) → inline JSON (starts with `{`).

fzd-specific: `--input_dir/-i`, `--input_vars/-v` (JSON with `"[min;max]"` ranges),
`--output_expression/-e`, `--algorithm/-a`, `--options/-o`, `--results_dir`.

Exit code is non-zero on failure; use `--format json` for machine-readable output.

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
