"""P0-8 regression tests: path resolution in sh:// commands.

Only words that exist in the launch directory and not in the case directory
are resolved; output redirection targets are never resolved.
"""

import os
from pathlib import Path

import fz
from fz.runners.sh import resolve_all_paths_in_command


def test_resolver_skips_nonexistent_and_case_files(tmp_path):
    launch = tmp_path / "launch"
    case = tmp_path / "case"
    launch.mkdir()
    case.mkdir()
    (launch / "in.txt").write_text("template")
    (launch / "tool.sh").write_text("echo tool")
    (case / "in.txt").write_text("compiled")

    cmd, _ = resolve_all_paths_in_command(
        "bash tool.sh in.txt > out.txt", str(launch), str(case)
    )
    assert f"{launch}/tool.sh" in cmd          # only in launch dir: resolved
    assert f"{launch}/in.txt" not in cmd       # in case dir: compiled file wins
    assert f"{launch}/out.txt" not in cmd      # redirection target untouched
    assert cmd.endswith("> out.txt")


def test_resolver_never_resolves_output_redirect_even_if_exists(tmp_path):
    launch = tmp_path / "launch"
    case = tmp_path / "case"
    launch.mkdir()
    case.mkdir()
    (launch / "out.txt").write_text("x")
    for op in (">", ">>", "2>"):
        cmd, _ = resolve_all_paths_in_command(
            f"echo hi {op} out.txt", str(launch), str(case)
        )
        assert str(launch) not in cmd


def test_resolver_nonexistent_word_kept(tmp_path):
    cmd, _ = resolve_all_paths_in_command("bash ghost.sh ./x", str(tmp_path), None)
    assert str(tmp_path) not in cmd


def test_fzr_sh_cat_redirect_two_cases(tmp_path):
    model_dir = tmp_path
    (model_dir / "in.txt").write_text("x=${x}\n")
    inp = model_dir / "in.txt"
    launch = Path.cwd()

    res = fz.fzr(
        str(inp),
        {"x": [1, 2]},
        {"varprefix": "$", "delim": "{}", "output": {"y": "cat res.txt"}},
        calculators="sh://cat in.txt > res.txt",
        results_dir=str(tmp_path / "res"),
    )
    # fz appends the input file name to the command, so cat prints it twice
    assert [v.splitlines()[0] for v in res["y"].astype(str)] == ["x=1", "x=2"]
    case_dirs = sorted(p for p in (tmp_path / "res").iterdir() if p.is_dir())
    assert len(case_dirs) == 2
    for d in case_dirs:
        assert (d / "res.txt").read_text().startswith("x=")
    assert not (launch / "res.txt").exists()


def test_fzr_sh_script_only_in_launch_dir(tmp_path):
    (tmp_path / "in.txt").write_text("v=${x}\n")
    script = Path.cwd() / "myscript.sh"
    script.write_text("#!/bin/bash\ncat in.txt > out.dat\n")
    try:
        res = fz.fzr(
            str(tmp_path / "in.txt"),
            {"x": [3]},
            {"varprefix": "$", "delim": "{}", "output": {"y": "cat out.dat"}},
            calculators="sh://bash myscript.sh",
            results_dir=str(tmp_path / "res"),
        )
        assert str(res["y"].iloc[0]).strip() == "v=3"
    finally:
        script.unlink()
