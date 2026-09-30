---
description: Run an fz parametric study over a variable grid and collect the results
argument-hint: [variables + ranges, calculator/host, outputs wanted]
---
Run a parametric study with **fz** (`fzr`), following the fz Agent Skill.

Request: $ARGUMENTS

- If the simulation is not wrapped and verified yet, do that first (`fzi` → `fzc` →
  one manual run → `fzo` on a single case) before launching the batch.
- Build `input_variables` as a dict of lists (full factorial — Cartesian product) or,
  from Python only, as a DataFrame with one row per case (LHS, constrained or imported
  designs; read a CSV with `pandas.read_csv`). The CLI only takes the dict form.
- Choose calculators: `sh://` local, `ssh://user@host/command` remote, `slurm://`
  for HPC. Repeat a URI or pass a list to run cases in parallel. Put
  `cache://<previous results dir>` first in the list to resume or extend a run —
  only the missing cases are computed.
- Use `--format json` on the CLI (data → stdout, logs → stderr; `fzr` exits 1 when no
  case succeeds).
- In Python, pass `calculators=` and `results_dir=` as keywords (`results_dir` is the
  4th positional parameter of `fz.fzr`).
- After the run, report the `status` counts (`done`/`failed`/`error`/`timeout`/
  `interrupted`; cache hits are `done` with a `cache://` calculator) and show the
  results table. For any non-`done` or `null`-output case, read that case's
  `err.txt` / `log.txt` before concluding.
