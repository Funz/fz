#!/usr/bin/env python3
"""
Test R algorithm loading and integration with fzd

This test suite verifies that:
1. R algorithms can be loaded via rpy2
2. RAlgorithmWrapper correctly wraps R S3 class instances
3. All algorithm methods work correctly (get_initial_design, get_next_design, get_analysis, get_analysis_tmp)
4. Data type conversion between Python and R works correctly
5. R algorithms integrate seamlessly with fzd
"""

import pytest
import sys
from pathlib import Path

# Try to import rpy2
try:
    import rpy2
    import rpy2.robjects
    HAS_RPY2 = True
except ImportError:
    HAS_RPY2 = False

# Skip all tests in this module if rpy2 is not available
pytestmark = pytest.mark.skipif(
    not HAS_RPY2,
    reason="rpy2 is required for R algorithm tests. Install with: pip install rpy2"
)


def test_r_algorithm_loading():
    """Test loading R algorithm with load_algorithm"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(
        str(r_algo_path),
        batch_sample_size=5,
        max_iterations=3,
        confidence=0.9,
        target_confidence_range=0.5,
        seed=42
    )

    # Verify wrapper was created
    from fz.algorithms import RAlgorithmWrapper
    assert isinstance(algo, RAlgorithmWrapper)
    assert algo.r_instance is not None
    assert algo.r_globals is not None


def test_r_algorithm_get_initial_design():
    """Test get_initial_design method with R algorithm"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Call get_initial_design
    input_vars = {
        "x": (0.0, 10.0),
        "y": (-5.0, 5.0)
    }
    output_vars = ["result"]

    initial_design = algo.get_initial_design(input_vars, output_vars)

    # Verify result
    assert isinstance(initial_design, list)
    assert len(initial_design) == 5
    assert all(isinstance(point, dict) for point in initial_design)
    assert all("x" in point and "y" in point for point in initial_design)
    assert all(0.0 <= point["x"] <= 10.0 for point in initial_design)
    assert all(-5.0 <= point["y"] <= 5.0 for point in initial_design)


def test_r_algorithm_get_next_design():
    """Test get_next_design method with R algorithm"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs
    Y = [point["x"]**2 + point["y"]**2 for point in X]

    # Call get_next_design
    next_design = algo.get_next_design(X, Y)

    # Verify result
    assert isinstance(next_design, list)
    assert len(next_design) == 5
    assert all(isinstance(point, dict) for point in next_design)


def test_r_algorithm_get_next_design_with_none():
    """Test get_next_design handles None values in outputs"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs with some None values (failed evaluations)
    Y = []
    for i, point in enumerate(X):
        if i % 2 == 0:
            Y.append(point["x"]**2 + point["y"]**2)
        else:
            Y.append(None)  # Failed evaluation

    # Call get_next_design - should handle None values
    next_design = algo.get_next_design(X, Y)

    # Verify result (should still generate next design)
    assert isinstance(next_design, list)


def test_r_algorithm_get_analysis():
    """Test get_analysis method with R algorithm"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs
    Y = [point["x"]**2 + point["y"]**2 for point in X]

    # Call get_analysis
    analysis = algo.get_analysis(X, Y)

    # Verify result
    assert isinstance(analysis, dict)
    assert "text" in analysis
    assert "data" in analysis
    assert isinstance(analysis["text"], str)
    assert isinstance(analysis["data"], dict)
    assert "mean" in analysis["data"]
    assert "std" in analysis["data"]


def test_r_algorithm_get_analysis_tmp():
    """Test get_analysis_tmp method with R algorithm"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs
    Y = [point["x"]**2 + point["y"]**2 for point in X]

    # Call get_analysis_tmp
    tmp_analysis = algo.get_analysis_tmp(X, Y)

    # Verify result (method is optional, may return None if not implemented)
    if tmp_analysis is not None:
        assert isinstance(tmp_analysis, dict)
        assert "text" in tmp_analysis or "data" in tmp_analysis


