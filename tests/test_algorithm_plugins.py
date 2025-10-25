#!/usr/bin/env python3
"""
Test algorithm plugin system

This test suite verifies that:
1. Algorithms can be loaded by name from .fz/algorithms/ directory
2. Project-level plugins take priority over global plugins
3. Both .py and .R algorithms work as plugins
4. Direct paths still work as before
5. Helpful error messages when plugins not found
"""

import pytest
from pathlib import Path
import shutil

from fz.algorithms import load_algorithm, resolve_algorithm_path


class TestAlgorithmPluginResolution:
    """Test algorithm plugin path resolution"""

    def test_resolve_direct_path(self):
        """Test that direct paths are not resolved as plugins"""
        # Paths with / should not be resolved
        assert resolve_algorithm_path("path/to/algo.py") is None
        assert resolve_algorithm_path("../algo.py") is None

        # Paths with extension should not be resolved
        assert resolve_algorithm_path("algo.py") is None
        assert resolve_algorithm_path("algo.R") is None

    def test_resolve_plugin_name(self, temp_test_dir):
        """Test resolving plugin name to path"""
        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create a test algorithm
        algo_file = algo_dir / "testalgo.py"
        algo_file.write_text("""
class TestAlgo:
    def __init__(self, **options):
        pass

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "test"}
""")

        # Resolve plugin name
        resolved = resolve_algorithm_path("testalgo")

        # Verify it found the plugin
        assert resolved is not None
        assert resolved.exists()
        assert resolved.name == "testalgo.py"

    def test_resolve_plugin_with_r_extension(self, temp_test_dir):
        """Test resolving R algorithm plugin"""
        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create a test R algorithm
        algo_file = algo_dir / "testalgo.R"
        algo_file.write_text("""
TestAlgo <- function(...) {
  obj <- list()
  class(obj) <- "TestAlgo"
  return(obj)
}
""")

        # Resolve plugin name
        resolved = resolve_algorithm_path("testalgo")

        # Verify it found the R plugin
        assert resolved is not None
        assert resolved.exists()
        assert resolved.name == "testalgo.R"

    def test_resolve_plugin_python_priority_over_r(self, temp_test_dir):
        """Test that .py plugin has priority over .R when both exist"""
        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create both .py and .R algorithms with same name
        py_file = algo_dir / "testalgo.py"
        py_file.write_text("class TestAlgo: pass")

        r_file = algo_dir / "testalgo.R"
        r_file.write_text("TestAlgo <- function() {}")

        # Resolve plugin name - should get .py first
        resolved = resolve_algorithm_path("testalgo")

        # Verify it found the Python plugin (priority)
        assert resolved is not None
        assert resolved.name == "testalgo.py"

    def test_resolve_plugin_not_found(self, temp_test_dir):
        """Test resolving non-existent plugin returns None"""
        # Try to resolve non-existent plugin
        resolved = resolve_algorithm_path("nonexistent")

        # Should return None
        assert resolved is None


class TestAlgorithmPluginLoading:
    """Test loading algorithms via plugin system"""

    def test_load_plugin_by_name(self, temp_test_dir):
        """Test loading algorithm by plugin name"""
        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create a test algorithm
        algo_file = algo_dir / "myalgorithm.py"
        algo_file.write_text("""
class MyAlgorithm:
    def __init__(self, **options):
        self.batch_size = options.get("batch_size", 5)

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": float(i)} for i in range(self.batch_size)]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Analysis complete", "data": {"count": len(X)}}
""")

        # Load by plugin name
        algo = load_algorithm("myalgorithm", batch_size=3)

        # Test the algorithm works
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert len(design) == 3
        assert design[0]["x"] == 0.0

    def test_load_plugin_from_global_directory(self, temp_test_dir, monkeypatch):
        """Test loading algorithm from global ~/.fz/algorithms/"""
        # Mock home directory
        fake_home = Path(temp_test_dir) / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Create global .fz/algorithms/ directory
        algo_dir = fake_home / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create a test algorithm in global directory
        algo_file = algo_dir / "globalalgo.py"
        algo_file.write_text("""
class GlobalAlgo:
    def __init__(self, **options):
        pass

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 1.0}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "global"}
""")

        # Load by plugin name
        algo = load_algorithm("globalalgo")

        # Test the algorithm works
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert len(design) == 1
        assert design[0]["x"] == 1.0

    def test_load_plugin_project_priority_over_global(self, temp_test_dir, monkeypatch):
        """Test that project-level plugin takes priority over global"""
        # Mock home directory
        fake_home = Path(temp_test_dir) / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Create global plugin
        global_algo_dir = fake_home / ".fz" / "algorithms"
        global_algo_dir.mkdir(parents=True)
        global_file = global_algo_dir / "samename.py"
        global_file.write_text("""
class SameName:
    def __init__(self, **options):
        self.source = "global"

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 999.0}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": self.source}
""")

        # Create project-level plugin (should have priority)
        project_algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        project_algo_dir.mkdir(parents=True)
        project_file = project_algo_dir / "samename.py"
        project_file.write_text("""
class SameName:
    def __init__(self, **options):
        self.source = "project"

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 1.0}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": self.source}
""")

        # Load by plugin name - should get project-level
        algo = load_algorithm("samename")

        # Verify it loaded the project-level one
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert design[0]["x"] == 1.0  # Not 999.0 from global

        analysis = algo.get_analysis([], [])
        assert analysis["text"] == "project"

    def test_load_direct_path_still_works(self, temp_test_dir):
        """Test that direct paths still work (backward compatibility)"""
        # Create algorithm file in arbitrary location
        algo_file = Path(temp_test_dir) / "direct_algo.py"
        algo_file.write_text("""
class DirectAlgo:
    def __init__(self, **options):
        pass

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 42.0}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "direct"}
""")

        # Load by direct path
        algo = load_algorithm(str(algo_file))

        # Verify it works
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert design[0]["x"] == 42.0

    def test_load_plugin_not_found_error(self, temp_test_dir):
        """Test helpful error message when plugin not found"""
        # Try to load non-existent plugin
        with pytest.raises(ValueError) as exc_info:
            load_algorithm("nonexistent")

        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "Plugin 'nonexistent' not found" in error_msg
        assert ".fz/algorithms/nonexistent.py" in error_msg
        assert "~/.fz/algorithms/nonexistent.py" in error_msg

    def test_load_plugin_with_options(self, temp_test_dir):
        """Test passing options to plugin algorithm"""
        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create algorithm that uses options
        algo_file = algo_dir / "optionalgo.py"
        algo_file.write_text("""
class OptAlgo:
    def __init__(self, **options):
        self.value = options.get("value", 10)
        self.name = options.get("name", "default")

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": float(self.value)}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": self.name, "data": {"value": self.value}}
""")

        # Load with options
        algo = load_algorithm("optionalgo", value=42, name="test")

        # Verify options were passed
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert design[0]["x"] == 42.0

        analysis = algo.get_analysis([], [])
        assert analysis["text"] == "test"
        assert analysis["data"]["value"] == 42


