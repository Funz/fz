"""Campaign manifest (manifest.json) and optional RO-Crate export (P1-4)."""
import json
import os
from pathlib import Path

import pytest

import fz
from fz.manifest import redact_uri, uri_host


@pytest.fixture(autouse=True)
def _reset_config():
    yield
    os.environ.pop("FZ_RO_CRATE", None)
    fz.config.get_config().reload()


def _run(tmp_path, monkeypatch, ro_crate=False):
    monkeypatch.delenv("FZ_RO_CRATE", raising=False)
    if not ro_crate:
        monkeypatch.setenv("FZ_RO_CRATE", "0")
    fz.config.get_config().reload()
    inp = tmp_path / "input.txt"
    inp.write_text("x=$x\n")
    model = {"varprefix": "$", "delim": "()", "output": {"out": "cat input.txt"}}
    out = tmp_path / "results"
    df = fz.fzr(str(inp), {"x": [1, 2]}, model, calculators="sh://bash -c 'cat input.txt > output.txt'",
                results_dir=str(out))
    return df, out


def test_manifest_written(tmp_path, monkeypatch):
    df, out = _run(tmp_path, monkeypatch)  # FZ_RO_CRATE=0
    m = json.loads((out / "manifest.json").read_text())
    assert m["schema"] == "fz-manifest/1"
    assert m["n_cases"] == 2 and len(m["cases"]) == 2
    assert m["fz_version"] and m["python_version"] and m["model_sha256"]
    assert m["start_time"] <= m["end_time"]
    assert all(len(c["fz_hash_sha256"]) == 64 for c in m["cases"])
    assert not (out / "ro-crate-metadata.json").exists()  # FZ_RO_CRATE=0


def test_ro_crate_default_on(tmp_path, monkeypatch):
    _, out = _run(tmp_path, monkeypatch, ro_crate=True)
    crate = json.loads((out / "ro-crate-metadata.json").read_text())
    ids = {n["@id"] for n in crate["@graph"]}
    assert {"ro-crate-metadata.json", "./", "manifest.json", "#run"} <= ids


def test_fzd_manifest_and_crate(tmp_path):
    out = tmp_path / "ana"
    algo = Path(__file__).parent.parent / "examples" / "algorithms" / "randomsampling.py"

    def model_func(x):
        return {"z": (x - 0.3) ** 2}

    fz.fzd(input_path=None, input_variables={"x": "[0;1]"}, model=model_func,
           output_expression="z", algorithm=str(algo),
           algorithm_options={"nvalues": 3, "seed": 42}, analysis_dir=str(out))
    m = json.loads((out / "manifest.json").read_text())
    assert m["schema"] == "fz-manifest-fzd/1" and m["n_iterations"] >= 1
    assert m["model"] == {"python_callable": "model_func"}
    crate = json.loads((out / "ro-crate-metadata.json").read_text())
    assert any(n["@id"] == "#run" and "fzd" in n["name"] for n in crate["@graph"])


def test_redact_and_host():
    assert redact_uri("ssh://bob:secret@node1/bash x") == "ssh://bob:***@node1/bash x"
    assert redact_uri("sh://bash x") == "sh://bash x"
    assert uri_host("ssh://bob:pw@node1:22/bash") == "node1"
    assert uri_host("sh://bash") is None
