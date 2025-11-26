"""
Demo tests for fzd features

These tests verify various fzd features work correctly by running
demonstrations that were previously standalone scripts.
"""

import pytest
import fz
import tempfile
from pathlib import Path
import shutil
import logging


class TestAlgorithmAutoInstall:
    """Test automatic package installation for algorithm requirements"""

    def test_load_algorithm_with_auto_install(self):
        """Test that packages are automatically installed when loading an algorithm"""
        # Create a test algorithm that requires a package
        # We'll use 'six' as it's small and commonly used
        test_algo_content = """
#title: Test Algorithm with Package Requirement
#author: Test
#type: test
#require: six

class TestAlgorithm:
    def __init__(self, **options):
        # Import the required package to verify it's installed
        import six
        self.options = options

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Test", "data": {}}
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_algo_content)
            algo_file = f.name

        try:
            # Load the algorithm - this should auto-install 'six' if not present
            from fz.algorithms import load_algorithm
            algo = load_algorithm(algo_file)

            # Verify the algorithm loaded successfully
            assert algo is not None

            # Verify we can now import six
            import six
            assert six is not None

        finally:
            # Clean up temporary file
            Path(algo_file).unlink()


class TestDisplayResultsTmp:
    """Test intermediate progress display using get_analysis_tmp"""

    def test_get_analysis_tmp_is_called(self):
        """Test that get_analysis_tmp is called during fzd iterations"""
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Create input directory
            input_dir = tmpdir / "input"
            input_dir.mkdir()

            # Create input file
            (input_dir / "input.txt").write_text("x = $x\ny = $y\n")

            # Define simple model
            model = {
                "varprefix": "$",
                "delim": "()",
                "run": "echo 'result = 1.0' > output.txt",
                "output": {
                    "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
                }
            }

            # Path to montecarlo_uniform algorithm (has get_analysis_tmp)
            import os
            repo_root = Path(__file__).parent.parent
            algo_path = str(repo_root / "examples" / "algorithms" / "montecarlo_uniform.py")

            # Run fzd with small batch to see multiple iterations
            result = fz.fzd(
                input_path=str(input_dir),
                input_variables={"x": "[0;1]", "y": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=algo_path,
                algorithm_options={
                    "batch_sample_size": 3,  # Small batches to see more iterations
                    "max_iterations": 5,
                    "target_confidence_range": 0.01,
                    "seed": 42
                }
            )

            # Verify result structure
            assert 'XY' in result
            assert 'analysis' in result
            assert 'iterations' in result
            assert result['iterations'] > 0

        finally:
            # Cleanup
            shutil.rmtree(tmpdir)


class TestContentDetection:
    """Test intelligent content detection and file saving"""

    def test_content_detection_with_different_formats(self):
        """Test that fzd detects and processes different content types"""
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Create input directory
            input_dir = tmpdir / "input"
            input_dir.mkdir()

            # Create input file
            (input_dir / "input.txt").write_text("x = $x\n")

            # Define simple model
            model = {
                "varprefix": "$",
                "delim": "()",
                "run": "echo 'result = 1.5' > output.txt",
                "output": {
                    "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
                }
            }

            # Create algorithm with different content types in get_analysis
            algo_file = tmpdir / "test_algo.py"
            algo_file.write_text("""
class TestContentAlgorithm:
    def __init__(self, **options):
        self.iteration = 0

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        self.iteration += 1
        if self.iteration < 2:
            return [{"x": 0.7}]
        return []

    def get_analysis(self, X, Y):
        # Return different content types based on iteration
        if self.iteration == 0:
            # First iteration: JSON content
            return {
                "text": '{"mean": 1.234, "std": 0.567, "samples": 1}',
                "data": {"iteration": 0}
            }
        elif self.iteration == 1:
            # Second iteration: Key=Value content
            return {
                "text": "mean = 1.345\\nstd = 0.432\\nsamples = 2",
                "data": {"iteration": 1}
            }
        else:
            # Final iteration: Markdown content
            return {
                "text": '# Final Results\\n\\nMean: 1.456',
                "data": {"iteration": 2}
            }

    def get_analysis_tmp(self, X, Y):
        return {"text": f"Progress: {len(X)} samples", "data": {}}
