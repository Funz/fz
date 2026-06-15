# Example: calibrating a Newton's-law-of-cooling model (Modelica + brent)

A worked example of using the **fz skill** with an AI coding agent (Claude Code) to solve
a real engineering inverse problem end to end. It shows the *path* the agent takes — in
particular how it discovers and reuses two ready-made fz packages instead of building
everything from scratch:

- the **Modelica wrapper** (`fz install model modelica`) — runs the differential-equation
  model with OpenModelica, so we never write a solver;
- the **brent algorithm** (`fz install algorithm brent`) — a 1-D **root-finder** that drives
  the calibration loop, searching for the `k` where the simulated value hits the target.

Assert on the outcome, not the prose: the calibrated coefficient is analytic, so you can
check the agent's answer exactly.

## The engineering problem

A hot object cools in still ambient air. Newton's law of cooling models its temperature
`T(t)` with a single unknown — the lumped cooling coefficient `k` [1/s]:

```
dT/dt = -k · (T − T_env)
```

We know the boundary conditions (`T0 = 90 °C`, `T_env = 20 °C`) but **not** `k`. We have
**one measurement**: after `t = 600 s`, the object is at `T_obs = 40 °C`. *Calibration* =
find the `k` whose simulation reproduces that measurement.

This is a one-parameter inverse problem, which is exactly what `fzd` + a 1-D algorithm
like brent is for: we look for the `k` at which the residual `T_sim(600 s) − 40` crosses
zero. (The analytic answer, for checking: `T(t) = T_env + (T0−T_env)·e^{−kt}`, so
`k = −ln((40−20)/(90−20)) / 600 ≈ 0.002088 1/s`.)

## Prerequisites

- `fz` on PATH (`pip install 'funz-fz>=1.1'`; the CLI `fzd` used here is fixed in 1.1).
- The **fz skill** installed (see [../howto.md](../howto.md)).
- **OpenModelica** (`omc` on PATH) — the Modelica wrapper shells out to it.
  Ubuntu/Debian: `sudo apt-get install openmodelica`; macOS: `brew install openmodelica`.
- **R with rpy2** — the installed `brent` algorithm is implemented in R (`brent.R`), so fz
  evaluates it through rpy2; it also needs the R package `base64enc`. (`pip install rpy2`,
  and an R install; fz auto-installs `base64enc` via its `#require` header on first use.)
- `claude` CLI, logged in or `ANTHROPIC_API_KEY` set.

Work in a scratch directory **outside any git repository** (Claude Code resolves its
project at the enclosing repo root, which would otherwise hide a project-level skill):

```bash
SANDBOX=$(mktemp -d) && cd "$SANDBOX"
```

## Solve it in one ask

You don't have to spell out the steps — the skill supplies the workflow. Describe the
problem and the two tools, and let the agent drive:

```bash
claude -p "Using the fz skill, calibrate a Newton's-law-of-cooling model.

Physics: dT/dt = -k*(T - T_env), with T0 = 90 degC, T_env = 20 degC, and k [1/s] unknown.
Measurement: at t = 600 s the temperature is 40 degC. Find k.

Use fz's ready-made Modelica wrapper for the forward simulation (install it with
'fz install model modelica') and fz's brent algorithm for the 1-D calibration
('fz install algorithm brent'). Write a Modelica model NewtonCooling.mo parameterized
on k, add a scalar output for the final temperature, and verify the forward run on one
value first. Then use fzd with brent (a root-finder) to solve for the k where the
simulated temperature at t = 600 s equals 40 degC — i.e. the root of (T_final - 40) —
searching k in [0.0005; 0.01]. When done, write solution.json with keys k (the calibrated
value) and T_final (the temperature reached at t = 600 s)." \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" --max-turns 80
```

Check the agent's answer against the analytic value (within 5 % on `k`, 0.5 °C on the
fitted temperature):

```bash
jq -e '
  (-( ( (40-20)/(90-20) ) | log) / 600) as $k_exact
  | ((.k - $k_exact) / $k_exact | fabs) < 0.05
    and ((.T_final - 40) | fabs) < 0.5' solution.json \
  && echo "PASS: cooling coefficient calibrated"
```

## The path the agent follows

Under the hood the skill steers the agent through its standard wrap-and-verify ladder
(SKILL.md), with step 0 doing the heavy lifting here:

### 0. Discover the wrappers — don't reinvent them

The skill's first instruction is *check for an official wrapper*. For a Modelica model
that means:

```bash
fz install model modelica       # → github.com/Funz/fz-modelica; installs the 'Modelica'
                                 #   model + a localhost calculator alias into ./.fz/
fz install algorithm brent       # → github.com/Funz/fz-brent; installs brent.R into ./.fz/algorithms/
fz list --check                  # model + calculator + algorithm all present and valid?
```

