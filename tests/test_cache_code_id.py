#!/usr/bin/env python3
"""
P0-1: cache:// identity checks.

The .fz_hash key no longer includes the calculator's command or a model
hash (both were removed after review - see the audit doc): the command is
routinely calculator-specific even for the exact same code (e.g. "bash
run.sh" locally vs "/opt/telemac/v8p5/run.sh" over SSH), and the model hash
was redundant (outputs are re-applied via fzo() on every cache hit; inputs
are already covered by the compiled-files hash). Instead, a calculator alias
may declare an optional "code_id" (its code installation's identity, e.g.
"telemac@v8p5"); cache:// uses it, not the command, to decide whether a
result may be reused across calculators.
"""
import os
from pathlib import Path

import pytest

from fz import fzr
from fz.config import get_config
from fz.io import create_hash_file, _parse_hash_file, md5_file
from fz.logging import get_log_level, set_log_level


def _write_input():
    with open("input.txt", "w", newline='\n') as f:
        f.write("x = ${x}\n")


def _write_counting_calculator(name: str, tag: str, counter_file: str):
    """A calculator that records every real execution (so a cache hit, which
    never runs it, can be told apart from an actual (re)computation).
    The calculator runs in a per-case temp directory, not the test's cwd, so
    the counter file is tracked by absolute path."""
    counter_path = (Path.cwd() / counter_file).as_posix()
    with open(name, "w", newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write(f"echo 1 >> {counter_path}\n")
        f.write("X=$(grep 'x =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write(f"echo \"result = {tag}_$X\" > output.txt\n")
    os.chmod(name, 0o755)


def _count(counter_file: str) -> int:
    if not Path(counter_file).exists():
        return 0
    return len(Path(counter_file).read_text().splitlines())


MODEL = {
    "varprefix": "$",
    "delim": "{}",
    "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"},
}


def test_same_code_id_matches_despite_different_command():
    """Two calculators with different commands but the same code_id share the cache."""
    _write_input()
    _write_counting_calculator("calc_a.sh", "A", "runs.txt")
    _write_counting_calculator("calc_b.sh", "B", "runs.txt")

    fzr(
        "input.txt", {"x": [1]}, MODEL,
        calculators=[{"uri": "sh://bash ./calc_a.sh", "code_id": "code@v1"}],
        results_dir="results_1",
    )
    assert _count("runs.txt") == 1

    result2 = fzr(
        "input.txt", {"x": [1]}, MODEL,
        calculators=["cache://results_1", {"uri": "sh://bash ./calc_b.sh", "code_id": "code@v1"}],
        results_dir="results_2",
    )

    # calc_b never ran: the case was served from cache (calc_a's result, "A_1")
    assert _count("runs.txt") == 1
    assert result2["result"][0] == "A_1"
    assert result2["status"][0] == "done"


def test_different_code_id_does_not_match():
    """Same command, different declared code_id: no cache reuse."""
    _write_input()
    _write_counting_calculator("calc_a.sh", "A", "runs.txt")

    fzr(
        "input.txt", {"x": [1]}, MODEL,
        calculators=[{"uri": "sh://bash ./calc_a.sh", "code_id": "code@v1"}],
        results_dir="results_1",
    )
    assert _count("runs.txt") == 1

    fzr(
        "input.txt", {"x": [1]}, MODEL,
        calculators=["cache://results_1", {"uri": "sh://bash ./calc_a.sh", "code_id": "code@v2"}],
        results_dir="results_2",
    )

    # Same script, but declared a different code_id: must recompute, not reuse
    assert _count("runs.txt") == 2