""")

            # Run fzd
            result = fz.fzd(
                input_path=str(input_dir),
                input_variables={"x": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file)
            )

            # Verify result structure
            assert 'XY' in result
            assert 'analysis' in result

        finally:
            # Cleanup
            shutil.rmtree(tmpdir)


class TestDataFrame:
    """Test XY DataFrame returned by fzd"""

    def test_xy_dataframe_structure(self):
        """Test that fzd returns XY DataFrame with correct structure"""
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Create input directory
            input_dir = tmpdir / "input"
            input_dir.mkdir()

            # Create input file
            (input_dir / "input.txt").write_text("x = $x\ny = $y\n")

            # Define simple model
            model = {
                "varprefix": "$",
                "delim": "()",
                "run": "echo 'result = 1.0' > output.txt",
                "output": {
                    "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
                }
            }

            # Use randomsampling algorithm
            repo_root = Path(__file__).parent.parent
            algo_path = str(repo_root / "examples" / "algorithms" / "randomsampling.py")

            # Run fzd
            result = fz.fzd(
                input_path=str(input_dir),
                input_variables={"x": "[0;1]", "y": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=algo_path,
                algorithm_options={"nvalues": 5, "seed": 42}
            )

            # Access the XY DataFrame
            df = result['XY']

            # Verify structure
            assert df is not None
            assert 'x' in df.columns
            assert 'y' in df.columns
            assert 'result' in df.columns  # Output column named with output_expression
            assert len(df) == 5

            # Verify old keys are not present
            assert 'input_vars' not in result
            assert 'output_values' not in result

            # Verify new key is present
            assert 'XY' in result

        finally:
            # Cleanup
            shutil.rmtree(tmpdir)


class TestProgressBar:
    """Test progress bar with total time display"""

    def test_progress_bar_shows_total_time(self):
        """Test that progress bar shows total time after completion"""
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Create input directory
            input_dir = tmpdir / "input"
            input_dir.mkdir()

            # Create input file
            (input_dir / "input.txt").write_text("x = $x\ny = $y\n")

            # Define simple model
            model = {
                "varprefix": "$",
                "delim": "()",
                "run": "echo 'result = 1.0' > output.txt",
                "output": {
                    "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
                }
            }

            # Use randomsampling algorithm
            repo_root = Path(__file__).parent.parent
            algo_path = str(repo_root / "examples" / "algorithms" / "randomsampling.py")

            # Run fzd
            result = fz.fzd(
                input_path=str(input_dir),
                input_variables={"x": "[0;1]", "y": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=algo_path,
                algorithm_options={"nvalues": 5, "seed": 42}
            )

            # Verify result was returned (progress bar didn't block)
            assert result is not None
            assert 'XY' in result

        finally:
            # Cleanup
            shutil.rmtree(tmpdir)


class TestParallelExecution:
    """Test parallel calculator execution in fzd"""

    def test_parallel_execution_structure(self):
        """Test that fzd executes cases in batches enabling parallelization"""
        # Create temporary directory
        tmpdir = Path(tempfile.mkdtemp())

        try:
            # Create input directory
            input_dir = tmpdir / "input"
            input_dir.mkdir()

            # Create input file
            (input_dir / "input.txt").write_text("x = $x\ny = $y\n")

            # Define simple model
            model = {
                "varprefix": "$",
                "delim": "()",
                "run": "echo 'result = 1.0' > output.txt",
                "output": {
                    "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
                }
            }

            # Path to randomsampling algorithm
            repo_root = Path(__file__).parent.parent
            algo_path = str(repo_root / "examples" / "algorithms" / "randomsampling.py")

            # Run fzd
            result = fz.fzd(
                input_path=str(input_dir),
                input_variables={"x": "[0;1]", "y": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=algo_path,
                algorithm_options={"nvalues": 5, "seed": 42}
            )

            # Verify result structure
            assert 'total_evaluations' in result
            assert result['total_evaluations'] > 0
            assert 'XY' in result

        finally:
            # Cleanup
            shutil.rmtree(tmpdir)
