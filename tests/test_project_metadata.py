"""Project metadata: CITATION.cff validity (classifier/CI consistency is covered by
test_python_version_support.py)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_citation_cff_is_valid():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    for key in ("cff-version", "message", "title", "authors"):
        assert data.get(key), f"CITATION.cff: missing {key}"
    assert data["authors"][0].get("family-names")
