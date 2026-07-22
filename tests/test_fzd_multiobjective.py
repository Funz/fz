"""
Tests for fzd multi-objective (vector) output_expression support and the
NSGA-II example algorithm.

Complements tests/test_fzd_vector_outputs.py (vector-valued model OUTPUTS
reduced to a scalar objective): here the OBJECTIVE itself is a vector,
i.e. output_expression is a list of expressions.
"""
import csv
import math
import os

import pytest

from fz import fzd
from fz.algorithms import evaluate_output_expressions

NSGA2 = os.path.join(os.path.dirname(__file__), "..", "examples", "algorithms", "nsga2.py")


# ---------------------------------------------------------------------------
# Unit: evaluate_output_expressions
# ---------------------------------------------------------------------------

class TestEvaluateOutputExpressions:
    def test_string_keeps_scalar_behavior(self):
        assert evaluate_output_expressions("x + y * 2", {"x": 1.0, "y": 3.0}) == 7.0

    def test_list_returns_one_scalar_per_expression(self):
        out = evaluate_output_expressions(["x", "y * 2", "x - y"], {"x": 1.0, "y": 3.0})
        assert out == [1.0, 6.0, -2.0]

    def test_list_with_vector_output_reductions(self):
        data = {"Tser": [10.0, 20.0, 30.0]}
        out = evaluate_output_expressions(["min(Tser)", "max(Tser)"], data)
        assert out == [10.0, 30.0]

    def test_list_failure_names_offending_expression(self):
        with pytest.raises(ValueError, match="does_not_exist"):
            evaluate_output_expressions(["x", "does_not_exist + 1"], {"x": 1.0})

    def test_tuple_accepted(self):
        assert evaluate_output_expressions(("x", "x + 1"), {"x": 2.0}) == [2.0, 3.0]


# ---------------------------------------------------------------------------
# End-to-end: fzd with a list of objectives (function-model mode)
# ---------------------------------------------------------------------------

def _binh_korn(x, y):
    """Classic bi-objective test problem (constrained variant omitted).

    f1 = 4x^2 + 4y^2 ; f2 = (x-5)^2 + (y-5)^2, x in [0;5], y in [0;3].
    Known Pareto set: y = min(x, 3), x in [0;5] -> smooth convex front.
    """
    return {"f1": 4*x**2 + 4*y**2, "f2": (x - 5)**2 + (y - 5)**2}


class TestFzdMultiObjective:
    def test_fzd_vector_objectives_with_nsga2(self):
        result = fzd(
            None,
            {"x": "[0;5]", "y": "[0;3]"},
            _binh_korn,
            ["f1", "f2"],
            NSGA2,
            algorithm_options={"pop_size": 32, "generations": 40, "seed": 7},
            calculators=1,
        )
        # XY DataFrame: one column per objective expression
        assert "f1" in result["XY"].columns and "f2" in result["XY"].columns
        assert len(result["XY"]) == 32 * 40

        # Pareto front from the algorithm analysis
        X = result["analysis"]["data"]["pareto_X"]
        F = result["analysis"]["data"]["pareto_F"]
        assert len(F) >= 10

        # Front quality in OBJECTIVE space: distance to the analytic front.
        # (The decision-space valley of Binh-Korn is flat, so objective-space
        # proximity is the meaningful convergence criterion.)
        true_front = [(4*t**2 + 4*min(t, 3)**2, (t - 5)**2 + (min(t, 3) - 5)**2)
                      for t in [k/200*5 for k in range(201)]]
        s1, s2 = 136.0, 46.0  # objective scales over the front
        for (x, y), (f1, f2) in zip(X, F):
            assert f1 == pytest.approx(4*x**2 + 4*y**2, rel=1e-9)
            d = min(math.hypot((f1 - g1)/s1, (f2 - g2)/s2) for g1, g2 in true_front)
            assert d < 0.03, f"front point too far from analytic front: ({f1:.2f}, {f2:.2f}), d={d:.4f}"

        # Front spread: reaches toward both extremes
        f1s = [f for f, _ in F]
        assert min(f1s) < 5 and max(f1s) > 80

        # nsga2_pareto.csv written and consistent
        rows = list(csv.DictReader(open("nsga2_pareto.csv")))
        assert len(rows) == len(F)
        assert set(rows[0].keys()) == {"x", "y", "objective_1", "objective_2"}

    def test_fzd_scalar_expression_unchanged(self):
        # Backward compatibility: plain-string objective, mono-objective algorithm
        algo = os.path.join(os.path.dirname(__file__), "..", "examples",
                            "algorithms", "randomsampling.py")
        result = fzd(
            None,
            {"x": "[0;1]"},
            lambda x: {"f": (x - 0.3)**2},
            "f",
            algo,
            algorithm_options={"n_samples": 10, "seed": 1},
            calculators=1,
        )
        assert "f" in result["XY"].columns
        vals = result["XY"]["f"].tolist()
        assert all(isinstance(v, float) and not isinstance(v, list) for v in vals)

    def test_fzd_partial_objective_failure_gives_none_point(self):
        # One expression valid, one invalid -> the point fails as a whole (None),
        # NSGA-II treats it as dominated; the run must complete.
        result = fzd(
            None,
            {"x": "[0;5]", "y": "[0;3]"},
            _binh_korn,
            ["f1", "nonexistent_output"],
            NSGA2,
            algorithm_options={"pop_size": 8, "generations": 3, "seed": 0},
            calculators=1,
        )
        assert result["total_evaluations"] == 8 * 3
        assert "(0 valid)" in result["summary"]
