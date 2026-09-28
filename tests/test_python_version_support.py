"""
Guard against pyproject.toml's declared Python support drifting from what
CI (.github/workflows/ci.yml) actually tests.

Regression test for P0-5 follow-up: pyproject.toml declared
`requires-python = ">=3.8"` and classifiers for 3.8-3.12 while CI's matrix
actually tested 3.9-3.14 (3.8 unsupported/untested, 3.13-3.14 tested but
undeclared). This does not require a TOML parser (tomllib is 3.11+ only,
and requires-python must stay usable on the oldest supported interpreter);
it extracts the relevant lines with a simple regex, matching the style of
tests/test_skill_static.py.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = (REPO / "pyproject.toml").read_text(encoding="utf-8")
CI_YML = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _requires_python_minimum() -> tuple:
    m = re.search(r'requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', PYPROJECT)
    assert m, "pyproject.toml must declare requires-python = '>=X.Y'"
    return (int(m.group(1)), int(m.group(2)))


def _classifier_versions() -> set:
    return {
        tuple(int(p) for p in v.split("."))
        for v in re.findall(
            r'"Programming Language :: Python :: (\d+\.\d+)"', PYPROJECT
        )
    }


def _ci_matrix_versions() -> set:
    """Stable (non -dev/-rc) python-version entries in ci.yml's matrix."""
    versions = set()
    for v in re.findall(r"python-version:\s*\[([^\]]+)\]", CI_YML):
        for tok in re.findall(r"'([\d.]+)'", v):
            versions.add(tuple(int(p) for p in tok.split(".")))
    return versions


def test_requires_python_is_not_end_of_life():
    # Python 3.8 reached end-of-life in October 2024; fz should not declare
    # support for it. This also guards against a future regression back to
    # an unsupported floor.
    assert _requires_python_minimum() >= (3, 9)


def test_requires_python_matches_ci_minimum():
    ci_versions = _ci_matrix_versions()
    assert ci_versions, "expected at least one stable python-version in ci.yml's matrix"
    assert _requires_python_minimum() == min(ci_versions)


def test_classifiers_cover_all_stable_ci_versions():
    ci_versions = _ci_matrix_versions()
    classifiers = _classifier_versions()
    missing = ci_versions - classifiers
    assert not missing, (
        f"ci.yml tests {sorted(missing)} but pyproject.toml has no matching "
        "'Programming Language :: Python :: X.Y' classifier for them"
    )


def test_no_classifier_for_untested_or_eol_versions():
    ci_versions = _ci_matrix_versions()
    classifiers = _classifier_versions()
    extra = classifiers - ci_versions
    assert not extra, (
        f"pyproject.toml declares classifiers for {sorted(extra)} which "
        "ci.yml's stable matrix does not test"
    )
