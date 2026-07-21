"""
Tests for vector (array) outputs used as fzd objectives.

fzd's algorithms (sampling, optimization, ...) all work with a single
scalar objective per case, but the underlying model output can be a vector
(e.g. a time series -- see tests/test_vector_outputs.py and
doc/model-definition.md, "Vector / array outputs"). This suite covers the
reduction step in between: evaluate_output_expression() must offer the
tools to turn a vector-valued output into that scalar (sum, len, mean,
median, stdev, variance, indexing/slicing, on top of the pre-existing
max/min), and must fail with a clear, actionable message -- naming the
vector-valued output(s) and suggesting a reduction -- when an expression
is not reduced to a scalar, instead of a bare float() TypeError.
"""
import json
import math
import os
import shutil

import pytest

import fz
from fz.algorithms import evaluate_output_expression

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash not available on this platform"
)


# ---------------------------------------------------------------------------
# evaluate_output_expression: vector-reduction helpers
# ---------------------------------------------------------------------------

class TestEvaluateOutputExpressionVectorReductions:

    def test_mean(self):
        assert evaluate_output_expression("mean(series)", {"series": [1.0, 2.0, 3.0]}) == 2.0

    def test_sum_and_len(self):
        result = evaluate_output_expression(
            "sum(series) / len(series)", {"series": [1.0, 2.0, 3.0, 4.0]}
        )
        assert result == 2.5

    def test_median(self):
        assert evaluate_output_expression("median(series)", {"series": [1.0, 2.0, 3.0, 4.0]}) == 2.5

    def test_stdev(self):
        result = evaluate_output_expression("stdev(series)", {"series": [1.0, 2.0, 3.0]})
        assert result == pytest.approx(1.0)

    def test_variance(self):
        result = evaluate_output_expression("variance(series)", {"series": [1.0, 2.0, 3.0]})
        assert result == pytest.approx(1.0)

    def test_sorted_then_index(self):
        result = evaluate_output_expression("sorted(series)[0]", {"series": [3.0, 1.0, 2.0]})
        assert result == 1.0

    def test_indexing_and_slicing_unchanged(self):
        # These already worked before this change -- lock them in alongside
        # the new helpers.
        assert evaluate_output_expression("series[-1]", {"series": [1.0, 2.0, 5.0]}) == 5.0
        assert evaluate_output_expression("max(series)", {"series": [1.0, 2.0, 5.0]}) == 5.0
        assert evaluate_output_expression("min(series)", {"series": [1.0, 2.0, 5.0]}) == 1.0

    def test_manual_rms_over_vector(self):
        # sqrt(mean(v**2 for v in series)) -- a realistic fzd objective for
        # a trajectory/time-series output.
        result = evaluate_output_expression(
            "sqrt(sum(v**2 for v in series) / len(series))", {"series": [3.0, 4.0]}
        )
        assert result == pytest.approx(5.0 / math.sqrt(2))

    def test_combining_scalar_and_vector_outputs(self):
        result = evaluate_output_expression(
            "scale * mean(series)", {"series": [1.0, 2.0, 3.0], "scale": 10.0}
        )
        assert result == 20.0


class TestEvaluateOutputExpressionVectorErrors:

    def test_unreduced_vector_raises_clear_error(self):
        with pytest.raises(ValueError) as exc_info:
            evaluate_output_expression("T_series", {"T_series": [1.0, 2.0, 3.0]})
        message = str(exc_info.value)
        assert "T_series" in message
        assert "vector-valued" in message
        # Should suggest at least one concrete reduction
        assert "mean(T_series)" in message or "sum(T_series)" in message

    def test_unreduced_vector_names_only_the_vector_keys(self):
        with pytest.raises(ValueError) as exc_info:
            evaluate_output_expression(
                "T_series", {"T_series": [1.0, 2.0], "pressure": 101.325}
            )
        message = str(exc_info.value)
        # The hint lists the vector-valued output(s) only -- a co-existing
        # scalar output ("pressure") must not be flagged as vector-valued.
        assert "['T_series']" in message
        assert "pressure" not in message

    def test_undefined_name_error_unchanged(self):
        """Regression: referencing an unknown output must still raise clearly."""
        with pytest.raises(ValueError) as exc_info:
            evaluate_output_expression("x + z", {"x": 1.0})
        assert "not defined" in str(exc_info.value)


# ---------------------------------------------------------------------------
# End-to-end: fzd() with a vector-output model and a reducing output_expression
# ---------------------------------------------------------------------------

@requires_bash
class TestFzdVectorOutputIntegration:

    @pytest.fixture
    def vector_output_model(self):
        """
        A toy 'simulation': prints an exponential-decay time series to
        series.json, given n_steps and T0. Same shape as
        tests/test_vector_outputs.py / examples/vector_outputs_example.md,
        reused here to feed fzd's output_expression reduction step.
        """
        with open("input.txt", "w") as f:
            f.write("T0=${T0}\n")

        with open("run_case.sh", "w", newline="\n") as f:
            f.write("#!/bin/bash\n")
            f.write("source input.txt\n")
            f.write(
                "python3 -c \"\n"
                "import json\n"
                "n = 4\n"
                "T0 = float($T0)\n"
                "series = [round(T0 * (0.9 ** i), 3) for i in range(n)]\n"
                "print(json.dumps(series))\n"
                "\" > series.json\n"
            )
        os.chmod("run_case.sh", 0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"T_series": "python://json_file('series.json')"},
        }
        return model

    def test_fzd_with_mean_reduced_vector_output(self, vector_output_model):
        algo_path = str(
            __import__("pathlib").Path(__file__).parent.parent
            / "examples" / "algorithms" / "randomsampling.py"
        )

        result = fz.fzd(
            input_path="input.txt",
            input_variables={"T0": "[50;200]"},
            model=vector_output_model,
            output_expression="mean(T_series)",
            algorithm=algo_path,
            calculators="sh://bash run_case.sh",
            algorithm_options={"nvalues": 3, "seed": 42},
        )

        assert result is not None
        df = result["XY"]
        assert len(df) == 3
        assert "T0" in df.columns
        assert "mean(T_series)" in df.columns

        # Recompute the expected mean directly from T0, and check every row
        for _, row in df.iterrows():
            t0 = row["T0"]
            expected_series = [round(t0 * (0.9 ** i), 3) for i in range(4)]
            expected_mean = sum(expected_series) / len(expected_series)
            assert row["mean(T_series)"] == pytest.approx(expected_mean, rel=1e-6)

    def test_fzd_unreduced_vector_output_reports_failed_points(self, vector_output_model):
        """
        Forgetting to reduce a vector output must not crash fzd(): each
        point is reported as a failed evaluation (output value None), with
        the clear error surfaced via log_warning -- exactly like any other
        per-case evaluation failure.
        """
        algo_path = str(
            __import__("pathlib").Path(__file__).parent.parent
            / "examples" / "algorithms" / "randomsampling.py"
        )

        result = fz.fzd(
            input_path="input.txt",
            input_variables={"T0": "[50;200]"},
            model=vector_output_model,
            output_expression="T_series",  # not reduced -- every point fails
            algorithm=algo_path,
            calculators="sh://bash run_case.sh",
            algorithm_options={"nvalues": 2, "seed": 42},
        )

        assert result is not None
        df = result["XY"]
        assert len(df) == 2
        assert df["T_series"].isna().all()
