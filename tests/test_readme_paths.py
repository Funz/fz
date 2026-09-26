"""Every repo path cited in backticks in README.md must exist."""

import glob
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH_RE = re.compile(
    r"`((?:tests|doc|examples|fz|skills|scripts)/[A-Za-z0-9_.*/\-]+\.(?:py|md|json|sh|yml|yaml|toml))`"
)


def test_readme_cited_paths_exist():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    missing = sorted(
        {p for p in PATH_RE.findall(text) if not glob.glob(str(REPO / p))}
    )
    assert not missing, f"README.md cites nonexistent paths: {missing}"
