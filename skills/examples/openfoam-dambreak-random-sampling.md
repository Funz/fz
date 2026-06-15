# Example: random-sampling an OpenFOAM dam break — wrapper *and* algorithm built live

A worked example of using the **fz skill** with an AI coding agent (Claude Code) on a code
that has **no ready-made fz package**. It is the deliberate opposite of
[newton-cooling-calibration.md](newton-cooling-calibration.md), where the agent installed an
official Modelica wrapper and brent algorithm: here **both pieces are authored from
scratch**, in the working directory, because nothing exists to install —

- the **OpenFOAM coupling** — a code wrapper (model + runner + calculator), following
  [../fz/code-wrapper.md](../fz/code-wrapper.md);
- the **random sampling** — a custom `fzd` algorithm, following
  [../fz/algorithm-wrapper.md](../fz/algorithm-wrapper.md).

So this is the path the skill takes when its step-0 check ("is there an official wrapper?")
comes back empty: build the binding yourself, verify it cheaply, then run the study.

> **Validated end to end** against OpenFOAM v2412 (`interFoam`) and the bundled
> `damBreak` tutorial: the wrapper and the custom algorithm below were run as written —
> an 8-sample study completes in ~30 s and yields a peak water height varying ~0.08–0.18 m
> with obstacle height. OpenFOAM-internal names (paths, the `blockMeshDict` obstacle level,
> the function-object column) are still **distribution/version dependent** — confirm them
> in your install. A directory-tree code like OpenFOAM needs **fz ≥ 1.1** to run at all
> (1.1 added recursive staging of case subdirectories into and out of the run directory,
> plus the `fzd` CLI/auto-discovery fixes this study relies on).

## The engineering problem

