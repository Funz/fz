"""Documentation consistency: all documentation lives in doc/ (reference text, then "Guide"
sections that used to be the README), so facts must not drift apart silently."""
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
            continue  # scope: README and doc/ (skills have their own test)
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


def test_former_readme_content_is_in_doc():
    """The former README sections live in doc/, merged into one page per topic (no 'Guide' duplicates)."""
    expected = {  # file -> heading that must exist in it
        "cli-usage.md": "# CLI Usage", "configuration.md": "# Configuration",
        "custom-algorithms.md": "# Writing Custom Algorithms for fzd", "installation.md": "# Installation",
        "quick-start.md": "# Quick Start", "interrupt-handling.md": "# Interrupt Handling",
        "breaking-changes.md": "# Breaking Changes", "troubleshooting.md": "# Troubleshooting",
        "development.md": "# Development", "ai-agents.md": "# Using fz with AI Coding Agents",
        "resources.md": "# Documentation",
        "core-functions.md": "## Input Variables: Factorial vs Non-Factorial Designs",
        "calculators.md": "### Calculator-Model Compatibility",
        "parallel-and-caching.md": "### Progress callbacks",
        "quick-examples.md": "## Interactive Jupyter Notebooks",
        "installing-models.md": "## Creating an algorithm plugin",
        "overview.md": "## Output Structure",
    }
    missing = [f for f, h in expected.items()
               if h not in (REPO / "doc" / f).read_text(encoding="utf-8").split("\n")]
    assert not missing, f"missing former-README content in doc/: {missing}"
    assert not (REPO / "doc" / "guide").exists(), "doc/guide/ was merged into doc/"
    assert not (REPO / "doc" / "output-structure.md").exists(), "merged into overview.md"
    leftovers = [p.name for p in (REPO / "doc").glob("*.md")
                 if re.search(r"^## Guide: ", p.read_text(encoding="utf-8"), flags=re.M)]
    assert not leftovers, f"un-merged 'Guide:' sections remain in: {leftovers}"


def test_fzr_callbacks_documented_as_dict():
    """fzr(callbacks=...) takes a dict keyed by event name; docs must not show a list."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "doc").glob("*.md"))
    for name in ("on_start", "on_case_start", "on_case_complete", "on_progress", "on_complete"):
        assert name in text, name
    assert "callbacks=[" not in text and "callbacks=[progress_callback]" not in text


# Anchors of the former README's table of contents (external links may still use them)
LEGACY_TOC_ANCHORS = """features installation quick-start cli-usage argument-formats fzi---parse-input-variables
fzc---compile-input-files fzo---read-output-files fzl---list-and-validate-modelscalculators
fzr---run-parametric-calculations fzd---design-of-experiments fz-install--uninstall core-functions
model-definition variable-default-values old-funz-syntax-compatibility formula-evaluation calculator-types
local-shell-execution ssh-remote-execution slurm-workload-manager funz-server-execution cache-calculator
calculator-model-compatibility advanced-features parallel-execution retry-mechanism caching-strategy
output-type-casting progress-callbacks complete-examples interactive-jupyter-notebooks
writing-custom-algorithms-for-fzd configuration environment-variables shell-path-configuration-fz_shell_path
timeout-configuration threat-model interrupt-handling breaking-changes development troubleshooting
performance-tips documentation support""".split()


def test_legacy_readme_anchors_are_kept():
    """Old links README.md#<heading> still land in the README (heading or hidden anchor)."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    present = _anchors(REPO / "README.md") | set(re.findall(r'<a id="([^"]+)"></a>', readme))
    missing = [a for a in LEGACY_TOC_ANCHORS if a not in present]
    assert not missing, f"README lacks legacy anchors for: {missing}"