def test_r_algorithm_html_output():
    """Test that R algorithm can generate HTML output"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=10, seed=42)

    # Get some data
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)
    Y = [point["x"]**2 + point["y"]**2 for point in X]

    # Get more data
    X2 = algo.get_next_design(X, Y)
    for point in X2:
        X.append(point)
        Y.append(point["x"]**2 + point["y"]**2)

    # Call get_analysis
    analysis = algo.get_analysis(X, Y)

    # Verify HTML output exists (if base64enc is available in R)
    # HTML generation is optional and depends on base64enc package
    if "html" in analysis:
        assert isinstance(analysis["html"], str)
        assert len(analysis["html"]) > 0


def test_r_algorithm_empty_next_design():
    """Test that R algorithm returns empty list when finished"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm with very tight convergence criteria
    algo = load_algorithm(
        str(r_algo_path),
        batch_sample_size=100,
        max_iterations=1,  # Only 1 iteration allowed
        seed=42
    )

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs
    Y = [point["x"]**2 + point["y"]**2 for point in X]

    # Call get_next_design - should return empty list (max iterations reached)
    next_design = algo.get_next_design(X, Y)

    # Verify empty list is returned
    assert isinstance(next_design, list)
    assert len(next_design) == 0


def test_r_algorithm_convergence():
    """Test that R algorithm converges based on confidence interval"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm with very loose convergence criteria (easy to reach)
    algo = load_algorithm(
        str(r_algo_path),
        batch_sample_size=50,
        max_iterations=10,
        confidence=0.9,
        target_confidence_range=100.0,  # Very large target - should converge quickly
        seed=42
    )

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Simulate outputs (constant function - will have tight confidence interval)
    Y = [50.0 for _ in X]  # All same value

    # Call get_next_design - should return empty list (converged)
    next_design = algo.get_next_design(X, Y)

    # Verify empty list is returned (algorithm converged)
    assert isinstance(next_design, list)
    assert len(next_design) == 0


def test_r_algorithm_data_type_conversion():
    """Test that data types are correctly converted between Python and R"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=3, seed=42)

    # Get initial design
    input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Test with various output types
    Y = [
        10.5,      # float
        None,      # None -> NULL in R
        25.3       # float
    ]

    # Call get_next_design - should handle mixed types
    next_design = algo.get_next_design(X, Y)

    # Verify it works
    assert isinstance(next_design, list)

    # Call get_analysis
    analysis = algo.get_analysis(X, Y)

    # Verify analysis data types
    assert isinstance(analysis["data"]["mean"], float)
    assert isinstance(analysis["data"]["std"], float)
    assert isinstance(analysis["data"]["n_samples"], (int, float))


def test_r_algorithm_multiple_variables():
    """Test R algorithm with multiple input variables"""
    from fz.algorithms import load_algorithm

    # Get path to R algorithm
    repo_root = Path(__file__).parent.parent
    r_algo_path = repo_root / "examples" / "algorithms" / "montecarlo_uniform.R"

    # Load R algorithm
    algo = load_algorithm(str(r_algo_path), batch_sample_size=5, seed=42)

    # Get initial design with 3 variables
    input_vars = {
        "x": (0.0, 10.0),
        "y": (-5.0, 5.0),
        "z": (1.0, 3.0)
    }
    output_vars = ["result"]
    X = algo.get_initial_design(input_vars, output_vars)

    # Verify all variables are present
    assert all("x" in point and "y" in point and "z" in point for point in X)
    assert all(0.0 <= point["x"] <= 10.0 for point in X)
    assert all(-5.0 <= point["y"] <= 5.0 for point in X)
    assert all(1.0 <= point["z"] <= 3.0 for point in X)


def test_r_algorithm_error_handling():
    """Test that loading non-existent R file raises appropriate error"""
    from fz.algorithms import load_algorithm

    # Try to load non-existent R file
    with pytest.raises(ValueError, match="Algorithm file not found"):
        load_algorithm("nonexistent_algorithm.R")


def test_r_algorithm_invalid_extension():
    """Test that loading file with wrong extension raises error"""
    from fz.algorithms import load_algorithm
    import tempfile

    # Create a temp file with wrong extension
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
        f.write(b"dummy content")

    try:
        # Try to load file with wrong extension
        with pytest.raises(ValueError, match="must be a Python \\(\\.py\\) or R \\(\\.R\\) file"):
            load_algorithm(temp_path)
    finally:
        # Clean up
        import os
        os.unlink(temp_path)