The [OpenFOAM "breaking of a dam" tutorial](https://www.openfoam.com/documentation/tutorial-guide/4-multiphase-flow/4.1-breaking-of-a-dam)
(`damBreak`, the `interFoam` VOF multiphase solver) releases a column of water that
collapses across a tank. The tank floor carries a small **obstacle**. We treat the
**obstacle height** as uncertain and do a **random (Monte-Carlo) sampling** of it to study
how it affects a quantity of interest — here the **peak water height** reached at a
downstream location.

## Prerequisites

- **OpenFOAM** installed and its environment **sourced** (`blockMesh`, `setFields`, and the
  solver — `interFoam` or `foamRun` depending on your distribution — on PATH). The tutorial
  case ships under `$FOAM_TUTORIALS/multiphase/interFoam/laminar/damBreak/damBreak`.
- `fz` on PATH (`pip install 'funz-fz>=1.1'`) and the **fz skill** installed (see
  [../howto.md](../howto.md)).
- `claude` CLI, logged in or `ANTHROPIC_API_KEY` set.

Work in a scratch directory **outside any git repository** (Claude Code resolves its
project at the enclosing repo root, which would otherwise hide a project-level skill):

```bash
SANDBOX=$(mktemp -d) && cd "$SANDBOX"
```

## Solve it in one ask

Describe the problem and make the two "build it yourself" requirements explicit, so the
agent doesn't waste a turn hunting for a plugin that isn't there:

```bash
claude -p "Using the fz skill, run a random-sampling study on the OpenFOAM 'damBreak'
tutorial (interFoam). There is NO official fz wrapper for OpenFOAM and NO installable
sampling algorithm — implement both yourself in this directory:

1. Wrap the case as a reusable fz model (follow the skill's code-wrapper guide): copy the
   damBreak tutorial, parameterize the obstacle height in system/blockMeshDict, write the
   model JSON + a runner script that runs blockMesh and the solver + a local calculator
   alias. Mind the variable-prefix collision: OpenFOAM uses '\$' for its own macros, so
   choose a different fz varprefix (e.g. '%'). Pick a scalar output: the peak water height
   at a downstream location (add an interfaceHeight function object if needed).
2. Write a custom fzd random-sampling algorithm (follow the skill's algorithm-wrapper
   guide) that draws N uniform samples of the obstacle height in one batch.

Verify the wrapper on a single height before the study. Then sample the obstacle height
(20 draws, seed 1) over a sensible range and report mean/std of the peak height; write the
per-sample results to results.json (records of obstacle_height, peak_height, status)." \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" --max-turns 120
```

## The path the agent follows

### 0. No official wrapper → author one

The skill's step 0 is *check for an official wrapper*. `fz install model openfoam` resolves
to `github.com/Funz/fz-openfoam`, which does not exist — so the agent falls through to the
authoring path ([code-wrapper.md](../fz/code-wrapper.md)) instead of a one-line install.

### 1. Get the case

```bash
cp -r "$FOAM_TUTORIALS/multiphase/interFoam/laminar/damBreak/damBreak" case
# conda-forge OpenFOAM leaves FOAM_TUTORIALS unset; use $WM_PROJECT_DIR/tutorials/... there
```

### 2. Parameterize the obstacle height — mind the prefix collision

In this geometry the obstacle is the **un-meshed floor block** between `x = 2` and
`x = 2.16438`: the `blocks` list simply omits it, so the mesh flows around a solid step
whose top sits at the shared y-level `0.32876` (× `scale 0.146` ≈ 0.048 m). Raising or
lowering that level *is* changing the obstacle height, so the agent replaces every
occurrence of `0.32876` in `system/blockMeshDict` with the fz variable:

```bash
sed -i 's/0.32876/%obstacle_height/g' case/system/blockMeshDict   # 8 vertex rows
```

**OpenFOAM already uses `$` for macro expansion**, so reusing fz's default `$` prefix would
clash — the agent picks a non-colliding prefix (`%`), exactly the situation
[code-wrapper.md](../fz/code-wrapper.md) warns about:

```c++
// system/blockMeshDict (the 8 vertices at the obstacle-top level)
    (0       %obstacle_height 0)
    (2       %obstacle_height 0)
    (2.16438 %obstacle_height 0)
    (4       %obstacle_height 0)
    // ... and the same four at z = 0.1
```

(`%obstacle_height` is in `blockMeshDict` units — multiplied by `scale`; default `0.32876`,
sampled below over `[0.2; 0.5]`. fz's `{}`/`@` formula syntax is untouched: OpenFOAM never
writes `@{...}`, so no formula is triggered.)

### 3. Define the QoI and the model

The base case writes no scalar result, so the agent enables an `interfaceHeight` function
object to record the water height at two downstream probes. `controlDict` already ends with
`functions { #sinclude "sampling" }`, so just drop in `system/sampling`:

```c++
// system/sampling
interfaceHeight1
{
    type        interfaceHeight;
    libs        (fieldFunctionObjects);
    alpha       alpha.water;
    locations   ((0.35 0 0.005) (0.45 0 0.005));   // just downstream of the obstacle
    writeControl    timeStep;
    writeInterval   20;
}
```

It writes `postProcessing/interfaceHeight1/0/height.dat` with columns
`Time, hB hL (loc0), hB hL (loc1)`; the QoI is the peak `hB` at the first probe (column 2).

`.fz/models/OpenFOAM.json` — `varprefix: "%"`, `commentline: "//"`, and a scalar
`peak_height` output:

```json
{
    "id": "OpenFOAM",
    "varprefix": "%",
    "commentline": "//",
    "output": {
        "peak_height": "LC_ALL=C awk '!/^#/ && NF {v=$2+0; if (v>m) m=v} END {print m}' postProcessing/interfaceHeight1/0/height.dat"
    }
}
```

The output command runs **inside each case's result directory** after the solver; its
stdout is auto-cast to a number. Two robustness points learned by actually running this:
**`LC_ALL=C`** forces a period decimal separator — without it, on a non-English locale a
plain `sort -g` mis-orders the scientific-notation values and returns a near-zero "max";
and computing the max in `awk` (rather than `sort | tail`) keeps it to one pass.

### 4. The runner script

`.fz/calculators/OpenFOAM.sh` — runs the meshing and the solver in the compiled case dir.
Using the tutorial's own `Allrun` keeps it solver-version agnostic (`Allrun` reads the
solver name from `controlDict`):

```bash
#!/bin/bash
# OpenFOAM.sh — fz runner for the damBreak wrapper. Usage: OpenFOAM.sh <compiled case dir>
[ -d "$1" ] && cd "$1"
command -v blockMesh >/dev/null || { echo "OpenFOAM environment not sourced" >&2; exit 2; }

bash ./Allrun > log.Allrun 2>&1       # blockMesh + setFields + the case's solver

# fail loudly if the quantity of interest was not produced, so the case is marked error
ls postProcessing/interfaceHeight1/*/height.dat >/dev/null 2>&1 || { echo "no interfaceHeight output" >&2; exit 1; }
```

(Invoke it as `bash ./Allrun`, not `bash Allrun`: `Allrun`'s first line is
`cd "${0%/*}"`, which with a bare name becomes `cd Allrun` and aborts the script.)

