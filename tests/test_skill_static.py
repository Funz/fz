"""
Static validation of the agent skill in skills/fz/.

These tests need no API key and no claude CLI: they check that the skill is
well-formed (frontmatter, links) and that everything it claims about fz still
matches the code (CLI flags, env vars, defaults, Python signatures), so the
skill cannot silently drift from the implementation.
"""
import inspect
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "skills" / "fz"
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_FILES = sorted(SKILL_DIR.glob("*.md"))
CLI_SRC = (REPO / "fz" / "cli.py").read_text(encoding="utf-8")
FZ_SRC = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "fz").glob("*.py"))


def _frontmatter() -> str:
    text = SKILL_MD.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md must start with a --- frontmatter block"
    return m.group(1)


def _frontmatter_description() -> str:
    lines = _frontmatter().splitlines()
    desc_lines = []
    in_desc = False
    for line in lines:
        if line.startswith("description:"):
            in_desc = True
            rest = line.split(":", 1)[1].strip()
            if rest and rest not in (">", ">-", "|", "|-"):
                desc_lines.append(rest)
        elif in_desc:
            if line.startswith((" ", "\t")):
                desc_lines.append(line.strip())
            else:
                in_desc = False
    return " ".join(desc_lines)


class TestSkillFormat:
    """Skill files are well-formed per the agent skills format"""

    def test_skill_files_exist(self):
        assert SKILL_MD.exists()
        assert (SKILL_DIR / "reference.md").exists()
        assert (SKILL_DIR / "algorithms.md").exists()

    def test_name_matches_directory(self):
        name = re.search(r"^name:\s*(\S+)", _frontmatter(), re.M)
        assert name, "frontmatter must define 'name'"
        assert name.group(1) == SKILL_DIR.name == "fz"

    def test_description(self):
        desc = _frontmatter_description()
        assert desc, "frontmatter must define a non-empty 'description'"
        assert len(desc) <= 1024, f"description too long ({len(desc)} > 1024 chars)"
        # The description is the trigger: it should mention the package and commands
        assert "fz" in desc

    def test_relative_links_resolve(self):
        broken = []
        for md in SKILL_FILES:
            for label, target in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target_path = SKILL_DIR / target.split("#")[0]
                if not target_path.exists():
                    broken.append(f"{md.name}: [{label}]({target})")
        assert not broken, f"broken relative links: {broken}"


class TestSkillCodeDrift:
    """Claims made by the skill still match the fz code"""

    def test_documented_cli_flags_exist(self):
        """Every --flag mentioned in the skill is a real argparse option"""
        # Any double-quoted long flag in cli.py is an argparse option string
        # (including aliases like --variables given as secondary option strings)
        real_flags = set(re.findall(r'"(--[a-z][a-z_-]*)"', CLI_SRC))
        real_flags |= set(re.findall(r'"(-[a-z])"', CLI_SRC))
        real_flags |= {"--help", "--version"}
        documented = set()
        for md in SKILL_FILES:
            documented |= set(
                re.findall(r"(?<!-)(--[a-z][a-z_-]*)", md.read_text(encoding="utf-8"))
            )
        unknown = documented - real_flags
        assert not unknown, f"skill documents CLI flags that do not exist: {sorted(unknown)}"

    def test_documented_format_choices(self):
        """--format values listed in reference.md equal the argparse choices"""
        code_choices = set()
        for block in re.findall(r"choices=\[([^\]]+)\]", CLI_SRC):
            code_choices |= {c.strip().strip("\"'") for c in block.split(",")}
        ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
        m = re.search(r"`--format` accepts: (.+?)\.", ref)
        assert m, "reference.md must list the --format choices"
        documented = set(re.findall(r"`(\w+)`", m.group(1)))
        assert documented == code_choices, (
            f"documented formats {sorted(documented)} != argparse choices {sorted(code_choices)}"
        )

    def test_documented_env_vars_exist(self):
        """Every FZ_* env var mentioned in the skill appears in the source"""
        documented = set()
        for md in SKILL_FILES:
            documented |= set(re.findall(r"\b(FZ_[A-Z_]+)\b", md.read_text(encoding="utf-8")))
        missing = {v for v in documented if v not in FZ_SRC}
        assert not missing, f"skill documents env vars not found in fz/: {sorted(missing)}"

    def test_documented_retry_default(self):
        """The retry default stated in the skill matches fz/config.py"""
        code = re.search(r"FZ_MAX_RETRIES',\s*'(\d+)'", (REPO / "fz" / "config.py").read_text(encoding="utf-8"))
        assert code, "FZ_MAX_RETRIES default not found in config.py"
        ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
        doc = re.search(r"FZ_MAX_RETRIES\s+\D*\(default (\d+)\)", ref)
        assert doc, "reference.md must state the FZ_MAX_RETRIES default"
        assert doc.group(1) == code.group(1)

    def test_python_api_signatures(self):
        """Parameter names and key defaults documented in reference.md exist in fz"""
        import fz

        documented = {
            "fzi": {"input_path", "model"},
            "fzc": {"input_path", "input_variables", "model", "output_dir"},
            "fzo": {"output_path", "model"},
            "fzr": {
                "input_path", "input_variables", "model", "results_dir",
                "calculators", "callbacks", "timeout",
            },
            "fzd": {
                "input_path", "input_variables", "model", "output_expression",
                "algorithm", "calculators", "algorithm_options", "analysis_dir",
            },
            "fzl": {"models", "calculators", "check"},
        }
        for func_name, params in documented.items():
            actual = set(inspect.signature(getattr(fz, func_name)).parameters)
            missing = params - actual
            assert not missing, f"fz.{func_name} lost documented parameters: {sorted(missing)}"

        assert inspect.signature(fz.fzr).parameters["results_dir"].default == "results"
        assert inspect.signature(fz.fzc).parameters["output_dir"].default == "output"
        assert inspect.signature(fz.fzd).parameters["analysis_dir"].default == "analysis"

    def test_six_core_functions_exported(self):
        import fz

        for name in ("fzi", "fzc", "fzo", "fzr", "fzl", "fzd"):
            assert hasattr(fz, name), f"fz.{name} missing from public API"
