"""
End-to-end tests of the agent skill in skills/fz/, driven by the claude CLI.

These tests launch a headless Claude Code session in a sandbox containing the
skill and a small deterministic simulation (perfect gas pressure), then assert
on the artifacts the agent leaves behind — never on its prose.

They are skipped when the `claude` CLI is not installed or not functional: a cheap
one-shot probe (one tiny haiku call) checks that claude can actually answer — it works
with ANTHROPIC_API_KEY as well as with the CLI's own login credentials. Set
FZ_SKILL_E2E=0 to skip unconditionally (e.g. to avoid token usage in local full-suite
runs).

Cost/model can be tuned with FZ_SKILL_TEST_MODEL (default: claude-haiku-4-5).
"""
import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL_SRC = REPO / "skills" / "fz"

CLAUDE = shutil.which("claude")
MODEL = os.environ.get("FZ_SKILL_TEST_MODEL", "claude-haiku-4-5")

pytestmark = [
    pytest.mark.requires_claude,
    pytest.mark.slow,
    pytest.mark.skipif(CLAUDE is None, reason="claude CLI not installed"),
    pytest.mark.skipif(
        os.environ.get("FZ_SKILL_E2E") == "0", reason="skill e2e disabled (FZ_SKILL_E2E=0)"
    ),
]


