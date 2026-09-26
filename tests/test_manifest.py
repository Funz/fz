"""Campaign manifest (manifest.json) and optional RO-Crate export (P1-4)."""
import json
from pathlib import Path

import fz
from fz.manifest import redact_uri, uri_host


def _run(tmp_path, monkeypatch, ro_crate=False):
    if ro_crate:
        monkeypatch.setenv("FZ_RO_CRATE", "1")
        fz.config.get_config().reload()
    inp = tmp_path / "input.txt"
    inp.write_text("x=$x\n")
    model = {"varprefix": "$", "delim": "()", "output": {"out": "cat input.txt"}}
    out = tmp_path / "results"
    df = fz.fzr(str(inp), {"x": [1, 2]}, model, calculators="sh://bash -c 'cat input.txt > output.txt'",
                results_dir=str(out))
    return df, out


def test_manifest_written(tmp_path, monkeypatch):
    df, out = _run(tmp_path, monkeypatch)
    m = json.loads((out / "manifest.json").read_text())
    assert m["schema"] == "fz-manifest/1"
    assert m["n_cases"] == 2 and len(m["cases"]) == 2
    assert m["fz_version"] and m["python_version"] and m["model_sha256"]
    assert m["start_time"] <= m["end_time"]
    assert all(len(c["fz_hash_sha256"]) == 64 for c in m["cases"])
    assert not (out / "ro-crate-metadata.json").exists()


def test_ro_crate_optional(tmp_path, monkeypatch):
    try:
        _, out = _run(tmp_path, monkeypatch, ro_crate=True)
        crate = json.loads((out / "ro-crate-metadata.json").read_text())
        ids = {n["@id"] for n in crate["@graph"]}
        assert {"ro-crate-metadata.json", "./", "manifest.json", "#run"} <= ids
    finally:
        monkeypatch.delenv("FZ_RO_CRATE", raising=False)
        fz.config.get_config().reload()


def test_redact_and_host():
    assert redact_uri("ssh://bob:secret@node1/bash x") == "ssh://bob:***@node1/bash x"
    assert redact_uri("sh://bash x") == "sh://bash x"
    assert uri_host("ssh://bob:pw@node1:22/bash") == "node1"
    assert uri_host("sh://bash") is None
