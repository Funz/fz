# FZ - Parametric Scientific Computing Framework

[![CI](https://github.com/Funz/fz/workflows/CI/badge.svg)](https://github.com/Funz/fz/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Version](https://img.shields.io/badge/version-1.2-blue.svg)](https://github.com/Funz/fz/releases)

FZ wraps a simulation code driven by text input files and turns it into a parametric
study: it substitutes variable values into input templates, runs every case (locally, over
SSH, on SLURM or a Funz server, in parallel, with caching and retries) and returns the
results as a pandas DataFrame.

- [Features](#features) · [Installation](#installation) · [Quick Start](#quick-start) ·
  [The six functions](#the-six-functions) · [Key concepts](#key-concepts) ·
  [Configuration](#configuration) · [Threat Model](#threat-model) ·
  [AI agents and MCP](#using-fz-with-ai-coding-agents) · [Documentation](#documentation)

## Features

- **Parametric studies**: factorial designs (dict, Cartesian product) or explicit cases (DataFrame).
- **Templates with formulas**: `$var` substitution and `@{...}` Python or R expressions in any text input file.
- **Local, SSH, SLURM and Funz execution**, with automatic file transfer and protocol-specific error reports.
- **Parallel execution** over several calculators, **retries** on another calculator, **caching** of previous results.
- **Adaptive design of experiments** (`fzd`) with pluggable algorithms.
- **Traceability**: one `manifest.json` (and an RO-Crate) per campaign.
- **Interrupt handling**: Ctrl+C stops cleanly and keeps partial results.
- Linux, macOS and Windows (MSYS2/Git Bash); requires `bash`.

## Installation

```bash
pip install funz-fz          # or: pipx install funz-fz  (isolated CLI install)
pip install -e .             # from a clone of https://github.com/Funz/fz
```

Required dependencies (`paramiko`, `pandas`, `charset-normalizer`) are installed
automatically. Optional extras: `funz-fz[r]` (R formulas, needs R), `funz-fz[mcp]`
(MCP server, Python >= 3.10). Python 3.9 to 3.14 are supported. More options:
[Installation](doc/guide/installation.md).

## Quick Start

A complete parametric study (ideal gas pressure, 4 × 3 = 12 cases).

`input.txt` (the template; `$var` are variables, `@{...}` formulas, `#@` preprocessing lines):

```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@{L_to_m3($V_L)}
```

`PerfectGazPressure.sh` (the calculation; receives the compiled input as `$1`; make it executable with `chmod +x`):

```bash
#!/bin/bash
source $1
sleep 5 # simulate a calculation time
echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
```

`run_study.py`:

```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
        # shell-free alternative: "python://grep(r'pressure = (\\S+)', 'output.txt')"
    },
}

input_variables = {
    "T_celsius": [10, 20, 30, 40],  # 4 temperatures
    "V_L": [1, 2, 5],               # 3 volumes
    "n_mol": 1.0,                   # fixed amount
}

results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="results",
)
print(results)
```

```
   T_celsius  V_L  n_mol     pressure status calculator       error command
0         10  1.0    1.0  235358.1200   done     sh://        None    bash...
1         10  2.0    1.0  117679.0600   done     sh://        None    bash...
...
```

Each case runs in its own directory under `results/` with its compiled input, `out.txt`,
`err.txt` and `log.txt`. More examples: [`examples/examples.md`](examples/examples.md)
and the notebooks in [`examples/`](examples/). Extended version (R formulas, other output
extractors): [Quick Start](doc/guide/quick-start.md).

## The six functions

Each function has a CLI twin with the same semantics (`fz <name>`, or `fzi`, `fzc`, ...);
CLI output is parseable with `--format json`.

| Function | Purpose |
|----------|---------|
| `fzi` | **I**nspect input files: list the variables (and defaults) |
| `fzc` | **C**ompile input files by substituting variable values |
| `fzo` | Parse **o**utput files of finished calculations |
| `fzr` | **R**un a complete parametric study, end to end |
| `fzd` | Iterative **d**esign of experiments with adaptive algorithms |
| `fzl` | **L**ist and validate installed models and calculators |

Full reference: [Python API](doc/guide/python-api.md) and [CLI](doc/guide/cli-usage.md).
`fz install <name|url>` installs models and algorithms ([details](doc/guide/installing-plugins.md)).

## Key concepts

**Model**: a dict or JSON file (or installed alias) telling fz how to read templates
(`varprefix`, `formulaprefix`, `delim`, `commentline`) and how to extract results
(`output`: shell commands, or shell-free `python://`, `jq://`, `yq://`, `xpath://`).
See [Model definition](doc/guide/model-definition.md).

**Calculator**: where and how a case runs, given as a URI (or an installed alias):

| URI | Runs on |
|-----|---------|
| `sh://command` | local shell |
| `ssh://user@host[:port]/command` | remote host over SSH (key authentication recommended) |
| `slurm://[user@host:]:partition/command` | SLURM (`srun`); `slurm-array://` batches cases in a job array (local only) |
| `funz://host:port/Code` | legacy Java Funz server |
| `cache://path` | reuse results of a previous run (matched by input hash and, if declared, code identity) |

Pass a list to spread cases over several calculators. See [Calculator types](doc/guide/calculator-types.md).

**Execution**: cases run in parallel with automatic load balancing, failed cases are
retried on another calculator, `cache://` resumes an interrupted or extended study, and
Ctrl+C stops gracefully. See [Advanced features](doc/guide/advanced-features.md) and
[Interrupt handling](doc/guide/interrupt-handling.md).

## Configuration

Main environment variables (all optional; full list in [Configuration](doc/guide/configuration.md)):

| Variable | Meaning |
|----------|---------|
| `FZ_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `FZ_MAX_WORKERS` | maximum parallel cases |
| `FZ_MAX_RETRIES` | attempts per failed case (default 5) |
| `FZ_RUN_TIMEOUT` | per-calculation timeout in seconds (default 3600 for `sh://` and `funz://`; unlimited for `ssh://` and `slurm://` unless set) |
| `FZ_SHELL_PATH` | directories searched for shell tools (mainly Windows/MSYS2) |
| `FZ_CACHE_STRICT` | `1`: refuse `cache://` matches whose code identity cannot be verified |

## Threat Model

fz does not sandbox the models, algorithms, or calculators it runs. This is a
deliberate, current choice, not an oversight to be fixed later: any isolation
(e.g. restricting formulas to a safe subset) would break real, existing usage
of this repository (`#@import math` and other multi-line preprocessing
directives, multi-line Python/R formulas, output-parsing commands that shell
out, `python -c` calculator invocations). Isolation is deferred until there is
a concrete need for it (network-facing exposure, running third-party models
you did not author) rather than added speculatively.

Concretely, everything below runs as code, with your user's privileges, when
you call `fzi`/`fzc`/`fzr`/`fzd`:

- **Template preprocessing lines** (`#@...`) and **formulas** (`@{...}`) in
  input files are evaluated (Python `eval`/`exec`, or R).
- **Output-parsing commands** declared in a model's `"output"` (e.g. a shell
  pipeline, or a `python://`/`python -c` snippet) are executed to extract
  results.
- **Calculator commands** (`sh://`, `ssh://`, ...) run whatever command string
  you or a model/calculator alias declare.
- **`version_cmd`** of a calculator alias (used to resolve `code_id` for
  `cache://`, see [Calculator Aliases](doc/guide/calculator-types.md#calculator-aliases)) is a shell command run by fz itself,
  locally for `sh://` or on the remote host for `ssh://`, when a campaign
  resolves its calculators (once per calculator and process, before any case
  runs). It carries the same trust requirement as the calculator command.

**Don't run a model, algorithm, or calculator alias from a source you don't
trust** — it is equivalent to running a shell script from that source.
`fz install <url>` (see [Installing Plugins](doc/guide/installing-plugins.md)) prints a one-time
reminder of this when installing from a network source. The same applies to
`fz-mcp` (see [MCP server](#mcp-server-fz-mcp) below): giving an AI agent access to it in its
default (trusted) mode is equivalent to giving that agent shell access.


## Using fz with AI Coding Agents

An [Agent Skill](https://agentskills.io) is bundled in [`skills/fz/`](skills/fz/): it teaches
coding agents (Claude Code and other agents supporting the skills format) the fz workflow.
In Claude Code:

```
/plugin marketplace add Funz/fz
/plugin install fz@funz
```

or copy `skills/fz/` into `.claude/skills/` (project) or `~/.claude/skills/` (user). The
skill holds the workflow ([`skills/fz/SKILL.md`](skills/fz/SKILL.md)), a condensed
API/CLI reference ([`skills/fz/reference.md`](skills/fz/reference.md)) and wrapper guides.
Walkthrough with example prompts: [`skills/howto.md`](skills/howto.md); plugin slash commands
and manual install: [AI agents](doc/guide/ai-agents.md).

### MCP server (`fz-mcp`)

**Trusted mode (the default) is equivalent to giving the agent shell access** (see
[Threat Model](#threat-model) and [`doc/mcp-server.md`](doc/mcp-server.md)).

`fz-mcp` exposes `fzi`, `fzc`, `fzr`, `fzo` and `fzl` as [MCP](https://modelcontextprotocol.io)
tools over `stdio` (the only transport by default). Install with `pip install 'funz-fz[mcp]'`
(Python >= 3.10), then e.g. `claude mcp add fz -- fz-mcp`. File paths are confined to
`FZ_MCP_ROOT` (default: working directory). `FZ_MCP_TRUSTED=0` restricts models and
calculators to installed aliases; it does not sandbox formula evaluation inside fz.
Details: [MCP server](doc/guide/mcp-server.md).

## Documentation

- **Guides** (full reference, split by topic): [`doc/guide/`](doc/guide/) - CLI, Python API,
  model definition, calculator types, advanced features, configuration, troubleshooting,
  complete examples, custom `fzd` algorithms, plugins, development, breaking changes.
- **Modular reference**: [`doc/INDEX.md`](doc/INDEX.md) (overview, syntax guide, formulas,
  caching, SLURM architecture, Funz protocol, shell path, MCP).
- **Examples**: [`examples/examples.md`](examples/examples.md), [`examples/`](examples/) notebooks and scripts.
- **All resources and test examples**: [Resources](doc/guide/resources.md).
- **Release notes**: [`NEWS.md`](NEWS.md).

## Development and contributing

```bash
pip install -e ".[dev]"
pytest tests/ -x
```

See [Development](doc/guide/development.md) for the test layout and CI. Contributions
welcome: fork, create a feature branch, add tests, make sure they pass, open a pull request.

## Citation

If you use FZ in your research, please cite it (see [`CITATION.cff`](CITATION.cff)):

```bibtex
@software{fz,
  title = {FZ: Parametric Scientific Computing Framework},
  designers = {[Yann Richet]},
  authors = {[Claude Sonnet, Yann Richet]},
  year = {2025},
  url = {https://github.com/Funz/fz}
}
```

## License and support

BSD 3-Clause License, see [`LICENSE`](LICENSE). Issues: https://github.com/Funz/fz/issues ·
Repository: https://github.com/Funz/fz