@functools.lru_cache(maxsize=1)
def _claude_probe():
    """One-shot functional check of the claude CLI (cached for the session).

    Runs lazily (from a fixture, not at import) so collecting or deselecting
    these tests never triggers an API call.
    """
    try:
        result = subprocess.run(
            [CLAUDE, "-p", "Reply with exactly: OK", "--model", MODEL, "--max-turns", "1"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        return False, f"claude probe failed to run: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-300:]
        return False, f"claude probe exited {result.returncode}: {detail}"
    return True, ""


@pytest.fixture
def claude_ready():
    ok, reason = _claude_probe()
    if not ok:
        pytest.skip(reason)

GAS_CONSTANT = 8.314


def setup_sandbox(sandbox: Path):
    """Populate a project dir with the skill and a tiny simulation.

    The sandbox must live outside the fz repository (pytest's tmp_path does),
    otherwise the spawned claude session resolves the enclosing fz repo as its
    project and ignores the sandbox's .claude/skills.

    Deliberately NO fz model is provided: defining it (variable syntax, output
    parsing command) is part of what the agent must do, guided by the skill
    (SKILL.md step 2 / wrapper.md).
    """
    shutil.copytree(SKILL_SRC, sandbox / ".claude/skills/fz")

    (sandbox / "input.txt").write_text(
        "# perfect gas pressure input\n"
        "n_mol=$n_mol\n"
        "T_kelvin=@{$T_celsius + 273.15}\n"
        "V_m3=@{$V_L / 1000}\n"
    )
    (sandbox / "calc.sh").write_text(
        "#!/bin/bash\n"
        "source $1\n"
        'python3 -c "print(\'pressure =\', '
        f'$n_mol*{GAS_CONSTANT}*$T_kelvin/$V_m3)" > output.txt\n'
    )


def run_claude(prompt, max_turns, cwd):
    # Make the fz CLI visible to the spawned session even from a non-activated venv
    env = os.environ.copy()
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
    cmd = [
        CLAUDE, "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns),
        "--model", MODEL,
        "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,Skill",
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=900, cwd=cwd, env=env
    )


def expected_pressure(n_mol, t_celsius, v_l):
    return n_mol * GAS_CONSTANT * (t_celsius + 273.15) / (v_l / 1000.0)


def test_skill_activation(tmp_path, claude_ready):
    """Level 1: the skill is discovered and used for an fz question"""
    setup_sandbox(tmp_path)
    result = run_claude(
        "Using the fz skill, find which input variables input.txt contains "
        "and list their names. It uses the default fz parameterization syntax.",
        max_turns=10,
        cwd=tmp_path,
    )
    transcript = result.stdout
    assert result.returncode == 0, f"claude failed: {result.stderr[-2000:]}"

    # The skill must actually be loaded (Skill tool call or SKILL.md read)
    used_skill = ('"fz"' in transcript and '"Skill"' in transcript) or "SKILL.md" in transcript
    assert used_skill, "no evidence the fz skill was used in the transcript"

    # The variables must be identified in the final answer
    for var in ("n_mol", "T_celsius", "V_L"):
        assert var in transcript, f"variable {var} not found in transcript"


def test_skill_implement_wrapper(tmp_path, claude_ready, monkeypatch):
    """Level 2: the agent implements a reusable fz wrapper and we test it.

    The agent must follow the skill's wrapper guide (wrapper.md): create the
    model under .fz/models/ and a calculator alias under .fz/calculators/,
    verify them, and run a study. We then assert on its artifacts AND run fzr
    ourselves through the wrapper on a parameter point the agent never used —
    proving the wrapper generalizes instead of hardcoding the asked cases.
    """
    setup_sandbox(tmp_path)
    cases = [(10, 1), (10, 2), (20, 1), (20, 2)]
    result = run_claude(
        "Using the fz skill, implement a reusable fz wrapper for the simulation in "
        "this directory, following the skill's wrapper implementation guide. The "
        "simulation is launched by 'bash calc.sh <input file>'; the parameterized "
        "input file is input.txt; read calc.sh to see what output it writes (no fz "
        "model is provided — define it yourself). Create the model as "
        ".fz/models/PerfectGas.json (id 'PerfectGas') and a local calculator alias "
        "under .fz/calculators/ wired to it. Then test your wrapper by running a "
        "parametric study over T_celsius in [10, 20] and V_L in [1, 2] with n_mol "
        "fixed to 1, and write the results to a file named results.json as a JSON "
        "list of records, one per case, each with keys T_celsius, V_L, n_mol, "
        "pressure, status.",
        max_turns=80,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"claude failed: {result.stderr[-2000:]}"

    # 1. The agent's own study produced correct artifacts
    results_file = tmp_path / "results.json"
    assert results_file.exists(), "agent did not produce results.json"
    records = json.loads(results_file.read_text(encoding="utf-8"))
    assert len(records) == len(cases), f"expected {len(cases)} cases, got {len(records)}"

    by_case = {(round(float(r["T_celsius"])), round(float(r["V_L"]))): r for r in records}
    for t_celsius, v_l in cases:
        assert (t_celsius, v_l) in by_case, f"case T={t_celsius}, V={v_l} missing"
        rec = by_case[(t_celsius, v_l)]
        assert rec["status"] == "done"
        expected = expected_pressure(1, t_celsius, v_l)
        assert abs(float(rec["pressure"]) - expected) / expected < 1e-3, (
            f"case T={t_celsius}, V={v_l}: pressure {rec['pressure']} != {expected}"
        )

    # 2. The wrapper has the documented structure: a model with an id and
    #    output parsers, and a calculator alias wired to that id
    model_files = sorted((tmp_path / ".fz" / "models").glob("*.json"))
    assert model_files, "agent did not create a model under .fz/models/"
    model = json.loads(model_files[0].read_text(encoding="utf-8"))
    assert model.get("id"), "wrapper model has no 'id' (required to bind calculators)"
    assert model.get("output"), "wrapper model has no 'output' parsers"

    calc_files = sorted((tmp_path / ".fz" / "calculators").glob("*.json"))
    wired = [
        c for c in calc_files
        if model["id"] in json.loads(c.read_text(encoding="utf-8")).get("models", {})
    ]
    assert wired, f"no calculator alias maps model id '{model['id']}'"

    # 3. The wrapper actually works, independently of the agent's own run:
    #    fzr through the installed alias (calculator auto-discovered) on a
    #    parameter point the agent never computed
    import fz

    monkeypatch.chdir(tmp_path)
    verify = fz.fzr(
        "input.txt",
        {"T_celsius": [30], "V_L": [4], "n_mol": 2},
        model_files[0].stem,
        results_dir="verify_results",
    )
    assert list(verify["status"]) == ["done"], f"wrapper verify run failed: {verify}"
    pressure = float(list(verify["pressure"])[0])
    expected = expected_pressure(2, 30, 4)
    assert abs(pressure - expected) / expected < 1e-3, (
        f"wrapper verify run: pressure {pressure} != {expected}"
    )
