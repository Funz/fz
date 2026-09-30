"""Documentation consistency: the former README lives in doc/guide/ next to the modular
reference pages in doc/, so facts must not drift apart silently."""
import glob
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Historical mentions of names that intentionally do not exist in the code
ALLOWED_UNKNOWN_VARS = {"FZ_SLURM_MODE"}  # doc/slurm-architecture.md: "replaces the earlier FZ_SLURM_MODE idea"


def _doc_files():
    return (
        [REPO / "README.md"]
        + [Path(p) for p in glob.glob(str(REPO / "doc" / "*.md"))]
        + [Path(p) for p in glob.glob(str(REPO / "doc" / "guide" / "*.md"))]
        + [Path(p) for p in glob.glob(str(REPO / "skills" / "fz" / "*.md"))]
        + [Path(p) for p in glob.glob(str(REPO / "examples" / "*.md"))]
    )


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


def test_documented_env_vars_exist_in_code():
    code = "\n".join(
        Path(p).read_text(encoding="utf-8") for p in glob.glob(str(REPO / "fz" / "**" / "*.py"), recursive=True)
    )
    known = set(re.findall(r"FZ_[A-Z0-9_]+", code)) | ALLOWED_UNKNOWN_VARS
    unknown = {}
    for f in _doc_files():
        for var in set(re.findall(r"\bFZ_[A-Z0-9_]+\b", f.read_text(encoding="utf-8"))):
            if var not in known and not var.endswith("_"):
                unknown.setdefault(var, []).append(str(f.relative_to(REPO)))
    assert not unknown, f"documentation cites FZ_* variables absent from the code: {unknown}"


def test_relative_links_in_doc_resolve():
    bad = []
    for f in _doc_files():
        if f.parent.name == "examples" or f.parent.name == "fz":
            continue  # scope: README, doc/, doc/guide/ (skills have their own test)
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


def test_every_guide_page_points_to_its_reference_counterpart_or_is_standalone():
    """Guide pages with a modular counterpart carry the pointer note, and vice versa."""
    marker = "<!-- counterpart-note -->"
    with_note = {p.name for p in (REPO / "doc" / "guide").glob("*.md") if marker in p.read_text(encoding="utf-8")}
    assert {"python-api.md", "calculator-types.md", "model-definition.md", "advanced-features.md"} <= with_note
    for m in ("core-functions.md", "calculators.md", "parallel-and-caching.md", "model-definition.md"):
        assert marker in (REPO / "doc" / m).read_text(encoding="utf-8"), m


def test_legacy_readme_anchors_are_kept():
    """Old links README.md#<heading> for sections that moved to doc/guide/ still land on the README."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    present = _anchors(REPO / "README.md") | set(re.findall(r'<a id="([^"]+)"></a>', readme))
    missing = []
    for f in glob.glob(str(REPO / "doc" / "guide" / "*.md")):
        for a in _anchors(Path(f)):
            if a not in present:
                missing.append(f"{Path(f).name}#{a}")
    assert not missing, f"README lacks legacy anchors for: {missing[:10]}"
