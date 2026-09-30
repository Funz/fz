# Constraints, Limits and Pitfalls

This page lists the behaviors of fz that most often surprise users. Each item states the
rule, the consequence, and what to do instead. Items are checked against the code
(`fz/core.py`, `fz/helpers.py`, `fz/runners/`, `fz/config.py`, `fz/cli.py`).

## Platform and dependencies

- **Python ≥ 3.9.** 3.9–3.13 are tested in CI; 3.14 is exercised as a pre-release only.
- **bash is required everywhere.** Calculator commands and shell output parsers run
  through bash. On Windows, install MSYS2 or Git Bash and point `FZ_SHELL_PATH` at its
  `bin` directories (see [shell-path.md](shell-path.md)). Shell-free output parsers
  (`python://`) remove the need for grep/awk, but not for bash in `sh://` calculators.
- **Required Python dependencies:** `paramiko`, `pandas`, `charset-normalizer`.
  Optional: `rpy2` (R formulas, extra `[r]`), `mcp` (the `fz-mcp` server, extra `[mcp]`,
  **Python ≥ 3.10 only**), `h5py` (the `hdf5_file()` output helper), `jq`, `yq`
  (mikefarah), `xmllint` (for `jq://`, `yq://`, `xpath://` outputs).
- **R formulas:** `import rpy2` can succeed while `import rpy2.robjects` fails
  (`ffi.error`, R/rpy2 version mismatch). fz then reports R as unavailable.

## Templates and models

- **Default delimiters differ for variables and formulas.** A model without `delim`
  (nor `var_delim`) delimits variables with `()` and formulas with `{}`: `${x}` is then
  not a variable. The CLI without `--model` uses `delim: "{}"`. Set `delim` explicitly.
- **No automatic `?var` conversion.** `?var` is a variable only with `"varprefix": "?"`.
- A variable absent from `input_variables` and without `~default` is left as-is in the
  compiled file (no error from `fzc`).
- `fzi` returns variables *and* formula expressions (e.g. `'T_celsius + 273.15'`) as keys.

## Python API

- **`fzr` argument order is `(input_path, input_variables, model, results_dir,
  calculators, ...)`.** `results_dir` comes *before* `calculators`. A call such as
  `fz.fzr("input.txt", variables, model, "sh://bash calc.sh")` puts the calculator URI into
  `results_dir` (a directory literally named `sh:/bash calc.sh` is created) and runs with
  no calculator, so every case fails. **Always pass `calculators=` and `results_dir=` by
  keyword.**
- **A DataFrame design must not contain duplicate rows** (`ValueError`): each row is one
  case. Variables given but absent from the templates only trigger a warning.
- **`FZ_*` environment variables are read once, at `import fz`.** Setting
  `os.environ["FZ_MAX_WORKERS"] = "8"` after the import has no effect until
  `fz.reload_config()` is called. Alternatives: set the variable before starting Python,
  call `fz.set_log_level("DEBUG")`, or change `fz.get_config().max_workers` directly.
- **`callbacks` is a dict**, not a list: keys `on_start`, `on_case_start`,
  `on_case_complete`, `on_progress`, `on_complete`. Any other key raises `ValueError`.
  Callbacks run in worker threads; an exception inside a callback is logged and ignored.
- **`fzd` with a Python function as model** (`input_path=None`): `calculators` must be a
  positive int (number of concurrent evaluations, default 1). With `calculators > 1` the
  function must be thread-safe; any error in parallel mode aborts the whole `fzd` with
  `FunctionModelParallelError`. Callables bridged from R (reticulate) must use
  `calculators=1`.

## CLI

- **CLI and Python differ for `fzd`:**
  - `--output_expression` takes a single expression; a *list* of objectives
    (multi-objective `fzd`) is only available from Python.
  - The CLI default results directory is `results_fzd`; the Python default
    `analysis_dir` is `analysis`.
  - `fzd` has no `--format` option; function models are Python-only.
