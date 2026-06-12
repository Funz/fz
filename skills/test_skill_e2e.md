# Testing the fz skill with shell commands only

This is the shell-only equivalent of `tests/test_skill_e2e.py`: it drives a headless
Claude Code session against the fz skill and a tiny deterministic simulation (perfect gas
pressure), then asserts on the **artifacts** the agent leaves behind — never on its prose.
Paste the blocks in order, or save them as a script. Every block ends in a checkable exit
status, so `bash -e` (or `&&`-chaining) aborts at the first failure. The `< /dev/null` on each
`claude` call matters when running this as a script: headless claude reads piped stdin as
extra input and would otherwise swallow the rest of the script.

Requirements: `claude` CLI (logged in, or `ANTHROPIC_API_KEY` set), `fz` on PATH
(`pip install funz-fz`), `jq`.

```bash
# Model used by the agent session — haiku keeps the cost negligible
MODEL=${FZ_SKILL_TEST_MODEL:-claude-haiku-4-5}
```

## 0. Probe: does claude actually work here?

One tiny one-turn call. If this fails (not installed, not logged in, no key), there is no
point running the rest — this is exactly the check the pytest version uses to self-skip.

```bash
claude -p "Reply with exactly: OK" --model "$MODEL" --max-turns 1 < /dev/null \
  || { echo "claude CLI not functional — stopping"; exit 1; }
```

## 1. Build a sandbox project

The sandbox must live **outside any git repository** (in particular outside the fz repo):
Claude Code resolves its project at the enclosing repo root, and would otherwise ignore
the sandbox's `.claude/skills/`.

```bash
FZ_REPO=~/Sync/Open/Funz/github/fz        # adjust to your fz checkout
SANDBOX=$(mktemp -d)
cd "$SANDBOX"

# the skill, project-level
mkdir -p .claude/skills
cp -r "$FZ_REPO/skills/fz" .claude/skills/
```

The simulation: an input file parameterized with fz syntax (`$var` variables, `@{...}`
formulas) and a solver script. Deliberately **no fz model is provided** — defining it
(variable syntax, output parsing command) is part of what the agent must do, guided by
the skill (SKILL.md step 2 / wrapper.md), and part of what this test verifies.

```bash
# input file: 3 variables, 2 compile-time formulas
cat > input.txt <<'EOF'
# perfect gas pressure input
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
V_m3=@{$V_L / 1000}
EOF

# the "simulation": computes P = nRT/V into output.txt
cat > calc.sh <<'EOF'
#!/bin/bash
source $1
python3 -c "print('pressure =', $n_mol*8.314*$T_kelvin/$V_m3)" > output.txt
EOF
```

## 2. Level 1 — skill activation

Ask a question whose answer requires the skill, and check the transcript shows the skill
was actually loaded. `--output-format stream-json --verbose` makes every tool call visible
as a JSON line; `--allowedTools` pre-authorizes the tools so the headless session never
blocks on a permission prompt.

```bash
claude -p "Using the fz skill, find which input variables input.txt contains
and list their names. It uses the default fz parameterization syntax." \
  --output-format stream-json --verbose \
  --max-turns 10 --model "$MODEL" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" < /dev/null > transcript.jsonl

# evidence the skill was used: a Skill tool call on "fz", or SKILL.md being read
grep -q -e '"Skill"' -e 'SKILL.md' transcript.jsonl && echo "PASS: skill used"

# the three variables must appear in the transcript (final answer)
for var in n_mol T_celsius V_L; do
  grep -q "$var" transcript.jsonl || { echo "FAIL: $var not found"; exit 1; }
done
echo "PASS: all variables identified"
```

## 3. Level 2 — implement the wrapper and run a study

The real test of the skill's wrapper guide (`wrapper.md`): the agent must read `calc.sh`,
implement a reusable fz wrapper — model under `.fz/models/`, calculator alias under
`.fz/calculators/` wired to it — and prove it works with a study. 2×2 = 4 cases, physics
known exactly, so the assertions are deterministic even though the agent's reasoning is not.

```bash
claude -p "Using the fz skill, implement a reusable fz wrapper for the simulation in
this directory, following the skill's wrapper implementation guide. The simulation is
launched by 'bash calc.sh <input file>'; the parameterized input file is input.txt;
read calc.sh to see what output it writes (no fz model is provided — define it
yourself). Create the model as .fz/models/PerfectGas.json (id 'PerfectGas') and a
local calculator alias under .fz/calculators/ wired to it. Then test your wrapper by
running a parametric study over T_celsius in [10, 20] and V_L in [1, 2] with n_mol
fixed to 1, and write the results to a file named results.json as a JSON list of
records, one per case, each with keys T_celsius, V_L, n_mol, pressure, status." \
  --output-format stream-json --verbose \
  --max-turns 80 --model "$MODEL" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" < /dev/null > transcript2.jsonl
```

