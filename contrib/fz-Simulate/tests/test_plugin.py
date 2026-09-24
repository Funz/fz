"""Tests for the fz-Simulate wrapper (models Simulate and CasmoSimulate).

They run the fz CLI as a user would, without the Studsvik codes:
- tests/mock/{cas5,cmslink,sim5} stand in for the launchers. The mocks propagate
  data along the chain (CASMO k-inf -> library -> SIMULATE boron), so that the
  tests check that a CASMO parameter really reaches the SIMULATE result;
- tests/fixtures/<case>/ holds SIMULATE output files plus an expected.json,
  checked with fzo. Add real SIMULATE output excerpts there to validate parsers.

Run from the repository root:  pytest tests/
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FZ = REPO / ".fz"
MOCK = REPO / "tests" / "mock"
FIXTURES = REPO / "tests" / "fixtures"
SIM_EXAMPLE = REPO / "examples" / "Simulate" / "simulate.inp"
CHAIN_EXAMPLE = REPO / "examples" / "CasmoSimulate"


def fz_cli(tool, *args, env=None, check=True):
    """Run an fz CLI tool and return its decoded JSON output (None for fzc)."""
    fmt = [] if tool == "fzc" else ["--format", "json"]
    proc = subprocess.run([tool, *args, *fmt], capture_output=True, text=True, env=env)
    if check:
        assert proc.returncode == 0, f"{tool} failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout) if fmt else None


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A scratch project with the wrapper's .fz/ installed, as `fz install` would."""
    shutil.copytree(FZ, tmp_path / ".fz")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def mock_env(**extra):
    env = dict(os.environ, FZ_MAX_RETRIES="1", CASMO_CMD=str(MOCK / "cas5"),
               CMSLINK_CMD=str(MOCK / "cmslink"), SIMULATE_CMD=str(MOCK / "sim5"))
    for var in ("CASMO_PATH", "CMSLINK_PATH", "SIMULATE_PATH"):
        env.pop(var, None)
    env.update(extra)
    return env


# --- static checks -------------------------------------------------------------

@pytest.mark.parametrize("model_id", ["Simulate", "CasmoSimulate"])
def test_model_json(model_id):
    model = json.loads((FZ / "models" / f"{model_id}.json").read_text())
    assert model["id"] == model_id
    assert model["commentline"] == "*"
    for key in ("keff", "boron", "cycle_exposure", "fq", "fdh"):
        assert key in model["output"]


def test_alias_binds_both_models():
    alias = json.loads((FZ / "calculators" / "localhost_Simulate.json").read_text())
    assert alias["uri"] == "sh://"
    assert set(alias["models"]) == {"Simulate", "CasmoSimulate"}
    for command in alias["models"].values():
        script = REPO / command.split()[-1]
        assert os.access(script, os.X_OK), script
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


# --- input side ----------------------------------------------------------------

def test_fzi_simulate(project):
    found = fz_cli("fzi", "--input_path", str(SIM_EXAMPLE), "--model", "Simulate")
    assert found == {"boron_guess": 1200, "core_flow": 100.0, "core_power": 100.0,
                     "cycle_length": 18.0}


def test_fzi_chain_sees_variables_of_all_decks(project):
    found = fz_cli("fzi", "--input_path", str(CHAIN_EXAMPLE), "--model", "CasmoSimulate")
    assert found["enrichment_A"] == 3.1 and found["enrichment_B"] == 4.2
    assert found["core_power"] == 100.0


def test_fzc_chain_compiles_whole_tree(project):
    fz_cli("fzc", "--input_path", str(CHAIN_EXAMPLE), "--model", "CasmoSimulate",
           "--input_variables", json.dumps({"enrichment_B": 4.9, "core_power": 90}),
           "--output_dir", "compiled")
    fuel_b = next(Path("compiled").rglob("casmo/fuel_B.inp")).read_text()
    sim = next(Path("compiled").rglob("simulate.inp")).read_text()
    assert "FUE 1 10.4/4.9" in fuel_b
    assert "'PWR' 90 /" in sim
    for text in (fuel_b, sim):
        assert "${" not in text


