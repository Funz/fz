"""
Guards the Claude Code plugin in plugins/fz/ against changes that the Claude
plugin directory (the catalog the plugin is submitted to) would refuse.

The directory only accepts, from organizations that are not Verified, a plugin
folder made of Markdown, text, JSON, YAML and images, with no scripts, no
package-manager files, no install/download commands and no API-key variables.
These tests re-check the rules that can be checked offline. When the `claude`
CLI is installed, the official validator also runs (directory profile, strict).

The directory runs more checks (safety scan, policy review, name similarity)
than these: after a change, still re-validate in the developer portal.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "fz"
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
ICON = PLUGIN / ".claude-plugin" / "icon.png"

TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
# Extensionless files the directory keeps (license, readme, .gitignore)
ALLOWED_PLAIN_NAMES = {"license", "licence", "readme", "copying", "notice", ".gitignore"}

FORBIDDEN_NAMES = {
    "claude.md", "claude.local.md", "agents.md",
    "requirements.txt", "package.json", "package-lock.json", "pnpm-lock.yaml",
    "pnpm-workspace.yaml", "yarn.lock", "pyproject.toml", "setup.py", "setup.cfg",
    "pipfile", "pipfile.lock", "poetry.lock", "uv.lock", "environment.yml",
    "description", "gemfile", "cargo.toml", "go.mod", ".npmrc", "pip.conf",
    "hooks.json", ".lsp.json", "monitors.json", ".mcp.json",
}
FORBIDDEN_DIRS = {"node_modules", "hooks", "bin", "scripts", "agents", "output-styles"}

# Text the directory flags as installing/downloading code, changing package
# sources, or reading secrets. Link to https://github.com/Funz/fz#installation
# (or the tool's own install page) instead.
FORBIDDEN_PATTERNS = {
    "pip install": r"\bpip3?\s+install\b",
    "pipx/uv/conda install": r"\b(pipx|uv\s+(pip|tool|add)|conda|mamba)\s+install\b",
    "npm/npx": r"\b(npm|npx|pnpm|yarn)\s+\w",
    "apt/brew/dnf install": r"\b(apt(-get)?|brew|dnf|yum|pacman)\s+(-\S+\s+)*install\b",
    "curl/wget download": r"\b(curl|wget)\s",
    "git clone": r"\bgit\s+clone\b",
    "R package install": r"install\.packages\s*\(|remotes::|devtools::",
    "package index override": r"--(extra-)?index-url|\bgit\+https?://",
    "pipe to shell": r"\|\s*(ba|z)?sh\b",
    "API key variable": r"\b[A-Z][A-Z0-9_]*_(API_KEY|TOKEN|SECRET)\b",
    "password in a URI": r"\[:password\]|://[^\s/@]+:[^\s/@]+@",
}

MAX_TEXT_BYTES = 256 * 1024
MAX_FILES = 512


def plugin_files():
    return sorted(p for p in PLUGIN.rglob("*") if p.is_file() or p.is_symlink())


def rel(p: Path) -> str:
    return p.relative_to(PLUGIN).as_posix()


def text_files():
    return [p for p in plugin_files() if p.suffix.lower() not in IMAGE_SUFFIXES]


def frontmatter(path: Path) -> str:
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", path.read_text(encoding="utf-8"), re.S)
    assert m, f"{rel(path)} must start with a --- frontmatter block"
    return m.group(1)


class TestPluginFiles:
    """Only file kinds the directory accepts from a non-Verified organization"""

    def test_plugin_folder_exists(self):
        assert MANIFEST.is_file(), "plugins/fz/.claude-plugin/plugin.json is missing"

    def test_allowed_file_types_only(self):
        bad = []
        for p in plugin_files():
            suffix = p.suffix.lower()
            if suffix in TEXT_SUFFIXES | IMAGE_SUFFIXES:
                continue
            if suffix == "" and p.name.lower() in ALLOWED_PLAIN_NAMES:
                continue
            bad.append(rel(p))
        assert not bad, f"only Markdown/text/JSON/YAML/images are accepted: {bad}"

    def test_no_symlinks(self):
        links = [rel(p) for p in PLUGIN.rglob("*") if p.is_symlink()]
        assert not links, f"symlinks are not portable in a plugin: {links}"

    def test_no_forbidden_names(self):
        bad = [rel(p) for p in plugin_files() if p.name.lower() in FORBIDDEN_NAMES]
        assert not bad, f"files the directory refuses (CLAUDE.md, package manifests, ...): {bad}"

    def test_no_forbidden_dirs(self):
        bad = sorted({rel(p) for p in PLUGIN.rglob("*")
                      if p.is_dir() and p.name.lower() in FORBIDDEN_DIRS})
        nested = [rel(p) for p in PLUGIN.rglob(".claude*")
                  if p.is_dir() and p != PLUGIN / ".claude-plugin"]
        assert not bad + nested, f"folders the directory refuses: {bad + nested}"

    def test_claude_plugin_folder_holds_manifest_and_images_only(self):
        bad = [p.name for p in (PLUGIN / ".claude-plugin").iterdir()
               if p.name != "plugin.json" and p.suffix.lower() not in IMAGE_SUFFIXES]
        assert not bad, f"unexpected files in plugins/fz/.claude-plugin: {bad}"

    def test_file_count(self):
        assert len(plugin_files()) <= MAX_FILES

    def test_portable_paths(self):
        bad = [rel(p) for p in plugin_files()
               if not re.fullmatch(r"[A-Za-z0-9._/-]+", rel(p))]
        assert not bad, f"paths with characters not every system keeps: {bad}"

    def test_text_files_readable(self):
        problems = []
        for p in text_files():
            data = p.read_bytes()
            if data.startswith(b"#!"):
                problems.append(f"{rel(p)}: starts with #!")
            if b"\0" in data:
                problems.append(f"{rel(p)}: NUL byte")
            if len(data) > MAX_TEXT_BYTES:
                problems.append(f"{rel(p)}: {len(data)} bytes > 256 KB (not fully read)")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{rel(p)}: not UTF-8")
        assert not problems, problems

    def test_images_hold_no_archive(self):
        bad = [rel(p) for p in plugin_files()
               if p.suffix.lower() in IMAGE_SUFFIXES and b"PK\x03\x04" in p.read_bytes()]
        assert not bad, f"images that look like they hold a zip archive: {bad}"


class TestPluginText:
    """No install/download commands, package-source changes or secrets in the text"""

    @pytest.mark.parametrize("label,pattern", sorted(FORBIDDEN_PATTERNS.items()))
    def test_no_flagged_text(self, label, pattern):
        rx = re.compile(pattern)
        hits = []
        for p in text_files():
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel(p)}:{n}: {line.strip()[:100]}")
        assert not hits, (f"{label} is flagged by the plugin directory; link to "
                          f"https://github.com/Funz/fz#installation instead:\n" + "\n".join(hits))

    def test_relative_links_stay_inside_plugin(self):
        broken = []
        for p in plugin_files():
            if p.suffix.lower() != ".md":
                continue
            for target in re.findall(r"\]\(([^)\s]+)\)", p.read_text(encoding="utf-8")):
                if re.match(r"[a-z][a-z0-9+.-]*:|#", target):
                    continue
                dest = (p.parent / target.split("#")[0]).resolve()
                if not dest.exists() or PLUGIN.resolve() not in (dest, *dest.parents):
                    broken.append(f"{rel(p)} -> {target}")
        assert not broken, f"links that break once only plugins/fz is installed: {broken}"


class TestManifests:
    """plugin.json, marketplace.json and the listing icon"""

    def test_plugin_json(self):
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert m["name"] == "fz"  # /fz:* commands and fz@funz depend on it
        for key in ("displayName", "description", "version", "author", "license", "homepage"):
            assert m.get(key), f"plugin.json lacks {key}"
        assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"]), "version must be semver x.y.z"

    def test_plugin_version_follows_fz(self):
        # read the source, not an installed (possibly stale) fz
        src = (REPO / "fz" / "__init__.py").read_text(encoding="utf-8")
        version = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)", src, re.M).group(1)
        plugin = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"].split(".")
        package = version.split(".")
        package += ["0"] * (3 - len(package))
        assert plugin[:2] == package[:2], (
            f"plugin.json version {'.'.join(plugin)} does not follow fz {version}")

    def test_marketplace_points_to_plugin_folder(self):
        mk = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        entry = next(p for p in mk["plugins"] if p["name"] == "fz")
        assert entry["source"] == "./plugins/fz", "submitting the repo root would be refused"
        version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
        assert mk.get("metadata", {}).get("version", version) == version

    def test_icon(self):
        assert ICON.is_file(), "listing icon missing"
        data = ICON.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", "icon must be a PNG"
        width, height = struct.unpack(">II", data[16:24])
        assert width == height, f"icon must be square, got {width}x{height}"
        assert 512 <= width <= 2048, f"icon side must be 512-2048 px, got {width}"
        assert len(data) < 2 * 1024 * 1024, "icon must be under 2 MB"


class TestFrontmatter:
    """YAML frontmatter of skills and commands parses, with string values"""

    @pytest.mark.parametrize("path", sorted((PLUGIN / "commands").glob("*.md"))
                             + sorted((PLUGIN / "skills").glob("*/SKILL.md")),
                             ids=lambda p: rel(p))
    def test_frontmatter_values_are_strings(self, path):
        yaml = pytest.importorskip("yaml")
        data = yaml.safe_load(frontmatter(path))
        assert isinstance(data, dict) and data.get("description"), "description is required"
        for key in ("description", "argument-hint", "name", "license"):
            if key in data:
                assert isinstance(data[key], str), (
                    f"{key} must be a string (quote it): got {type(data[key]).__name__}")


class TestLegacySkillPath:
    def test_skills_fz_points_to_plugin(self):
        legacy = REPO / "skills" / "fz"
        if not legacy.is_symlink():
            pytest.skip("skills/fz is not checked out as a symlink (e.g. Windows)")
        assert legacy.resolve() == (PLUGIN / "skills" / "fz").resolve()


def _claude(*args):
    return subprocess.run(["claude", "plugin", "validate", *args], capture_output=True,
                          text=True, timeout=120, shell=sys.platform == "win32")


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_official_validator():
    """`claude plugin validate --strict` (no API call), with the directory profile
    when this claude build offers it (`--profile` is not available in every
    environment, even at the same version)"""
    if os.environ.get("FZ_SKILL_E2E") == "0":
        pytest.skip("FZ_SKILL_E2E=0")
    plugin_args = [str(PLUGIN), "--strict"]
    if "--profile" in _claude("--help").stdout:
        plugin_args += ["--profile", "directory"]
    for args in (plugin_args, [str(MARKETPLACE)]):
        r = _claude(*args)
        assert r.returncode == 0, (f"claude plugin validate {' '.join(args)} failed:\n"
                                   f"{r.stdout}\n{r.stderr}")
