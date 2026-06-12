"""
Test that funz:// UDP discovery failures do not count as hard failures
and that the case switches to other available calculators (e.g. sh://).

With the OLD implementation:
  max_retries=2 + calculators=[funz1, funz2, sh://success]
  → UDP misses consume both retry slots; sh:// is never tried; case fails.

With the NEW implementation:
  → UDP misses are not counted as hard failures; sh:// is tried and succeeds.
"""
import time
import pytest
from pathlib import Path
from unittest.mock import patch

import fz.config as fz_config
from fz.helpers import try_calculators_with_retry, get_calculator_manager


def _udp_miss(calc_uri):
    """Simulate a funz:// UDP discovery timeout."""
    port = calc_uri.split(":")[2].split("/")[0]
    return {"status": "error", "error": f"No calculator found on UDP port {port}"}


def _sh_success(calc_uri):
    return {"status": "done", "output": {}, "calculator_uri": calc_uri}


def _mock_run(tmp_dir, calculator_uri, model, timeout,
              original_input_was_dir, original_cwd, input_files_list):
    if calculator_uri.startswith("funz://"):
        return _udp_miss(calculator_uri)
    if calculator_uri.startswith("sh://"):
        return _sh_success(calculator_uri)
    return {"status": "error", "error": "Unknown calculator"}


def test_funz_udp_miss_falls_back_to_sh_calculator():
    """
    When funz calculators fail with UDP timeout the case must fall back to
    the next available calculator (sh://) and succeed.

    With max_retries=2 and [funz1, funz2, sh://success]:
    - OLD code: exhausts 2 retries on funz UDP misses → case FAILS  (test fails)
    - NEW code: UDP misses don't consume retry slots   → case PASSES via sh://
    """
    # Set max_retries to 2 — fewer than the 3 calculators in the list
    orig_max_retries = fz_config.config.max_retries
    fz_config.config.max_retries = 2

    calc_mgr = get_calculator_manager()
    calc_uris = [
        "funz://:59001/TestCode",
        "funz://:59002/TestCode",
        "sh://echo done",
    ]
    calc_ids = calc_mgr.register_calculator_instances(calc_uris)

    try:
        with patch("fz.runners.run_single_case_calculation", _mock_run):
            result, used_calc_id = try_calculators_with_retry(
                non_cache_calculator_ids=calc_ids,
                case_index=0,
                tmp_dir=Path("."),
                model={"output": {}},
                original_input_was_dir=False,
                thread_id=0,
                start_time=time.time(),
                original_cwd=".",
                input_files_list=[],
                timeout=5,
            )

        assert result["status"] == "done", (
            f"Expected case to succeed via sh:// fallback, but got: {result}"
        )
        used_uri = calc_mgr.get_original_uri(used_calc_id)
        assert used_uri.startswith("sh://"), (
            f"Expected sh:// calculator to be used, got: {used_uri}"
        )
    finally:
        fz_config.config.max_retries = orig_max_retries
        calc_mgr.cleanup_all_calculators()
