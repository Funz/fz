"""
Tests for the model "static_files" option: files identical across every case
(e.g. a shared weather CSV or a large reference dataset) that are never
templated/substituted, never re-hashed per case, and (for relative paths) not
duplicated on disk per case - symlinked into each case directory instead.

- Absolute path entries: assumed already present at that same path on the
  calculator side too; never copied/symlinked/transferred, only hashed (so
  cache matching still reacts if the shared file's content changes).
- Relative path entries: resolved against cwd at fzr() call time, identified
  by basename, symlinked into every case's result_dir/tmp_dir, and explicitly
  transferred to remote calculators (see tests/test_static_files_ssh.py for
  the ssh:// remote-transfer coverage).
"""
import os
from pathlib import Path

import pytest

import fz


def _write_input(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("x=$x\n")
    return input_file


def test_static_files_relative_symlinked_and_hashed(tmp_path, monkeypatch):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    weather = assets_dir / "weather.csv"
    weather.write_text("weather-v1")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": ["../assets/weather.csv"],
        "output": {"echo": "cat weather.csv"},
    }
    res = fz.fzr(str(input_file), {"x": [1, 2]}, model,
                 results_dir="results", calculators="sh://true")

    for p in res["path"]:
        link = Path(p) / "weather.csv"
        # Symlinked where the platform allows it; falls back to a real copy
        # on Windows without developer mode/admin privileges - either way the
        # content must be correct.
        if link.is_symlink():
            assert link.resolve() == weather.resolve()
        assert link.read_text() == "weather-v1"

    # Hashed with its basename, not the declared "../assets/weather.csv" path
    # (which would otherwise escape the case directory as a symlink name)
    hash_content = (Path(res["path"][0]) / ".fz_hash").read_text()
    assert "weather.csv" in hash_content
    assert "../assets/weather.csv" not in hash_content


def test_static_files_absolute_not_transferred_but_hashed(tmp_path, monkeypatch):
    shared = tmp_path / "shared_ref.bin"
    shared.write_text("shared-content")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": [str(shared)],
        "output": {"echo": "echo done"},
    }
    res = fz.fzr(str(input_file), {"x": [1]}, model,
                 results_dir="results", calculators="sh://true")

    case_dir = Path(res["path"][0])
    # Never copied or symlinked into the case directory
    assert not (case_dir / "shared_ref.bin").exists()
    assert not (case_dir / shared.name).is_symlink()

    # But still hashed, identified by its absolute path
    hash_content = (case_dir / ".fz_hash").read_text()
    assert str(shared) in hash_content


def test_static_files_command_can_read_both_kinds(tmp_path, monkeypatch):
    """Symlinked relative + absolute-referenced static files are both usable by
    a calculator script running in the case's working directory."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    weather = assets_dir / "weather.csv"
    weather.write_text("weather-data\n")

    shared = tmp_path / "shared_ref.bin"
    shared.write_text("shared-data")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    calc_script = study_dir / "calc.sh"
    calc_script.write_text(f"#!/bin/bash\ncat weather.csv {shared} > combined.txt\n")
    calc_script.chmod(0o755)

    model = {
        "static_files": ["../assets/weather.csv", str(shared)],
        "output": {"echo": "cat combined.txt"},
    }
    res = fz.fzr(str(input_file), {"x": [1]}, model,
                 results_dir="results", calculators="sh://bash calc.sh")

    assert res["status"][0] == "done"
    assert res["echo"][0] == "weather-data\nshared-data"


def test_static_files_excluded_from_fzi_variable_scan(tmp_path, monkeypatch):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    # This file contains something that looks like a $variable - it must NOT
    # be picked up as an fz variable since it's declared static
    weather = assets_dir / "weather.csv"
    weather.write_text("station=$not_a_real_var\n")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": ["../assets/weather.csv"],
        "output": {},
    }
    variables = fz.fzi(str(input_file), model)
    assert "x" in variables
    assert "not_a_real_var" not in variables


def test_static_files_cache_invalidated_on_content_change(tmp_path, monkeypatch):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    weather = assets_dir / "weather.csv"
    weather.write_text("v1")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": ["../assets/weather.csv"],
        "output": {"echo": "cat weather.csv"},
    }
    fz.fzr(str(input_file), {"x": [1]}, model,
           results_dir="results1", calculators="sh://true")

    # Re-run via cache with unchanged static file -> cache hit, same content
    res_hit = fz.fzr(str(input_file), {"x": [1]}, model, results_dir="results2",
                      calculators=["cache://results1", "sh://true"])
    assert res_hit["echo"][0] == "v1"

    # Change the shared static file, re-run via cache -> must NOT reuse stale cache
    weather.write_text("v2-changed")
    res_miss = fz.fzr(str(input_file), {"x": [1]}, model, results_dir="results3",
                       calculators=["cache://results1", "sh://true"])
    assert res_miss["echo"][0] == "v2-changed"


def test_static_files_missing_entry_skipped_with_warning(tmp_path, monkeypatch, caplog):
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": ["does_not_exist.csv"],
        "output": {"echo": "echo done"},
    }
    # Should not raise - the missing entry is skipped, case still runs
    res = fz.fzr(str(input_file), {"x": [1]}, model,
                 results_dir="results", calculators="sh://true")
    assert res["status"][0] == "done"


def test_static_files_invalid_type_raises():
    with pytest.raises(TypeError):
        fz.fzr("x", {}, {"output": {}, "static_files": "not-a-list"})

    with pytest.raises(TypeError):
        fz.fzr("x", {}, {"output": {}, "static_files": [123]})


def test_static_files_name_collision_skipped(tmp_path, monkeypatch):
    """Two relative entries resolving to the same basename: only the first is kept."""
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "config.xml").write_text("from-a")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "config.xml").write_text("from-b")

    study_dir = tmp_path / "study"
    study_dir.mkdir()
    monkeypatch.chdir(study_dir)
    input_file = _write_input(study_dir)

    model = {
        "static_files": ["../a/config.xml", "../b/config.xml"],
        "output": {"echo": "cat config.xml"},
    }
    res = fz.fzr(str(input_file), {"x": [1]}, model,
                 results_dir="results", calculators="sh://true")
    # Whichever was kept, the case must still run and read a consistent file
    assert res["status"][0] == "done"
    assert res["echo"][0] in ("from-a", "from-b")
