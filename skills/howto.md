# Using the fz skill with an AI coding agent

The [`fz/`](fz/) directory contains an [Agent Skill](https://agentskills.io) that teaches
AI coding agents (Claude Code, and other agents supporting the skills format) how to wrap
a simulation code with fz and run parametric studies. This page shows how to install and
use it.

## 1. Install the skill

**As a Claude Code plugin** (recommended — two slash-commands, auto-updating):

```
/plugin marketplace add Funz/fz
/plugin install fz@funz
```

**User-level copy** (available in all your projects):

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/fz/skills/fz ~/.claude/skills/
```

Or symlink it so it tracks your fz checkout:

```bash
ln -s /path/to/fz/skills/fz ~/.claude/skills/fz
```

**Project-level** (shared with anyone working in that project):

```bash
cd ~/my-simulation-project
mkdir -p .claude/skills
cp -r /path/to/fz/skills/fz .claude/skills/
```

> Note: don't install project-level *inside the fz repository itself* — nested directories
> resolve to the enclosing repo, not your sandbox. User-level is the simplest reliable
> option.

## 2. Go to a project with a simulation to wrap

Say you have a thermal solver:

```
~/work/cooling-study/
├── solver.sh          # reads a config file, writes report.txt
└── config.ini         # contains: thickness = 2.5, flow_rate = 10, ...
```

## 3. Start the agent and describe the goal

```bash
cd ~/work/cooling-study
claude
```

Then just ask — no need to mention the skill explicitly:

> Wrap solver.sh with fz and run a parametric study over thickness = 1, 2, 5 mm and
> flow_rate = 5, 10, 20 — extract the max temperature from report.txt and give me the
> results as a table.

The skill triggers on phrases like "parametric study" or "wrap my simulation", and the
agent then follows the workflow it teaches: parameterize `config.ini` with
`$thickness`/`$flow_rate`, write a model JSON with an output parser, verify step by step
(`fzi` → `fzc` → one manual solver run → `fzo`), and only then launch the full 9-case
`fzr` — so a typo'd output command or a solver path issue is caught on one cheap case
instead of a failed batch.

## More things you can ask

Remote execution:

> Run the same study on the cluster over SSH (user@cluster.edu, the solver is at
> /opt/solver/solver.sh), 4 cases in parallel.

Incremental extension (reuses the cache, only computes new cases):

> Extend the previous study with thickness = 10 too, reusing the results we already have.

Optimization (uses `fzd` with an adaptive algorithm):

> Find the thickness that minimizes max temperature, between 1 and 10 mm.

## Headless / scripted usage

The skill also works non-interactively, e.g. from a script or CI:

```bash
claude -p "Using the fz skill, run a parametric study of the simulation launched by
'bash calc.sh' over T_celsius in [10, 20] and V_L in [1, 2], and write the results
to results.json" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill" --max-turns 40
```

`tests/test_skill_e2e.py` in the fz repository does exactly this against a miniature
simulation and asserts the produced results are physically correct — read it for a
complete, working reference, or follow [test_skill_e2e.md](test_skill_e2e.md) for the
same test as explained, copy-pasteable shell commands.

## What's in the skill

- [fz/SKILL.md](fz/SKILL.md) — the workflow guide loaded by the agent when relevant
- [fz/reference.md](fz/reference.md) — condensed API/CLI reference and JSON schemas
- [fz/algorithms.md](fz/algorithms.md) — how to write custom `fzd` algorithms
