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
    (SKILL.md step 2 / code-wrapper.md).
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
        cmd, capture_output=True, text=True, timeout=1800, cwd=cwd, env=env
    )


def expected_pressure(n_mol, t_celsius, v_l):
    return n_mol * GAS_CONSTANT * (t_celsius + 273.15) / (v_l / 1000.0)


def install_wrapper(sandbox: Path):
    """Pre-install a working wrapper (as level 2 produces) plus the brent algorithm"""
    (sandbox / ".fz/models").mkdir(parents=True)
    (sandbox / ".fz/models/PerfectGas.json").write_text(json.dumps({
        "id": "PerfectGas",
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#",
        "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"},
    }))
    (sandbox / ".fz/calculators").mkdir(parents=True)
    (sandbox / ".fz/calculators/localhost_PerfectGas.json").write_text(json.dumps({
        "uri": "sh://",
        "models": {"PerfectGas": "bash calc.sh"},
    }))
    (sandbox / ".fz/algorithms").mkdir(parents=True)
    shutil.copy(REPO / "examples/algorithms/brent.py", sandbox / ".fz/algorithms/brent.py")


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
    """Level 2: the agent implements a reusable fz wrapper and we certify it.

    The agent must follow the skill's wrapper guide (code-wrapper.md): create the
    model under .fz/models/ and a calculator alias under .fz/calculators/,
    then verify them per the guide's definition of done. We assert the wrapper
    structure AND run fzr ourselves through it on a parameter point the agent
    never used — only a wrapper certified here is worth relying on for actual
    studies (levels 3-4 run on a stable, pre-installed equivalent).
    """
    setup_sandbox(tmp_path)
    result = run_claude(
        "Using the fz skill, implement a reusable fz wrapper for the simulation in "
        "this directory, following the skill's wrapper implementation guide. The "
        "simulation is launched by 'bash calc.sh <input file>'; the parameterized "
        "input file is input.txt; read calc.sh to see what output it writes (no fz "
        "model is provided — define it yourself). Create the model as "
        ".fz/models/PerfectGas.json (id 'PerfectGas') and a local calculator alias "
        "under .fz/calculators/ wired to it. Verify your wrapper per the guide's "
        "definition of done (fz list --check, and a successful single-case run "
        "without any --calculators argument) before declaring it finished.",
        max_turns=60,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"claude failed: {result.stderr[-2000:]}"

    # 1. The wrapper has the documented structure: a model with an id and
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

    # 2. The wrapper actually works, independently of the agent's own run:
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


def test_skill_parametric_study(tmp_path, claude_ready):
    """Level 3: parametric study on a stable, pre-installed wrapper.

    Wrapper authoring is level 2's job; here the agent must only USE the
    installed wrapper correctly: factorial study, results collected and
    exported. Assertions are on the artifact, physics known exactly.
    """
    setup_sandbox(tmp_path)
    install_wrapper(tmp_path)
    cases = [(10, 1), (10, 2), (20, 1), (20, 2)]
    result = run_claude(
        "Using the fz skill, run a parametric study with the installed fz wrapper "
        "(model alias 'PerfectGas'; the parameterized input file is input.txt). "
        "Run all combinations of T_celsius in [10, 20] and V_L in [1, 2] with "
        "n_mol fixed to 1, and write the results to a file named results.json as "
        "a JSON list of records, one per case, each with keys T_celsius, V_L, "
        "n_mol, pressure, status.",
        max_turns=40,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"claude failed: {result.stderr[-2000:]}"

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


def test_skill_inverse_problem_brent(tmp_path, claude_ready):
    """Level 4: inverse problem via fzd + brent — given a target pressure, find T.

    Runs on the same stable, pre-installed wrapper as level 3 (authoring is
    level 2's job); what is tested here is using fz's design-of-experiments
    tool with an installed algorithm to solve an inversion. The exact answer
    is known analytically, so the assertion is deterministic.
    """
    setup_sandbox(tmp_path)
    install_wrapper(tmp_path)
    target = 2_500_000.0
    t_exact = target * (1 / 1000.0) / GAS_CONSTANT - 273.15  # ~27.55 °C

    result = run_claude(
        "Using the fz skill, solve this inverse problem with fz's design-of-experiments "
        "tool (fzd) and the installed brent algorithm (.fz/algorithms/brent.py): for the "
        "simulation wrapped by the installed fz model 'PerfectGas' (input file input.txt, "
        f"runner 'bash calc.sh'), find the temperature T_celsius in [0;100] at which the "
        f"pressure equals {target:.0f}, with V_L fixed to 1 and n_mol fixed to 1. "
        "Hint: minimize a squared-difference output expression. The reported "
        "T_celsius must be accurate to within 0.1 degrees C: let the algorithm "
        "converge (enough iterations, small tolerance) and check the achieved "
        "pressure against the target before reporting. When done, write "
        "solution.json containing the keys T_celsius (the solution) and pressure "
        "(the pressure reached at that temperature).",
        max_turns=80,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"claude failed: {result.stderr[-2000:]}"

    solution_file = tmp_path / "solution.json"
    assert solution_file.exists(), "agent did not produce solution.json"
    solution = json.loads(solution_file.read_text(encoding="utf-8"))

    t_found = float(solution["T_celsius"])
    assert abs(t_found - t_exact) < 0.5, (
        f"T_celsius {t_found} not within 0.5°C of exact solution {t_exact:.4f}"
    )
    # physics consistency: the pressure at the reported T must hit the target
    p_at_t = expected_pressure(1, t_found, 1)
    assert abs(p_at_t - target) / target < 0.005
    # and the agent's reported pressure must be the actually computed one
    assert abs(float(solution["pressure"]) - target) / target < 0.01
