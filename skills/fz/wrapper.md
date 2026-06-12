# Implementing an fz wrapper (code binding)

How to package fz support for a simulation code as a reusable, installable wrapper —
the `fz-<code>` repositories that `fz install model <code>` consumes. Read this when the
task is "make fz support code X" or "publish an fz binding", rather than wrapping a code
ad hoc for one study (for that, [SKILL.md](SKILL.md) steps 1–2 suffice).

## What a wrapper is

A wrapper bundles, for one simulation code:

1. a **model JSON** — how to recognize variables in input files and parse outputs;
2. a **runner script** — how to launch the code on a compiled input file;
3. a **calculator alias** — wiring the script to the model on the local machine.

Installed with `fz install model <code>`, used with `--model <Code>` and (in `fzr`)
auto-discovered calculators. No Python code is involved — a wrapper is data + shell.

## Repository layout

The convention consumed by the installer (`fz/installer.py`):

```
fz-mycode/                         # GitHub repo named fz-<code> (lowercase)
├── .fz/
│   ├── models/
│   │   └── MyCode.json            # the model definition (file name = alias)
│   └── calculators/
│       ├── MyCode.sh              # runner script (made executable on install)
│       └── localhost_MyCode.json  # local calculator alias
├── tests/                         # recommended: a tiny end-to-end case
│   ├── input.txt                  # parameterized sample input
│   └── test.sh                    # runs the SKILL.md steps 3–6 against it
└── README.md
```

- A bare name resolves to `https://github.com/Funz/fz-<code>` (official wrappers live
  under the Funz organization; any git URL or local zip also works:
  `fz install model https://github.com/you/fz-mycode.git`).
- On install, `.fz/models/MyCode.json` is copied to the project's (or, with `--global`,
  the user's) `.fz/models/`; every other `.fz/` subdirectory (`calculators/`, optionally
  `algorithms/`) is copied wholesale, and `.sh`/`.bash`/`.zsh` scripts are made executable.

## 1. The model JSON

```json
{
    "id": "MyCode",
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "energy": "grep 'Total energy' out/results.log | awk '{print $4}'",
        "trajectory": "python -c 'import pandas, json; print(json.dumps(pandas.read_csv(\"out/traj.csv\").to_dict(orient=\"list\")))'"
    }
}
```

Rules and choices:

- **`id` is mandatory for a wrapper** — it is the key that binds calculators to this
  model. Match it to the alias file name (`MyCode.json` → `"id": "MyCode"`).
- Pick `varprefix`/`formulaprefix`/`delim`/`commentline` that do NOT collide with the
  code's own input syntax (e.g. if `$` is meaningful to the code, use `%`; `commentline`
  must be the code's real comment character so `#@` context lines are ignored by the code).
- Each `output` entry is a shell command run **inside the case's result directory** after
  the run; its stdout is the value, auto-cast to int/float/list/dict when possible. Returning
  a JSON dict/list (as `trajectory` above) gives structured columns in the results DataFrame.
- Prefer `python3` over `python` in output commands, and keep dependencies minimal —
  these commands run on the user's machine, not yours.

## 2. The runner script

The contract (see "Per-case execution lifecycle" in [reference.md](reference.md)):

- invoked **inside a fresh case directory** containing the compiled input file(s);
- receives the compiled input file (or directory) as **first argument** `$1`;
- must write the output files that the model's `output` commands parse;
- exit status `0` = case done, non-zero = case failed (fz retries it elsewhere);
- stdout/stderr are captured to `out.txt`/`err.txt` automatically — print freely;
- if the code spawns long-lived subprocesses, write their PID to a `PID` file so
  interrupts can kill them.

```bash
#!/bin/bash
# MyCode.sh — fz runner for MyCode. Usage: MyCode.sh <compiled input file>

# locate the executable: PATH first, then a conventional install dir
MYCODE=${MYCODE_BIN:-$(command -v mycode || echo /opt/mycode/bin/mycode)}
[ -x "$MYCODE" ] || { echo "mycode executable not found (set MYCODE_BIN)" >&2; exit 2; }

"$MYCODE" "$1" out &      # mycode <input file> <output dir>
echo $! >> PID            # let fz kill the run on interrupt
wait $!
status=$?
rm -f PID

# fail loudly if the expected output is missing, so the case is marked "error"
[ $status -eq 0 ] && [ -f out/results.log ] || exit 1
```

## 3. The local calculator alias

```json
{
    "uri": "sh://",
    "models": {
        "MyCode": ".fz/calculators/MyCode.sh"
    }
}
```

`models` maps the model **id** to the command launching it on this machine. With this
file installed, `fzr --model MyCode ...` without `--calculators` finds and uses it
automatically. Users add their own `ssh://`/`slurm://` aliases with the same `models` key
for remote execution.

## 4. Test it like a user would

From a scratch directory:

```bash
fz install model ./fz-mycode.zip        # or the repo path / URL
fz list --check --format json           # model + calculator must validate

# then the SKILL.md verification ladder on a sample input:
fzi --input_path tests/input.txt --model MyCode --format json     # variables found?
fzc --input_path tests/input.txt --model MyCode \
    --input_variables '{"x": 1}' --output_dir compiled/           # compiles?
(cd compiled && bash .fz/calculators/MyCode.sh input.txt)         # runs?
fzo --output_path compiled/ --model MyCode --format json          # outputs parse?
fzr --input_path tests/input.txt --model MyCode \
    --input_variables '{"x": [1, 2]}' --format json               # end to end
```

Ship that sequence as `tests/test.sh` in the wrapper repo (CI-friendly: it needs only
fz, bash, and the simulation code).

## 5. Publish

- Name the repo `fz-<code>`; the default branch must be `main` (the installer fetches
  `archive/refs/heads/main.zip`).
- README: what the wrapper expects installed (the code itself, env vars like
  `MYCODE_BIN`), the variables syntax chosen, the outputs provided, and a copy-paste
  quickstart (`fz install model <code>` + one `fzr` line).
- Same convention for algorithm packages: `fz-<name>` with `.fz/algorithms/<name>.py`,
  installed via `fz install algorithm <name>`.

## Existing wrappers to imitate

Browse <https://github.com/orgs/Funz/repositories?q=fz-> — e.g. `fz-modelica` and
`fz-moret` are reference implementations of this layout (the `plugin-*`/`algorithm-*`
repos are legacy Java-Funz, different format).