This gives the forward model (how to compile a `.mo` file, run `omc`, and parse the
trajectory) and the calibration algorithm for free — no model JSON, runner, or algorithm
code to write. Note `brent` here is `brent.R`, a 1-D **root-finder** (it drives the output
expression to a target value, `ytarget = 0` by default).

### 1. Parameterize the model

The agent writes `NewtonCooling.mo`, exposing only the unknown `k` as an fz variable
(`${k}`); the known quantities stay fixed, and the simulation stops at the measurement
time so the trajectory's last point is `T(600 s)`:

```modelica
model NewtonCooling "Lumped-capacitance cooling in ambient air"
  parameter Real T0    = 90   "Initial temperature [degC]";
  parameter Real T_env = 20   "Ambient temperature [degC]";
  parameter Real k     = ${k} "Cooling coefficient [1/s]";
  Real T(start = T0)          "Object temperature [degC]";
equation
  der(T) = -k * (T - T_env);
annotation(experiment(StopTime = 600, Interval = 1));
end NewtonCooling;
```

### 2. Make the objective a scalar

The Modelica wrapper's only built-in output is `res`, which fz flattens into the whole
trajectory as arrays (`res_NewtonCooling_time`, `res_NewtonCooling_T`, …). The root-finder
needs a single number per run, so the agent adds a scalar output — the final temperature —
to the model definition (the skill's step-2/step-6 output-parsing decision). Concretely, it
adds a `T_final` entry to `.fz/models/Modelica.json` that reads the last row of the
results CSV:

```json
"T_final": "python3 -c \"import pandas,glob;print(pandas.read_csv(glob.glob('*_res.csv')[0])['T'].iloc[-1])\""
```

The calibration target is then simply the root of `T_final − 40`.

### 3. Verify the forward run before calibrating

Per the skill, the agent proves the forward model works on one `k` (the cheap-failure
gate) before launching the loop. No `--calculators` is needed — the installed Modelica
calculator alias is auto-discovered from the model id:

```bash
fzi --input_path NewtonCooling.mo --model Modelica --format json      # finds: k
fzr --input_path NewtonCooling.mo --model Modelica \
    --input_variables '{"k": 0.002}' --format json
# T_final ≈ 41.08 degC for k = 0.002 — physically sensible, so proceed.
```

### 4. Calibrate with fzd + brent

Now the inverse problem: find the root of the residual over `k`, with brent proposing the
1-D search points and the Modelica wrapper evaluating each:

```bash
fzd --input_dir NewtonCooling.mo --model Modelica \
    --input_vars '{"k": "[0.0005; 0.01]"}' \
    --output_expression "T_final - 40" \
    --algorithm brent --options '{"ytol": 0.01, "xtol": 1e-6}'
```

brent converges in ~8 iterations to `k ≈ 0.002088 1/s` (root approximation), where the
simulated `T_final` matches the measured 40 °C. The agent reports that `k` and writes
`solution.json`.

> Note the `fzd` CLI quirks: unlike `fzi`/`fzc`/`fzr` (which take `--input_path` and
> `--input_variables`), `fzd` names these `--input_dir`/`-i` and `--input_vars`/`-v`, and
> it has no `--format` flag — it prints a convergence summary and writes the design and
> final analysis under `results_fzd/` (override with `--results_dir`). `--input_dir`
> accepts a single input file as well as a directory. Like `fzr`, it auto-discovers the
> installed calculator, so no `--calculators` is required.

## Notes

- **brent is a root-finder, not a minimizer**: its options are `ytarget` (default `0`),
  `ytol`, `xtol`, and `max_iterations` (passed via `--options`). The objective is the raw
  residual `T_final - 40` — not its square — because brent drives the expression *to*
  `ytarget`, and it needs the residual to **change sign across the bracket** (here
  `+31.9 °C` at `k = 0.0005` and `−19.8 °C` at `k = 0.01`). If the recovered `k` is off,
  tighten `ytol`/`xtol` rather than widening the bracket.
- **Bracket the answer**: the true `k ≈ 0.00209` lies inside `[0.0005; 0.01]`.
- **More data / more unknowns**: with several measurements you would calibrate by
  *minimizing* a summed squared residual instead of root-finding — swap brent for a
  minimization algorithm (`fz install algorithm bfgs`), which also handles more than one
  unknown parameter.
- This is the skill-driven sibling of `examples/fz_modelica_projectile.ipynb` (in the fz
  repo), which does forward studies and optimization on a Modelica projectile model from
  Python.