# --- output side: fixtures -----------------------------------------------------

FIXTURE_CASES = sorted(p.parent.name for p in FIXTURES.glob("*/expected.json"))


@pytest.mark.parametrize("case", FIXTURE_CASES)
def test_output_parsers_on_fixture(project, case):
    shutil.copytree(FIXTURES / case, "case")
    Path("case/expected.json").unlink()
    expected = json.loads((FIXTURES / case / "expected.json").read_text())
    parsed = fz_cli("fzo", "--output_path", "case", "--model", "Simulate")[0]
    for name, value in expected.items():
        assert parsed.get(name) == pytest.approx(value), name


# --- end to end with the mock launchers ---------------------------------------

def test_simulate_with_static_library(project):
    """Library shipped with --input_static; no --calculators (alias discovery)."""
    Path("cms.lib").write_text("1.25000\n")
    rows = fz_cli("fzr", "--input_path", str(SIM_EXAMPLE), "--model", "Simulate",
                  "--input_variables", json.dumps({"core_power": [100, 50]}),
                  "--input_static", "cms.lib", "--results_dir", "results",
                  env=mock_env())
    by_power = {r["core_power"]: r for r in rows}
    assert all(r["status"] == "done" for r in rows)
    assert by_power[100]["boron"][0] == pytest.approx(2500.0)
    assert by_power[50]["boron"][0] == pytest.approx(5000.0)
    assert by_power[100]["n_steps"] == 3
    assert not list(Path("results").rglob("PID"))


def test_chain_propagates_casmo_parameter(project):
    rows = fz_cli("fzr", "--input_path", str(CHAIN_EXAMPLE), "--model", "CasmoSimulate",
                  "--input_variables", json.dumps({"enrichment_B": [4.2, 5.0]}),
                  "--results_dir", "results", env=mock_env())
    assert [r["status"] for r in rows] == ["done", "done"]
    by_enr = {r["enrichment_B"]: r for r in rows}
    # mean k-inf of the two segments: (1.21 + 1.32) / 2 -> boron 2650 ppm at BOC
    assert by_enr[4.2]["boron"][0] == pytest.approx(2650.0)
    assert by_enr[5.0]["boron"][0] == pytest.approx(3050.0)
    assert by_enr[4.2]["casmo_decks"] == ["fuel_A", "fuel_B"]
    assert by_enr[4.2]["cax_files"] == ["fuel_A.cax", "fuel_B.cax"]


def test_chain_parallel_casmo(project):
    rows = fz_cli("fzr", "--input_path", str(CHAIN_EXAMPLE), "--model", "CasmoSimulate",
                  "--input_variables", json.dumps({"enrichment_B": 4.2}),
                  "--results_dir", "results", env=mock_env(CASMO_JOBS="2"))
    assert rows[0]["status"] == "done"


def test_chain_stops_on_casmo_failure(project):
    rows = fz_cli("fzr", "--input_path", str(CHAIN_EXAMPLE), "--model", "CasmoSimulate",
                  "--input_variables", json.dumps({"enrichment_B": 4.2}),
                  "--results_dir", "results", env=mock_env(MOCK_CASMO_FAIL="fuel_B"),
                  check=False)
    assert rows[0]["status"] != "done"
    assert rows[0]["exit_code"] == 10
    case = next(Path("results").iterdir())
    assert not (case / "simulate.out").exists()   # SIMULATE not run


def test_chain_missing_launcher(project, tmp_path):
    shutil.copytree(CHAIN_EXAMPLE, "case")
    env = mock_env(PATH="/usr/bin:/bin")
    env.pop("CMSLINK_CMD")
    proc = subprocess.run(["bash", str(FZ / "calculators" / "CasmoSimulate.sh"), "case"],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 2
    assert "CMS-LINK launcher not found" in proc.stderr