- **`fzl` / `fz list` formats** are `json`, `markdown` and `table` only (no `csv`/`html`).
- **Non-factorial designs are Python-only.** `--input_variables` takes a JSON dict
  (inline or file) or the short form `'a=1,b=[4,5,6]'`, always crossed as a full
  factorial; a list of cases requires a pandas DataFrame from Python.
- **No `--timeout` flag.** Use the model's `"timeout"` entry or `FZ_RUN_TIMEOUT`.
- **`fz list` / `fzl`** shows calculator aliases by their `uri`, not their file name, and
  `--check` reports an alias whose command sits in its `models` map
  (`{"uri": "sh://", "models": {...}}`, the layout of installed wrappers) as failed
  (`Empty sh:// command`) although `fzr` uses it correctly. Algorithms are not listed.
- **`fzr` exits with status 1 when no case succeeds**; data goes to stdout, logs and
  progress to stderr. Use `--format json` for machine-readable output.

## Parallelism and retries

- **Parallel workers = number of non-cache calculator entries** (capped by the number of
  cases). One entry runs cases sequentially; `["sh://bash calc.sh"] * 4` runs four at a
  time. `FZ_MAX_WORKERS` only **caps** that number; it never adds workers. Exception:
  `slurm-array://` uses one waiting thread per case (capped by `FZ_MAX_WORKERS`) so that
  cases can be batched into one job array.
- **Case → calculator assignment** prefers `case_index mod n_calculators` and falls back
  to the first free calculator.
- **`FZ_MAX_RETRIES` (default 5)** is the number of calculator failures tolerated per
  case; after that the case is marked `failed`. With several calculators, a failed
  attempt moves to another calculator.
- **Case `status` values:** `done`, `failed`, `error`, `timeout`, `interrupted`. A cache
  hit is `done` with a `calculator` value starting with `cache://`.

## Timeouts

- **Resolution order:** `timeout=` argument of `fzr()` > model `"timeout"` entry >
  `FZ_RUN_TIMEOUT`.
- **Default:** 3600 s for `sh://` and `funz://`; **no timeout** for `ssh://` and
  `slurm://` unless `FZ_RUN_TIMEOUT` is set explicitly (a warning is logged).
- **Only a model `"timeout"` of `null`/`None` or `0` disables the timeout.**
  `FZ_RUN_TIMEOUT=0` or `timeout=0` does *not* disable it: every case times out
  immediately.

## `sh://` command line

- **The command runs inside a per-case temporary directory**, and the case's input file
  names are **appended to the end of the whole command line** (`.` when there are none).
  With pipes or redirections, they are appended after the last element.
- **File names in the command**: a bare word (`run.sh`, `data.txt`) is made absolute in
  the launch directory only if it exists there **and not** in the case directory;
  redirection targets stay in the case directory. Consequence of the appended arguments:
  `sh://cat input.txt > res.txt` runs `cat input.txt > res.txt input.txt` and `res.txt`
  holds the input twice. **Put the work in a script** (`sh://bash run.sh`): inside it,
  relative paths refer to the case directory and `$1`, `$2`, ... are the compiled input
  files.
- `ssh://` and `slurm://` commands run on the remote side: use absolute remote paths.

## Files and directories

- **Reserved names in each case directory:** `out.txt` (stdout), `err.txt` (stderr),
  `log.txt`, `info.txt`, `history.txt` and `.fz_hash` are written by fz. A simulation
  output with one of these names is **overwritten** (e.g. a code writing `out.txt` loses
  it to the captured stdout). Name code outputs differently.
- **Reserved names at the results root:** `manifest.json`, `ro-crate-metadata.json`
  (disable with `FZ_RO_CRATE=0`) and, with `case_naming="hash"`/`"index"`, `cases.csv`.
