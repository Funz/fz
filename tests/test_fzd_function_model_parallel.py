"""
Tests for parallel evaluation of Python-function models in fz.fzd().

fzd(..., model=<callable>, calculators=N, ...) always defaults to N=1
(strictly sequential, one call at a time in the calling thread -- required
for callables that are only safe to invoke from that thread, e.g. an R
closure bridged in via reticulate; the fz.R wrapper always forces
calculators=1 for this reason, see fz.R's own tests).

For calculators=N>1, evaluations of an ordinary, thread-safe Python function
now run concurrently in a thread pool of N workers. If any evaluation
raises while running in parallel, fzd aborts immediately with an explicit
RuntimeError (mentioning parallel execution and suggesting calculators=1),
rather than silently downgrading it to a per-point failure as it does in
the sequential case.
"""
import threading
import time

import pytest

import fz
from fz.core import _run_function_model_design


# ---------------------------------------------------------------------------
# _run_function_model_design: unit tests
# ---------------------------------------------------------------------------

class TestRunFunctionModelDesignSequential:

    def test_sequential_runs_in_calling_thread(self):
        calling_thread = threading.current_thread().ident
        seen_threads = []

        def model_func(x):
            seen_threads.append(threading.current_thread().ident)
            return {"y": x * 2}

        design_points = [{"x": i} for i in range(4)]
        results = _run_function_model_design(model_func, design_points, None, 1)

        assert [r[1] for r in results] == [0, 2, 4, 6]
        assert all(t == calling_thread for t in seen_threads)

    def test_sequential_default_max_workers_none(self):
        # max_workers=None must behave like max_workers=1 (the "calculators
        # omitted" case), not raise or silently do something else.
        results = _run_function_model_design(
            lambda x: {"y": x + 1}, [{"x": 1}, {"x": 2}], None, None
        )
        assert [r[1] for r in results] == [2, 3]

    def test_sequential_per_point_failure_is_tolerated(self):
        def model_func(x):
            if x == 1:
                raise ValueError("boom")
            return {"y": x}

        design_points = [{"x": 0}, {"x": 1}, {"x": 2}]
        results = _run_function_model_design(model_func, design_points, None, 1)

        assert results[0][2] is None and results[0][1] == 0
        assert results[1][2] is not None and "boom" in results[1][2]
        assert results[2][2] is None and results[2][1] == 2


class TestRunFunctionModelDesignParallel:

    def test_parallel_runs_across_multiple_threads(self):
        seen_threads = set()
        lock = threading.Lock()

        def model_func(x):
            with lock:
                seen_threads.add(threading.current_thread().ident)
            time.sleep(0.05)
            return {"y": x * 2}

        design_points = [{"x": i} for i in range(8)]
        start = time.time()
        results = _run_function_model_design(model_func, design_points, None, 4)
        elapsed = time.time() - start

        assert sorted(r[1] for r in results) == [0, 2, 4, 6, 8, 10, 12, 14]
        # 8 points x 0.05s sequentially would take >=0.4s; with 4 workers
        # it should comfortably finish in well under that.
        assert elapsed < 0.35
        # More than one worker thread must actually have been used.
        assert len(seen_threads) > 1

    def test_parallel_error_aborts_and_raises_explicit_runtime_error(self):
        def model_func(x):
            if x == 3:
                raise ValueError("not thread safe")
            return {"y": x}

        design_points = [{"x": i} for i in range(6)]

        with pytest.raises(fz.FunctionModelParallelError) as excinfo:
            _run_function_model_design(model_func, design_points, None, 3)

        message = str(excinfo.value)
        assert "parallel" in message.lower()
        assert "calculators=1" in message
        assert "not thread safe" in message  # original error is chained/included

    def test_parallel_results_preserve_input_order(self):
        # Workers complete out of submission order (later points sleep less);
        # results must still line up with design_points by index.
        def model_func(x):
            time.sleep(0.05 if x == 0 else 0.0)
            return {"y": x}

        design_points = [{"x": i} for i in range(5)]
        results = _run_function_model_design(model_func, design_points, None, 5)
        assert [r[1] for r in results] == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# fzd(): end-to-end tests with a Python function model
# ---------------------------------------------------------------------------

class TestFzdFunctionModelCalculators:

    ALGO_PATH = str(
        __import__("pathlib").Path(__file__).parent.parent
        / "examples" / "algorithms" / "randomsampling.py"
    )

    def test_calculators_defaults_to_one_when_omitted(self):
        calling_thread = threading.current_thread().ident
        seen_threads = []

        def model_func(x, y):
            seen_threads.append(threading.current_thread().ident)
            return {"z": x + y}

        result = fz.fzd(
            input_path=None,
            input_variables={"x": "[0;1]", "y": "[0;1]"},
            model=model_func,
            output_expression="z",
            algorithm=self.ALGO_PATH,
            algorithm_options={"nvalues": 3, "seed": 42},
        )

        assert result is not None
        assert all(t == calling_thread for t in seen_threads)

    def test_calculators_greater_than_one_parallelizes(self):
        seen_threads = set()
        lock = threading.Lock()

        def model_func(x, y):
            with lock:
                seen_threads.add(threading.current_thread().ident)
            time.sleep(0.05)
            return {"z": x + y}

        result = fz.fzd(
            input_path=None,
            input_variables={"x": "[0;1]", "y": "[0;1]"},
            model=model_func,
            output_expression="z",
            algorithm=self.ALGO_PATH,
            calculators=5,
            algorithm_options={"nvalues": 5, "seed": 42},
        )

        assert result is not None
        assert len(seen_threads) > 1

    def test_calculators_zero_or_negative_rejected(self):
        with pytest.raises(ValueError):
            fz.fzd(
                input_path=None,
                input_variables={"x": "[0;1]"},
                model=lambda x: {"y": x},
                output_expression="y",
                algorithm=self.ALGO_PATH,
                calculators=0,
                algorithm_options={"nvalues": 2, "seed": 42},
            )

    def test_calculators_non_int_rejected(self):
        with pytest.raises(TypeError):
            fz.fzd(
                input_path=None,
                input_variables={"x": "[0;1]"},
                model=lambda x: {"y": x},
                output_expression="y",
                algorithm=self.ALGO_PATH,
                calculators="sh://",
                algorithm_options={"nvalues": 2, "seed": 42},
            )

    def test_parallel_error_propagates_as_explicit_fzd_error(self):
        call_count = {"n": 0}
        lock = threading.Lock()

        def model_func(x, y):
            with lock:
                call_count["n"] += 1
                n = call_count["n"]
            if n == 2:
                raise ValueError("simulated crash under concurrency")
            return {"z": x + y}

        with pytest.raises(fz.FunctionModelParallelError, match="parallel"):
            fz.fzd(
                input_path=None,
                input_variables={"x": "[0;1]", "y": "[0;1]"},
                model=model_func,
                output_expression="z",
                algorithm=self.ALGO_PATH,
                calculators=4,
                algorithm_options={"nvalues": 6, "seed": 42},
            )
