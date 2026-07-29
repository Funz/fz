"""
Tests for the one-time warning that suggests moving a large, variable-free
input_path file into input_static instead (see fz/helpers.py's
_maybe_warn_static_candidate, used by compile_to_result_directories).

Threshold is fz.config's FZ_STATIC_CANDIDATE_MIN_SIZE (default 1 MiB).
"""
from pathlib import Path

import fz
from fz import set_log_level
from fz.logging import LogLevel
from fz.config import get_config


def _write_template(tmp_path, extra_files):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "input.txt").write_text("x=$x\n")
    for name, content in extra_files.items():
        (template_dir / name).write_bytes(content)
    return template_dir


def test_warns_once_for_large_variable_free_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(get_config(), "static_candidate_min_size", 1000)
    set_log_level(LogLevel.WARNING)
    try:
        template_dir = _write_template(tmp_path, {"big_static.dat": b"A" * 2000})
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        monkeypatch.chdir(run_dir)

        model = {"output": {"echo": "echo done"}}
        fz.fzr(str(template_dir), {"x": [1, 2, 3]}, model,
               results_dir="results", calculators="sh://true")

        stderr = capsys.readouterr().err
        assert "big_static.dat" in stderr
        assert "input_static" in stderr
        # Only once, not once per case
        assert stderr.count("big_static.dat") == 1
    finally:
        set_log_level(LogLevel.ERROR)


def test_no_warning_for_small_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(get_config(), "static_candidate_min_size", 1_048_576)
    set_log_level(LogLevel.WARNING)
    try:
        template_dir = _write_template(tmp_path, {"small_static.dat": b"A" * 1000})
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        monkeypatch.chdir(run_dir)

        model = {"output": {"echo": "echo done"}}
        fz.fzr(str(template_dir), {"x": [1]}, model,
               results_dir="results", calculators="sh://true")

        stderr = capsys.readouterr().err
        assert "small_static.dat" not in stderr
    finally:
        set_log_level(LogLevel.ERROR)


def test_no_warning_for_templated_file(tmp_path, monkeypatch, capsys):
    """A large file that does contain a variable is not a static candidate."""
    monkeypatch.setattr(get_config(), "static_candidate_min_size", 1000)
    set_log_level(LogLevel.WARNING)
    try:
        template_dir = _write_template(
            tmp_path, {"big_templated.dat": b"val=$x " + b"A" * 2000}
        )
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        monkeypatch.chdir(run_dir)

        model = {"output": {"echo": "echo done"}}
        fz.fzr(str(template_dir), {"x": [1, 2]}, model,
               results_dir="results", calculators="sh://true")

        stderr = capsys.readouterr().err
        assert "big_templated.dat" not in stderr
    finally:
        set_log_level(LogLevel.ERROR)


def test_warning_disabled_when_threshold_is_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(get_config(), "static_candidate_min_size", 0)
    set_log_level(LogLevel.WARNING)
    try:
        template_dir = _write_template(tmp_path, {"big_static.dat": b"A" * 2_000_000})
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        monkeypatch.chdir(run_dir)

        model = {"output": {"echo": "echo done"}}
        fz.fzr(str(template_dir), {"x": [1]}, model,
               results_dir="results", calculators="sh://true")

        stderr = capsys.readouterr().err
        assert "big_static.dat" not in stderr
    finally:
        set_log_level(LogLevel.ERROR)