- **Case directory names (`case_naming="path"`, default)** are `var1=val1,var2=val2,...`.
  The characters `/ \ : * ? " < > | %` and control characters are percent-encoded, and a
  value of exactly `.` or `..` is encoded. Names can exceed the ~255-character filename
  limit with many variables or long values: use `case_naming="hash"` or `"index"`
  (always used internally by `fzd`).
- **`fzc` always writes one sub-directory per case** (`output_dir/var1=val1,.../`) when
  the input declares variables, even when all values are scalars. Run the code and
  `fzo` inside that sub-directory (or on the glob `output_dir/*`); `fzo output_dir`
  itself returns a row of `None`.
- **Global wrapper installs:** `fz install model <X> --global` copies the wrapper to `~/.fz/`, but its calculator
  alias keeps the relative command `bash .fz/calculators/<X>.sh`, looked up in the
  launch directory, then the case directory, never in `~/.fz/`: runs from any other
  directory fail (`Command not found locally: '.fz/calculators/<X>.sh'`). Prefer project-local installs, or edit
  `~/.fz/calculators/localhost_<X>.json` to use the absolute path of the script (`~` is
  not expanded).
- **Existing results directories are not overwritten in place**: an existing
  `results_dir` is renamed with a timestamp suffix before the new run (and can be reused
  via `cache://`).
- **`input_static` absolute paths** must exist at the same path on the calculator side
  (shared storage); fz never copies them. Relative paths are symlinked (copied where
  symlinks are unavailable) and transferred to remote calculators.

## Cache (`cache://`)

- **The cache key is the SHA-256 of the case's input files** (plus `input_static`), and,
  when declared, the calculator's `code_id`. It **does not include the calculator
  command or the output parsers**: changing the simulation script without changing the
  inputs still hits the cache. Declare a `code_id` (or `version_cmd`) in calculator
  aliases, or use a fresh `results_dir` without `cache://`, to force recomputation.
- A match between calculators with no declared `code_id` is accepted with a warning;
  `FZ_CACHE_STRICT=1` refuses it.
- **Resuming into the same `results_dir`** requires the special entry `cache://_` (the
  renamed previous content). `cache://<results_dir>` points to the new, empty directory
  and never hits.
- Caches written before the v2 hash format (MD5) are ignored unless
  `FZ_CACHE_ACCEPT_LEGACY=1`.
- A cached case is reused only if its outputs, parsed with the *current* model, are all
  non-`None`.

## Remote calculators

- **`slurm-array://` is local only** (the machine running fz must have `sbatch`/`sacct`).
  `slurm://` supports both local and SSH-remote SLURM.
- **SSH host keys:** with key authentication, an unknown host key is added
  automatically (paramiko `AutoAddPolicy`, no fingerprint check). With a password in the
  URI, fz asks interactively on stdin, which blocks unattended runs, unless
  `FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1`. Pre-populate `~/.ssh/known_hosts` when host identity
  matters. A password embedded in the URI is masked in results and logs but stays in
  memory and in your scripts: prefer keys.
- **No interactive SSH password prompt.** Use keys, or a password in the URI (keys are
  then not tried). Without `user@`, the user is `$SSH_USER`, else the local user.
- **Remote cleanup** (`rm -rf`) is refused outside fz's own `.fz/tmp/fz_calc_*` /
  `fz_slurm_*` directories.
- **`funz://`** needs a running legacy Java Funz calculator (TCP), optionally discovered
  by UDP broadcast (`fz.discover_funz_servers`).

## Security

Templates, `#@` formula-context lines, `@{...}` formulas, output commands and calculator
commands are **executed as code with the user's privileges**. There is no sandbox. Do not
run a model, algorithm or calculator alias obtained from an untrusted source without
reading it. `fz-mcp` confines file paths to `FZ_MCP_ROOT` and can restrict models and
calculators to installed aliases (`FZ_MCP_TRUSTED=0`), but its tool annotations are
advisory, not a security boundary. See the "Threat Model" section of the README and
[mcp-server.md](mcp-server.md).
