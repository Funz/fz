"""
Tests for fzr's case_naming option ("path", "hash", "index"), the single
cases.csv manifest written at the results root for "hash"/"index" naming,
and the fzo() fallback (manifest first, then per-case info.txt) that
recovers variable values when directory names aren't "key=val,...".
"""
import csv
from pathlib import Path

import fz


def _read_manifest(manifest_path):
    with open(manifest_path, newline="") as f:
        return {row["case"]: {k: v for k, v in row.items() if k != "case"} for row in csv.DictReader(f)}


def _write_input(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("x=$x\ny=$y\n")
    return input_file


def test_case_naming_path_default(tmp_path):
    input_file = _write_input(tmp_path)
    results_dir = tmp_path / "results"
    res = fz.fzr(
        str(input_file), {"x": [1, 2], "y": [10, 20]},
        {"output": {"echo": "echo done"}},
        results_dir=str(results_dir), calculators="sh://true",
    )
    paths = sorted(res["path"])
    assert paths == [
        f"{results_dir}/x=1,y=10",
        f"{results_dir}/x=1,y=20",
        f"{results_dir}/x=2,y=10",
        f"{results_dir}/x=2,y=20",
    ]
    # No cases.csv manifest for the default "path" naming - it would be redundant
    assert not (results_dir / "cases.csv").exists()


def test_case_naming_hash_manifest_and_fzo_fallback(tmp_path):
    input_file = _write_input(tmp_path)
    results_dir = tmp_path / "results_hash"
    res = fz.fzr(
        str(input_file), {"x": [1, 2], "y": [10, 20]},
        {"output": {"echo": "echo done"}},
        results_dir=str(results_dir), calculators="sh://true", case_naming="hash",
    )
    for p in res["path"]:
        assert Path(p).name.startswith("case_")
        assert "=" not in Path(p).name
        # Each case's own info.txt still has the values too (used as fallback
        # if the manifest is missing/incomplete)
        assert (Path(p) / "info.txt").exists()

    # Single manifest at the results root maps each case dir to its variables
    manifest_path = results_dir / "cases.csv"
    assert manifest_path.exists()
    manifest = _read_manifest(manifest_path)
    assert set(manifest.keys()) == {Path(p).name for p in res["path"]}
    for case_name, case_vars in manifest.items():
        row = res[res["path"] == str(results_dir / case_name)].iloc[0]
        assert int(case_vars["x"]) == row["x"]
        assert int(case_vars["y"]) == row["y"]

    # fzo must recover x/y columns via the manifest, since directory names
    # don't parse as "key=val,..."
    out = fz.fzo(f"{results_dir}/*", {"output": {"echo": "echo done"}})
    assert sorted(out["x"].tolist()) == [1, 1, 2, 2]
    assert sorted(out["y"].tolist()) == [10, 10, 20, 20]


def test_case_naming_index_manifest_and_fzo_fallback(tmp_path):
    input_file = _write_input(tmp_path)
    results_dir = tmp_path / "results_index"
    res = fz.fzr(
        str(input_file), {"x": [1, 2], "y": [10, 20]},
        {"output": {"echo": "echo done"}},
        results_dir=str(results_dir), calculators="sh://true", case_naming="index",
    )
    names = sorted(Path(p).name for p in res["path"])
    assert names == ["case_0", "case_1", "case_2", "case_3"]

    manifest = _read_manifest(results_dir / "cases.csv")
    assert set(manifest.keys()) == set(names)

    out = fz.fzo(f"{results_dir}/*", {"output": {"echo": "echo done"}})
    assert sorted(out["x"].tolist()) == [1, 1, 2, 2]
    assert sorted(out["y"].tolist()) == [10, 10, 20, 20]


def test_case_naming_fzo_falls_back_to_info_txt_without_manifest(tmp_path):
    """If cases.csv is missing/deleted, fzo still recovers variables from info.txt."""
    input_file = _write_input(tmp_path)
    results_dir = tmp_path / "results_no_manifest"
    fz.fzr(
        str(input_file), {"x": [1, 2]},
        {"output": {"echo": "echo done"}},
        results_dir=str(results_dir), calculators="sh://true", case_naming="index",
    )
    (results_dir / "cases.csv").unlink()

    out = fz.fzo(f"{results_dir}/*", {"output": {"echo": "echo done"}})
    assert sorted(out["x"].tolist()) == [1, 2]


def test_case_naming_invalid_raises(tmp_path):
    input_file = _write_input(tmp_path)
    try:
        fz.fzr(
            str(input_file), {"x": [1]}, {"output": {"echo": "echo done"}},
            results_dir=str(tmp_path / "r"), calculators="sh://true", case_naming="bogus",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_case_naming_env_var_default(tmp_path, monkeypatch):
    from fz.config import reload_config

    monkeypatch.setenv("FZ_CASE_NAMING", "index")
    reload_config()
    try:
        input_file = _write_input(tmp_path)
        results_dir = tmp_path / "results_env"
        res = fz.fzr(
            str(input_file), {"x": [1, 2]}, {"output": {"echo": "echo done"}},
            results_dir=str(results_dir), calculators="sh://true",
        )
        names = sorted(Path(p).name for p in res["path"])
        assert names == ["case_0", "case_1"]
    finally:
        monkeypatch.delenv("FZ_CASE_NAMING", raising=False)
        reload_config()
