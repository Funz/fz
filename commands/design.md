---
description: Adaptive design of experiments, optimization or calibration with fz (fzd)
argument-hint: [objective, variables + [min;max] ranges, algorithm]
---
Solve an adaptive design-of-experiments problem with **fz** (`fzd`), following the
fz Agent Skill.

Request: $ARGUMENTS

- Use `fzd` (not `fzr`) when the values should be chosen by an algorithm rather than a
  fixed grid: optimization, calibration / inversion, uncertainty propagation,
  sensitivity analysis, adaptive sampling.
- Ranges use `"[min;max]"` for a varied variable and `"value"` for a fixed one.
- Prefer an installed algorithm over writing one: `fz install algorithm <name>`
  (`brent`, `gradientdescent`, `PSO`, …; browse
  <https://github.com/orgs/Funz/repositories?q=fz->), or copy one from
  `examples/algorithms/` into `.fz/algorithms/`. Reference it by bare name.
- Set `output_expression` to any expression of the model outputs (e.g. a
  squared-difference for calibration against a target).
- Check the algorithm file's `#options:` and `#require:` header lines for its options
  and Python dependencies.
- Verify the wrapper on one case first. Report `results["summary"]` and the evaluated
  points in `results["XY"]`.