### 5. The local calculator alias

`.fz/calculators/localhost_OpenFOAM.json` — wires the model **id** to the runner so fz can
auto-discover it:

```json
{
    "uri": "sh://",
    "models": { "OpenFOAM": "bash .fz/calculators/OpenFOAM.sh" }
}
```

### 6. Verify the wrapper on one height (definition of done)

Per the skill, prove the binding works on a single case — the cheap-failure gate — before
the study. No `--calculators` is needed; the installed alias is auto-discovered from the
model id:

```bash
fzi --input_path case --model OpenFOAM --format json                 # finds: obstacle_height
fzr --input_path case --model OpenFOAM \
    --input_variables '{"obstacle_height": 0.33}' --format json      # one full run; peak_height parses?
```

### 7. Author the random-sampling algorithm

`.fz/algorithms/random_sampling.py` — a one-shot `fzd` algorithm
([algorithm-wrapper.md](../fz/algorithm-wrapper.md)): propose all N points up front, then
stop. `input_vars` arrives as `{name: (min, max)}`; `get_next_design` returning `[]` ends
the loop; `get_analysis` summarizes:

```python
#title: Uniform random sampling (Monte Carlo)
#author: example
#options: n=20;seed=1

import random

class RandomSampling:
    def __init__(self, **options):
        self.n = int(options.get("n", 20))
        self.seed = int(options.get("seed", 1))

    def get_initial_design(self, input_vars, output_vars):
        rng = random.Random(self.seed)
        return [{v: rng.uniform(lo, hi) for v, (lo, hi) in input_vars.items()}
                for _ in range(self.n)]

    def get_next_design(self, previous_input_vars, previous_output_values):
        return []  # one-shot: every point was proposed in the initial design

    def get_analysis(self, input_vars, output_values):
        ys = [y for y in output_values if y is not None]   # None = a failed case
        n = len(ys)
        mean = sum(ys) / n if n else float("nan")
        std = (sum((y - mean) ** 2 for y in ys) / n) ** 0.5 if n else float("nan")
        return {
            "text": f"random sampling: {n} valid samples, mean={mean:.4g}, std={std:.4g}",
            "data": {"n": n, "mean": mean, "std": std,
                     "min": min(ys, default=None), "max": max(ys, default=None)},
        }
```

### 8. Run the study

```bash
fzd --input_dir case --model OpenFOAM \
    --input_vars '{"obstacle_height": "[0.2; 0.5]"}' \
    --output_expression "peak_height" \
    --algorithm .fz/algorithms/random_sampling.py \
    --options '{"n": 20, "seed": 1}' \
    --results_dir study
```

`fzd` evaluates the sampled heights (each a full CFD run), records `peak_height` per sample
under `study/`, and prints the `get_analysis` summary (mean/std of the peak height). The
agent collects the per-sample records into `results.json`. As validated, an 8-sample run
finishes in ~30 s with peaks spread over ~0.08–0.18 m (mean ≈ 0.12, std ≈ 0.04).

## Notes

- **The prefix collision is the lesson here.** Because OpenFOAM owns `$`, the wrapper must
  set a different `varprefix`. The agent confirms its choice with `fzi` — it should report
  exactly `obstacle_height`, not stray `$`-macros from the OpenFOAM dictionaries.
- **CFD cost scales with `n`.** This tiny damBreak case runs in ~3 s, so 20 samples is a
  minute; a real case is far heavier. Run samples concurrently by supplying several
  calculators
  (`--calculators '["localhost_OpenFOAM", "localhost_OpenFOAM", "localhost_OpenFOAM"]'`),
  or lower `n` while developing. fz deduplicates and caches across runs, so re-running with
  a larger `n` reuses what was already computed.
- **Random sampling vs. `fzr`.** A fixed Monte-Carlo list could also be run with
  `fzr --input_variables '{"obstacle_height": [<random values>]}'`. Authoring it as an
  `fzd` algorithm instead is what makes the *sampling logic itself* a reusable, swappable
  component — and is the point this example demonstrates.
- **Promote it later.** Once verified, the two artifacts are exactly what the `fz-<name>`
  packaging conventions expect: the case + `.fz/` could become an installable
  `fz-openfoam` model, and `random_sampling.py` an installable `fz-randomsampling`
  algorithm (see [code-wrapper.md](../fz/code-wrapper.md) and
  [algorithm-wrapper.md](../fz/algorithm-wrapper.md)). This example is how a wrapper begins
  before it is published.