class TestAlgorithmPluginWithRAlgorithms:
    """Test plugin system with R algorithms"""

    @pytest.mark.skipif(
        True,  # Skip for now unless rpy2 is available
        reason="R plugin tests require rpy2"
    )
    def test_load_r_plugin_by_name(self, temp_test_dir):
        """Test loading R algorithm by plugin name"""
        try:
            import rpy2
        except ImportError:
            pytest.skip("rpy2 not available")

        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create R algorithm
        algo_file = algo_dir / "ralgo.R"
        algo_file.write_text("""
RAlgo <- function(...) {
  obj <- list(
    options = list(),
    state = new.env(parent = emptyenv())
  )
  class(obj) <- "RAlgo"
  return(obj)
}

get_initial_design.RAlgo <- function(obj, input_variables, output_variables) {
  return(list(list(x = 1.0)))
}

get_next_design.RAlgo <- function(obj, X, Y) {
  return(list())
}

get_analysis.RAlgo <- function(obj, X, Y) {
  return(list(text = "R plugin"))
}
""")

        # Load by plugin name
        algo = load_algorithm("ralgo")

        # Test it works
        design = algo.get_initial_design({"x": (0, 10)}, ["result"])
        assert len(design) == 1


class TestAlgorithmPluginIntegration:
    """Test plugin system integration with fzd"""

    def test_fzd_with_plugin_algorithm(self, temp_test_dir):
        """Test using plugin algorithm with fzd"""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas required for fzd")

        import fz

        # Create .fz/algorithms/ directory
        algo_dir = Path(temp_test_dir) / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)

        # Create simple sampling algorithm
        algo_file = algo_dir / "simplesampler.py"
        algo_file.write_text("""
class SimpleSampler:
    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 5)
        self.iteration = 0

    def get_initial_design(self, input_vars, output_vars):
        import random
        random.seed(42)
        samples = []
        for _ in range(self.n_samples):
            sample = {}
            for var, (min_val, max_val) in input_vars.items():
                sample[var] = random.uniform(min_val, max_val)
            samples.append(sample)
        return samples

    def get_next_design(self, X, Y):
        self.iteration += 1
        if self.iteration >= 1:
            return []
        return self.get_initial_design({"x": (0, 10)}, [])

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        mean_val = sum(valid_Y) / len(valid_Y) if valid_Y else 0
        return {
            "text": f"Mean: {mean_val:.2f}",
            "data": {"mean": mean_val, "n_samples": len(valid_Y)}
        }
""")

        # Create input template
        input_file = Path(temp_test_dir) / "input.txt"
        input_file.write_text("x=$x")

        # Create calculation script
        calc_script = Path(temp_test_dir) / "calc.sh"
        calc_script.write_text("""#!/bin/bash
source $1
echo "result=$x" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "output": {"result": "grep result output.txt | cut -d= -f2"}
        }

        # Run fzd with plugin algorithm
        results = fz.fzd(
            input_file=str(input_file),
            input_variables={"x": "[0;10]"},
            model=model,
            output_expression="result",
            algorithm="simplesampler",  # Plugin name!
            calculators=[f"sh://bash {calc_script}"],
            algorithm_options={"n_samples": 3},
            analysis_dir=str(Path(temp_test_dir) / "fzd_results")
        )

        # Verify results
        assert "XY" in results
        assert isinstance(results["XY"], pd.DataFrame)
        assert len(results["XY"]) >= 3
        assert "x" in results["XY"].columns
        assert "result" in results["XY"].columns
