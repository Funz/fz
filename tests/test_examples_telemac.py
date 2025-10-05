#!/usr/bin/env python3
"""
Test cases for Telemac examples from examples/examples.md
Auto-generated from examples.md code chunks
Requires: docker
"""

import os
import sys
import shutil
from pathlib import Path
import pytest

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import fz


# Check if docker is available
DOCKER_AVAILABLE = shutil.which("docker") is not None


@pytest.fixture
def telemac_setup(tmp_path):
    """Setup test environment for Telemac examples"""
    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available")

    original_dir = os.getcwd()
    os.chdir(tmp_path)

    # Copy t2d_breach.cas from examples/Telemac (from examples.md lines 123-125)
    examples_telemac = Path(__file__).parent.parent / "examples" / "Telemac"
    if not examples_telemac.exists():
        pytest.skip("examples/Telemac directory not found")

    t2d_path = examples_telemac / "t2d_breach.cas"
    if t2d_path.is_file():
        shutil.copy(t2d_path, ".")
    elif t2d_path.is_dir():
        shutil.copytree(t2d_path, "t2d_breach.cas")

    # Copy .fz directory if it exists (from examples.md lines 127-129)
    if (examples_telemac / ".fz").exists():
        shutil.copytree(examples_telemac / ".fz", ".fz")

    yield tmp_path

    os.chdir(original_dir)


def test_telemac_fzi(telemac_setup):
    """Test Telemac fzi - from examples.md lines 368-375"""
    if not Path("t2d_breach.cas").exists():
        pytest.skip("t2d_breach.cas not found")

    result = fz.fzi("t2d_breach.cas", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#"
    })

    # fzi should identify variables in the file
    assert isinstance(result, dict)


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
@pytest.mark.slow
def test_telemac_fzr(telemac_setup):
    """Test Telemac fzr - from examples.md lines 378-390"""
    if not Path("t2d_breach.cas").exists() or not Path(".fz/calculators/Telemac.sh").exists():
        pytest.skip("Telemac setup files not found")

    result = fz.fzr("t2d_breach.cas", input_variables={}, model={
        "id": "Telemac",
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {
            "S": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_S.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_S.csv\")}))'",
            "H": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_H.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_H.csv\")}))'"
        }
    }, calculators="sh:///bin/bash .fz/calculators/Telemac.sh", results_dir="result")

    assert len(result) >= 1


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")
@pytest.mark.slow
def test_telemac_with_aliases(telemac_setup):
    """Test Telemac with aliases - from examples.md lines 393-395"""
    if not Path("t2d_breach.cas").exists() or not Path(".fz").exists():
        pytest.skip("Telemac setup files not found")

    result = fz.fzr("t2d_breach.cas", input_variables={}, model="Telemac", calculators="*", results_dir="result")

    assert len(result) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
