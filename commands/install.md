---
description: Find and install an official fz-<code> model wrapper or fzd algorithm
argument-hint: [simulation code or algorithm name]
---
Find and install a ready-made **fz** package for: $ARGUMENTS

- Funz publishes model wrappers and algorithms as GitHub repos named `fz-<name>`
  under <https://github.com/orgs/Funz/repositories?q=fz->.
- Model wrapper: `fz install model <name>` (e.g. `fz install model modelica`).
- Algorithm: `fz install algorithm <name>` (e.g. `fz install algorithm brent`).
- Add `--global` to install into `~/.fz/` instead of the project's `.fz/`.
- Verify what got installed: `fz list --check --format json` (alias `fzl`).
- A model wrapper drops `.fz/models/<Code>.json` plus a `localhost_<Code>` calculator
  alias, auto-discovered by `fzr`/`fzd` from the model id. Then add `$var` markers to
  your input file and verify with `fzi` → `fzc` → run → `fzo`.
