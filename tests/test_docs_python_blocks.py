"""Every ```python block in README.md and doc/ must be valid Python (after dedenting).

Transcripts, pseudo-code, shell sessions and Jupyter magics belong in ```text / ```bash /
```ipython blocks (or must be commented out), not in ```python ones."""
import ast
import glob
import re
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLOCK_RE = re.compile(r"^([ \t]*)(`{3,})python\n(.*?)^\1\2\s*$", re.S | re.M)


def test_python_blocks_in_docs_are_valid_python():
    files = [REPO / "README.md"] + [Path(p) for p in sorted(glob.glob(str(REPO / "doc" / "*.md")))]
    bad = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in BLOCK_RE.finditer(text):
            try:
                ast.parse(textwrap.dedent(m.group(3)))
            except SyntaxError as e:
                bad.append(f"{f.relative_to(REPO)}:{text[:m.start()].count(chr(10)) + 2}: {e.msg}")
    assert not bad, "invalid ```python blocks:\n" + "\n".join(bad)