First, the agent's own study must have produced correct artifacts:

```bash
# the file exists and is valid JSON with 4 case records, all done
jq -e 'length == 4 and all(.[]; .status == "done")' results.json \
  && echo "PASS: 4 cases, all done"

# every pressure matches P = nRT/V within 0.1%
jq -e '
  all(.[];
    (8.314 * (.T_celsius + 273.15) / (.V_L / 1000)) as $expected
    | ((.pressure - $expected) / $expected | fabs) < 0.001
  )' results.json && echo "PASS: pressures physically correct"
```

And the wrapper must have the documented structure — a model with an `id` and `output`
parsers, and a calculator alias mapping that id:

```bash
jq -e '.id == "PerfectGas" and (.output | length > 0)' .fz/models/PerfectGas.json \
  && echo "PASS: model structure"
cat .fz/calculators/*.json | jq -es 'any(.[]; .models | has("PerfectGas"))' \
  && echo "PASS: calculator wired to the model"
```

## 4. Test the wrapper yourself

The strongest check: run fzr **through the agent's wrapper** on a parameter point the
agent never computed (n_mol=2, T=30, V=4 — its study fixed n_mol=1). This proves the
wrapper generalizes instead of hardcoding the asked cases. No `--calculators`: the
installed alias is auto-discovered from the model id.

```bash
fzr --input_path input.txt --model PerfectGas \
    --input_variables '{"T_celsius": [30], "V_L": [4], "n_mol": 2}' \
    --results_dir verify_results --format json < /dev/null > verify.json

# expected: P = 2 * 8.314 * 303.15 / 0.004
jq -e '
  .[0].status == "done" and
  ((.[0].pressure - (2 * 8.314 * 303.15 / 0.004)) / (2 * 8.314 * 303.15 / 0.004)
   | fabs) < 0.001' verify.json && echo "PASS: wrapper works on unseen point"
```

## 5. Level 3 — inverse problem with the brent algorithm (fzd)

The last capability the skill teaches: adaptive design of experiments. Given a target
pressure, the agent must find the temperature producing it, using `fzd` with the brent
1D-optimization algorithm — on the wrapper it built in Level 2. The exact answer is
analytic (T = P·V/(nR) − 273.15 ≈ 27.5476 °C for P = 2 500 000), so the check is
deterministic.

Provide the algorithm (as `fz install algorithm brent` would):

```bash
mkdir -p .fz/algorithms
cp "$FZ_REPO/examples/algorithms/brent.py" .fz/algorithms/
```

```bash
claude -p "Using the fz skill, solve this inverse problem with fz's
design-of-experiments tool (fzd) and the installed brent algorithm
(.fz/algorithms/brent.py): for the simulation wrapped by the installed fz model
'PerfectGas' (input file input.txt, runner 'bash calc.sh'), find the temperature
T_celsius in [0;100] at which the pressure equals 2500000, with V_L fixed to 1 and
n_mol fixed to 1. Hint: minimize a squared-difference output expression. The reported
T_celsius must be accurate to within 0.1 degrees C: let the algorithm converge (enough
iterations, small tolerance) and check the achieved pressure against the target before
reporting. When done, write solution.json containing the keys T_celsius (the solution)
and pressure (the pressure reached at that temperature)." \
  --output-format stream-json --verbose \
  --max-turns 80 --model "$MODEL" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" < /dev/null > transcript3.jsonl
```

Check the solution against the analytic answer (0.5 °C tolerance — 5× looser than what
the prompt demands):

```bash
jq -e '
  (2500000 * 0.001 / 8.314 - 273.15) as $t_exact
  | ((.T_celsius - $t_exact) | fabs) < 0.5
    and (((.pressure - 2500000) / 2500000) | fabs) < 0.01' solution.json \
  && echo "PASS: inverse problem solved"
```

## 6. Clean up

```bash
cd / && rm -rf "$SANDBOX"
```

## Notes

- **Assert on artifacts, not prose**: the agent's wording varies between runs; the
  existence and numerical content of `results.json` (and the case directories fz creates
  under `results/`) do not.
- Expect ~10 s for Level 1, ~1–3 min for Level 2 (it has to inspect calc.sh, write the
  model and calculator alias, and run the study), and ~3–15 min for Level 3 (iterative
  optimization with convergence checking) with haiku; a few cents of tokens.
- If Level 2 fails, look inside the sandbox before deleting it: `results/*/out.txt`,
  `err.txt` and `log.txt` show what each fz case actually did, and `transcript2.jsonl`
  shows what the agent tried.
- The pytest version (`tests/test_skill_e2e.py`) automates exactly this, probe included:
  `venv/bin/python -m pytest tests/test_skill_e2e.py -v`.
