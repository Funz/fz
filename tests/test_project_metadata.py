"""Project metadata consistency: CI matrix vs classifiers, CITATION.cff."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_classifiers_cover_ci_python_versions():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    versions = set(re.findall(r"['\"](3\.\d+)(?:-dev)?['\"]", ci))
    assert versions, "no Python versions found in ci.yml"
    pyproject = (ROOT / "pyproject.toml").read_text()
    declared = set(re.findall(r"Programming Language :: Python :: (3\.\d+)", pyproject))
    assert versions <= declared, f"CI tests {sorted(versions - declared)} but pyproject does not declare it"


def test_citation_cff_is_valid():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    for key in ("cff-version", "message", "title", "authors"):
        assert data.get(key), f"CITATION.cff: missing {key}"
    assert data["authors"][0].get("family-names")
