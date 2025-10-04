#!/usr/bin/env python3
"""
Test cases for Modelica examples from examples/examples.md
Auto-generated from examples.md code chunks
Requires: omc (OpenModelica compiler)
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


# Check if omc is available
OMC_AVAILABLE = shutil.which("omc") is not None


@pytest.fixture
def modelica_setup(tmp_path):
    """Setup test environment for Modelica examples"""
    if not OMC_AVAILABLE:
        pytest.skip("omc (OpenModelica compiler) not available")

    original_dir = os.getcwd()
    os.chdir(tmp_path)

    # Create NewtonCooling.mo (from examples.md lines 59-73)
    with open("NewtonCooling.mo", "w") as f:
        f.write("""model NewtonCooling "An example of Newton s law of cooling"
  parameter Real T_inf=25 "Ambient temperature";
  parameter Real T0=90 "Initial temperature";
  parameter Real h=$(convection) "Convective cooling coefficient";
  parameter Real A=1.0 "Surface area";
  parameter Real m=0.1 "Mass of thermal capacitance";
  parameter Real c_p=1.2 "Specific heat";
  Real T "Temperature";
initial equation
  T = T0 "Specify initial value for T";
equation
  m*c_p*der(T) = h*A*(T_inf-T) "Newton s law of cooling";
end NewtonCooling;
""")

    # Create Modelica.sh (from examples.md lines 75-103)
    with open("Modelica.sh", "w") as f:
        f.write("""#!/bin/bash

if [ ! ${1: -4} == ".mos" ]; then
  model=`grep "model" $1 | awk '{print $2}'`
  cat > $1.mos <<- EOM
loadModel(Modelica);
loadFile("$1");
simulate($model, stopTime=1,tolerance=0.001,outputFormat="csv");
EOM
  omc $1.mos > $1.moo 2>&1 &
else
  omc $1 > $1.moo 2>&1 &
fi

PID_OMC=$!
echo $PID_OMC >> PID #this will allow Funz to kill process if needed

wait $PID_OMC

rm -f PID

ERROR=`cat *.moo | grep "Failed"`
if [ ! "$ERROR" == "" ]; then
    echo $ERROR >&2
    exit 1
fi
""")
    os.chmod("Modelica.sh", 0o755)

    yield tmp_path

    os.chdir(original_dir)


def test_modelica_fzi(modelica_setup):
    """Test Modelica fzi - from examples.md lines 302-310"""
    result = fz.fzi("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    })

    assert "convection" in result


def test_modelica_fzc(modelica_setup):
    """Test Modelica fzc - from examples.md lines 313-323"""
    fz.fzc("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    }, {
        "convection": 123
    }, output_dir="output")

    assert Path("output").exists()


@pytest.mark.skipif(not OMC_AVAILABLE, reason="omc not available")
def test_modelica_fzr(modelica_setup):
    """Test Modelica fzr - from examples.md lines 326-344"""
    results = fz.fzr("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    }, {
        "convection": [.123, .456, .789],
    }, calculators="sh:///bin/bash ./Modelica.sh", results_dir="results")

    assert len(results) == 3
    assert all(results["status"] == "done")


@pytest.mark.skipif(not OMC_AVAILABLE, reason="omc not available")
def test_modelica_fzo(modelica_setup):
    """Test Modelica fzo - from examples.md lines 347-349"""
    # First run fzr to create results
    fz.fzr("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    }, {
        "convection": [.123, .456, .789],
    }, calculators="sh:///bin/bash ./Modelica.sh", results_dir="results")

    # Test fzo
    result = fz.fzo("results", {"output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}})

    assert len(result) == 3


@pytest.mark.skipif(not OMC_AVAILABLE, reason="omc not available")
def test_modelica_cache(modelica_setup):
    """Test Modelica with cache - from examples.md lines 352-363"""
    # First run to populate cache
    fz.fzr("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    }, {
        "convection": [.123, .456, .789],
    }, calculators="sh:///bin/bash ./Modelica.sh", results_dir="results_cache")

    # Second run with cache
    result = fz.fzr("NewtonCooling.mo", {
        "varprefix": "$",
        "formulaprefix": "@",
        "delim": "()",
        "commentline": "#",
        "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'}"}
    }, {
        "convection": [.123, .456, .789],
    }, calculators=["cache://results_cache*", "sh:///bin/bash ./Modelica.sh"], results_dir="results_cache")

    assert len(result) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
