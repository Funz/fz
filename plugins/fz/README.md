# fz — Claude Code plugin

Teaches Claude to run parametric simulation studies with [fz](https://github.com/Funz/fz)
(Funz): wrap a simulation code, run parameter sweeps locally, over SSH or on SLURM, run
adaptive designs of experiments (optimization, calibration), and collect results into
DataFrames.

## Install

```
/plugin install fz --marketplace Funz/fz
```

On older Claude Code: `/plugin marketplace add Funz/fz` then `/plugin install fz@funz`.

## Contents

- **Skill `fz`** (`skills/fz/`): the wrapping workflow, a condensed API/CLI reference, and
  guides for writing model wrappers and `fzd` algorithms.
- **Commands**: `/fz:wrap`, `/fz:run`, `/fz:design`, `/fz:install`.

## Requirements

The plugin contains instructions only. Running studies needs the `funz-fz` Python package
and bash: see <https://github.com/Funz/fz#installation>.

## License

BSD-3-Clause, see `LICENSE`.