def test_no_code_id_matches_with_warning_by_default(capsys):
    """No code_id declared on either side: identity can't be verified, so the
    match is still accepted (backward compatible) but with a one-time warning."""
    old_level = get_log_level()
    set_log_level("WARNING")  # log_warning() is a no-op below WARNING (default: ERROR)
    try:
        _write_input()
        _write_counting_calculator("calc_a.sh", "A", "runs.txt")

        fzr("input.txt", {"x": [1]}, MODEL, calculators=["sh://bash ./calc_a.sh"], results_dir="results_1")
        assert _count("runs.txt") == 1
        capsys.readouterr()

        fzr("input.txt", {"x": [1]}, MODEL, calculators=["cache://results_1", "sh://bash ./calc_a.sh"], results_dir="results_2")

        assert _count("runs.txt") == 1  # reused from cache, calc_a not re-run
        captured = capsys.readouterr()
        assert "code_id" in captured.err
    finally:
        set_log_level(old_level)


def test_no_code_id_refused_in_strict_mode(monkeypatch):
    """FZ_CACHE_STRICT=1: an unverifiable identity refuses the cache match."""
    monkeypatch.setattr(get_config(), "cache_strict", True)

    _write_input()
    _write_counting_calculator("calc_a.sh", "A", "runs.txt")

    fzr("input.txt", {"x": [1]}, MODEL, calculators=["sh://bash ./calc_a.sh"], results_dir="results_1")
    assert _count("runs.txt") == 1

    fzr("input.txt", {"x": [1]}, MODEL, calculators=["cache://results_1", "sh://bash ./calc_a.sh"], results_dir="results_2")

    # Strict mode can't verify code_id on either side -> refused -> recomputed
    assert _count("runs.txt") == 2


def test_hash_file_is_versioned_sha256():
    """.fz_hash is now a versioned (v2), SHA-256 format."""
    Path("a.txt").write_text("hello\n")
    directory = Path(".")
    create_hash_file(directory, ["a.txt"])
    hash_file = directory / ".fz_hash"
    lines = hash_file.read_text().splitlines()
    assert lines[0] == "# fz-hash v2"
    meta = _parse_hash_file(hash_file)
    assert meta["version"] == "v2"
    assert meta["code_id"] is None
    digest = meta["entries"]["a.txt"]
    assert len(digest) == 64  # SHA-256 hex digest length (MD5 was 32)


def test_legacy_v1_cache_ignored_by_default_and_accepted_when_opted_in():
    """A pre-v2 (MD5, no header) cache dir is skipped unless FZ_CACHE_ACCEPT_LEGACY=1."""
    _write_input()
    _write_counting_calculator("calc_a.sh", "A", "runs.txt")

    # Simulate a v1 cache directory written by an older fz version. Written
    # with newline='\n' throughout: fz preserves each compiled file's
    # original line ending (see helpers.py's compile_file), and the real
    # input.txt here is created with a bare '\n' by _write_input(), so the
    # legacy cache must match that exactly, or the MD5 comparison in
    # _entries_match() spuriously fails on Windows (default text mode would
    # write '\r\n', hashing differently from the '\n'-only compiled file).
    legacy_dir = Path("legacy_cache")
    legacy_dir.mkdir()
    with open(legacy_dir / "input.txt", "w", newline='\n') as f:
        f.write("x = 1\n")
    with open(legacy_dir / "output.txt", "w", newline='\n') as f:
        f.write("result = A_1\n")
    with open(legacy_dir / ".fz_hash", "w", newline='\n') as f:
        f.write(f"{md5_file(legacy_dir / 'input.txt')}  input.txt\n")

    fzr(
        "input.txt", {"x": [1]}, MODEL,
        calculators=[f"cache://{legacy_dir}", "sh://bash ./calc_a.sh"],
        results_dir="results_default",
    )
    # Legacy cache ignored by default: calculator actually ran
    assert _count("runs.txt") == 1

    config = get_config()
    config.cache_accept_legacy = True
    try:
        fzr(
            "input.txt", {"x": [1]}, MODEL,
            calculators=[f"cache://{legacy_dir}", "sh://bash ./calc_a.sh"],
            results_dir="results_legacy_ok",
        )
    finally:
        config.cache_accept_legacy = False
    # Opted in: legacy cache reused, calculator not run again
    assert _count("runs.txt") == 1
