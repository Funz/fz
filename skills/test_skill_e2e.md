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

## 3. Level 2 — end-to-end parametric study

Give the agent the full task and let it choose its path; we only check the artifact it
must produce. The agent has to read `calc.sh`, define the fz model itself (variable
syntax + an output command parsing `output.txt`), and only then run the study. 2×2 = 4
cases, physics known exactly, so the assertions are deterministic even though the agent's
reasoning is not.

```bash
claude -p "Using the fz skill, wrap the simulation in this directory with fz and run a
parametric study. The simulation is launched by 'bash calc.sh <input file>'; the
parameterized input file is input.txt; read calc.sh to see what output it writes and
define the fz model yourself (no model is provided). Run the study over
T_celsius in [10, 20] and V_L in [1, 2] with n_mol fixed to 1, then write the results
to a file named results.json as a JSON list of records, one per case, each with keys
T_celsius, V_L, n_mol, pressure, status." \
  --output-format stream-json --verbose \
  --max-turns 40 --model "$MODEL" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" < /dev/null > transcript2.jsonl
```

Now the artifact checks — the same three as the pytest version:

```bash
# 1. the file exists and is valid JSON with 4 case records, all done
jq -e 'length == 4 and all(.[]; .status == "done")' results.json \
  && echo "PASS: 4 cases, all done"

# 2. every pressure matches P = nRT/V within 0.1%
jq -e '
  all(.[];
    (8.314 * (.T_celsius + 273.15) / (.V_L / 1000)) as $expected
    | ((.pressure - $expected) / $expected | fabs) < 0.001
  )' results.json && echo "PASS: pressures physically correct"
```

(No `jq`? The same check in python:
`python3 -c "import json; rs=json.load(open('results.json')); assert len(rs)==4 and all(r['status']=='done' and abs(r['pressure']-8.314*(r['T_celsius']+273.15)/(r['V_L']/1000))/ (8.314*(r['T_celsius']+273.15)/(r['V_L']/1000)) < 1e-3 for r in rs); print('PASS')"`)

## 4. Clean up

```bash
cd / && rm -rf "$SANDBOX"
```

## Notes

- **Assert on artifacts, not prose**: the agent's wording varies between runs; the
  existence and numerical content of `results.json` (and the case directories fz creates
  under `results/`) do not.
- Expect ~10 s for Level 1 and ~60 s for Level 2 with haiku (it also has to inspect
  calc.sh and write the model); a few cents of tokens.
- If Level 2 fails, look inside the sandbox before deleting it: `results/*/out.txt`,
  `err.txt` and `log.txt` show what each fz case actually did, and `transcript2.jsonl`
  shows what the agent tried.
- The pytest version (`tests/test_skill_e2e.py`) automates exactly this, probe included:
  `venv/bin/python -m pytest tests/test_skill_e2e.py -v`.
