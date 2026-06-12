# fz — contributor guide

fz (PyPI: `funz-fz`) is a parametric scientific computing framework: it wraps simulation
codes to run parameter studies locally, over SSH, or on SLURM. Python rewrite of Java Funz.

## Layout

- `fz/` — the package. `core.py` (public functions `fzi`/`fzc`/`fzo`/`fzr`/`fzl`/`fzd`),
  `cli.py` (entry points `fz`, `fzi`, ... defined in pyproject.toml), `runners.py`
  (sh/ssh/slurm/funz/cache calculators), `interpreter.py` (variable/formula parsing,
  Python and R evaluation), `io.py`, `config.py` (env vars), `installer.py` (`fz install`).
- `tests/` — pytest suite. `context/` — modular user docs. `skills/fz/` — Agent Skill
  (workflow + condensed reference). `examples/` — example models, algorithms, notebooks.
- `fz/_version.py` is stamped by CI (`scripts/stamp_version.py`) — never edit manually.

## Setup and tests

```bash
pip install -e ".[dev]"
pytest tests/ -x                      # full local suite
pytest tests/test_core.py -k name     # single test
```

- `pytest.ini` uses `--strict-markers`: register any new marker there. Existing markers:
  `slow`, `integration`, `manual`, `requires_docker`, `requires_omc`, `requires_ssh`,
  `requires_paramiko`, `requires_claude`.
- The agent skill is tested: `tests/test_skill_static.py` (always runs; checks the skill's
  claims — CLI flags, env vars, defaults, signatures — against the code, so CLI changes can
  fail it legitimately: update `skills/fz/` accordingly) and `tests/test_skill_e2e.py`
  (headless Claude Code; skipped unless the `claude` CLI is installed and a cheap probe
  shows it can answer — works with `ANTHROPIC_API_KEY` or CLI login; `FZ_SKILL_E2E=0`
  forces a skip).
- An autouse fixture in `tests/conftest.py` runs **every test in a fresh temp directory
  under `./tmp`** and restores the cwd afterwards. Don't rely on repo-relative paths
  inside tests; reference test data via absolute paths or fixtures.
- Tests create real subprocesses (bash) — fz requires bash everywhere, including Windows
  (MSYS2/Git Bash, located via `FZ_SHELL_PATH`).

## R / rpy2 caveat (recurring CI trap)

On some CI images, `import rpy2` succeeds but `import rpy2.robjects` fails with
`ffi.error` (R/rpy2 version mismatch). Availability guards must therefore:

```python
try:
    import rpy2
    import rpy2.robjects
    R_AVAILABLE = True
except Exception:        # NOT just ImportError
    R_AVAILABLE = False
```

This pattern is applied across test files and `fz/interpreter.py`; keep it when adding
R-dependent code or tests.

## CI

- `ci.yml` — main matrix (Linux/macOS/Windows × Python 3.9–3.13, plus 3.14-dev). It
  excludes the example/SSH/funz-protocol test files (see the `pytest --ignore` list in
  the workflow); those run in dedicated workflows: `ssh-localhost.yml`,
  `slurm-localhost.yml`, `cli-tests.yml`, `examples.yml`, `funz-calculator.yml`.
- Some workflows skip branches named `claude/*`.
- Releases: `release.yml` builds wheels and publishes `funz-fz` to PyPI on tag.

## Conventions

- Public API surface is exported in `fz/__init__.py` (`__all__`); keep CLI (`cli.py`) and
  Python signatures consistent — every core function has a CLI twin with the same
  semantics, and CLI output must stay parseable with `--format json`.
- When changing the public API or CLI flags, update **all three** doc surfaces:
  `README.md`, `context/`, and `skills/fz/reference.md` (the agent skill ships to users).
- Default values live in `fz/config.py` and are env-overridable (`FZ_LOG_LEVEL`,
  `FZ_MAX_WORKERS`, `FZ_MAX_RETRIES` (default 5), `FZ_SSH_*`, `FZ_SHELL_PATH`).
- User-facing release notes go in `NEWS.md`.
