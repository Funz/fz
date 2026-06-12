"""
Regression tests for calculator alias resolution:

- fzd with calculators omitted must auto-discover installed calculator aliases
  bound to the model id, exactly like fzr (it used to resolve calculators
  before reading the model id, producing an empty sh:// command and failing
  every case).
- fzr must accept a calculator alias resolved to a dict (the CLI resolves bare
  alias names to their JSON content; fzr used to reject non-string elements).
"""
import json
from pathlib import Path

import pytest

pytest.importorskip("pandas")

import fz


ALGORITHM = '''#title: TwoPoints test algorithm
class TwoPoints:
    def __init__(self, **options):
        pass

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.25}, {"x": 0.75}]

    def get_next_design(self, previous_input_vars, previous_output_values):
        return []

    def get_analysis(self, input_vars, output_values):
        return {"text": "ok", "data": {"n": len(output_values)}}
'''


def _write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="\n") as f:
        f.write(content)


def _setup_installed_wrapper():
    """Simulate an installed fz wrapper: model alias + calculator alias + runner"""
    _write("input.txt", "x=$x\n")
    _write("calc.sh", "#!/bin/bash\nsource $1\necho \"y = $x\" > output.txt\n")
    _write(".fz/models/pg.json", json.dumps({
        "id": "pg",
        "varprefix": "$",
        "output": {"y": "grep 'y = ' output.txt | awk '{print $3}'"},
    }))
    _write(".fz/calculators/localhost_pg.json", json.dumps({
        "uri": "sh://",
        "models": {"pg": "bash calc.sh"},
    }))


def test_fzd_autodiscovers_installed_calculator():
    """fzd with calculators omitted finds the installed alias for the model"""
    _setup_installed_wrapper()
    _write("algo.py", ALGORITHM)

    result = fz.fzd(
        "input.txt",
        {"x": "[0;1]"},
        "pg",
        output_expression="y",
        algorithm="algo.py",
        # calculators intentionally omitted: must auto-discover localhost_pg
    )

    xy = result["XY"]
    assert len(xy) == 2
    assert sorted(xy["x"].tolist()) == [0.25, 0.75]
    assert sorted(xy["y"].tolist()) == [0.25, 0.75]


def test_fzr_accepts_calculator_dict():
    """fzr accepts an alias resolved to a dict (as the CLI produces)"""
    _setup_installed_wrapper()
    calculator_dict = json.loads(Path(".fz/calculators/localhost_pg.json").read_text())

    results = fz.fzr(
        "input.txt",
        {"x": [0.5]},
        "pg",
        results_dir="results_dict",
        calculators=[calculator_dict],
    )

    assert list(results["status"]) == ["done"]
    assert list(results["y"]) == [0.5]
