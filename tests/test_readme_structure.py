"""README is an entry point: keep it short, and keep its (and doc/guide's) links valid."""
import glob
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAX_README_LINES = 300


def _anchors(path: Path) -> set:
    seen, out, fence = {}, set(), False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if fence:
            continue
        m = re.match(r"^#{1,6} (.*)$", line)
        if m:
            s = re.sub(r"[^\w\- ]", "", m.group(1).strip().lower()).replace(" ", "-")
            n = seen.get(s, 0)
            seen[s] = n + 1
            out.add(s if n == 0 else f"{s}-{n}")
    return out


def test_readme_stays_short():
    n = len((REPO / "README.md").read_text(encoding="utf-8").split("\n"))
    assert n <= MAX_README_LINES, f"README.md has {n} lines (max {MAX_README_LINES}); move detail to doc/guide/"


def test_relative_links_and_anchors_resolve():
    files = [REPO / "README.md"] + [Path(p) for p in glob.glob(str(REPO / "doc" / "guide" / "*.md"))]
    bad = []
    for f in files:
        for m in re.finditer(r"\]\(([^)\s]+)\)", f.read_text(encoding="utf-8")):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            dest = (f.parent / path) if path else f
            if not dest.exists():
                bad.append(f"{f.relative_to(REPO)}: {target} (missing file)")
            elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
                bad.append(f"{f.relative_to(REPO)}: {target} (missing anchor)")
    assert not bad, "broken links:\n" + "\n".join(bad)
