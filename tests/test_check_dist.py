"""scripts/check_dist.py: distribution checks shared by ci.yml and release.yml (issue #102)."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_dist.py"
HAS_TWINE = importlib.util.find_spec("twine") is not None


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


def _dist(tmp_path, wheel="funz_fz-2.0-py3-none-any.whl", sdist="funz_fz-2.0.tar.gz"):
    d = tmp_path / "dist"
    d.mkdir()
    for name in filter(None, (wheel, sdist)):
        (d / name).write_bytes(b"")
    return d


def test_platform_wheel_rejected(tmp_path):
    proc = _run(_dist(tmp_path, wheel="funz_fz-2.0-cp311-cp311-linux_x86_64.whl"))
    assert proc.returncode == 1 and "not pure Python" in proc.stderr


def test_missing_sdist_rejected(tmp_path):
    proc = _run(_dist(tmp_path, sdist=None))
    assert proc.returncode == 1 and "exactly one sdist" in proc.stderr


def test_two_wheels_rejected(tmp_path):
    d = _dist(tmp_path)
    (d / "funz_fz-1.2-py3-none-any.whl").write_bytes(b"")
    proc = _run(d)
    assert proc.returncode == 1 and "exactly one wheel" in proc.stderr


@pytest.fixture(scope="module")
def built_dist(tmp_path_factory):
    if not HAS_TWINE or importlib.util.find_spec("build") is None:
        pytest.skip("needs the 'build' and 'twine' packages")
    out = tmp_path_factory.mktemp("built")
    repo = SCRIPT.parent.parent
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(out), str(repo)],
                   check=True, capture_output=True)
    return out


def test_real_build_passes_and_prints_version(built_dist):
    import fz
    proc = _run(built_dist)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == fz.__version__


@pytest.mark.parametrize("prefix", ["", "v"])
def test_matching_tag_passes(built_dist, prefix):
    import fz
    assert _run(built_dist, "--tag", prefix + fz.__version__).returncode == 0


def test_mismatching_tag_rejected(built_dist):
    proc = _run(built_dist, "--tag", "0.0.1")
    assert proc.returncode == 1 and "does not match fz.__version__" in proc.stderr
