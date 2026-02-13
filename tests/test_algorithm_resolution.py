"""
Test algorithm resolution with various formats

Tests that algorithm argument can be resolved as:
- Plain string (exact name)
- Glob pattern (wildcards)
- Direct path to .py or .R file
"""
import os
import tempfile
from pathlib import Path
import shutil

import pytest


class TestAlgorithmResolution:
    """Test algorithm resolution patterns"""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace with .fz/algorithms/"""
        tmpdir = tempfile.mkdtemp()
        algorithms_dir = Path(tmpdir) / ".fz" / "algorithms"
        algorithms_dir.mkdir(parents=True)
        
        # Create sample algorithm files
        self._create_sample_algorithm(algorithms_dir / "montecarlo.py", "MonteCarlo")
        self._create_sample_algorithm(algorithms_dir / "montecarlo_uniform.py", "MonteCarloUniform")
        self._create_sample_algorithm(algorithms_dir / "brent.py", "Brent")
        self._create_sample_algorithm(algorithms_dir / "gradientdescent.py", "GradientDescent")
        self._create_sample_algorithm(algorithms_dir / "optimization_pso.py", "PSO")
        
        # Create an R algorithm
        r_algo = algorithms_dir / "montecarlo.R"
        r_algo.write_text("""
MonteCarlo <- function(...) {
  opts <- list(...)
  obj <- list(
    options = list(n_samples = as.integer(ifelse(is.null(opts$n_samples), 10, opts$n_samples)))
  )
  class(obj) <- "MonteCarlo"
  return(obj)
}

get_initial_design.MonteCarlo <- function(obj, input_variables, output_variables) {
  samples <- list()
  for (i in 1:obj$options$n_samples) {
    sample <- list()
    for (var in names(input_variables)) {
      bounds <- input_variables[[var]]
      sample[[var]] <- runif(1, bounds[1], bounds[2])
    }
    samples[[i]] <- sample
  }
  return(samples)
}

get_next_design.MonteCarlo <- function(obj, X, Y) {
  return(list())
}

get_analysis.MonteCarlo <- function(obj, X, Y) {
  valid_Y <- Y[!sapply(Y, is.null)]
  mean_val <- mean(unlist(valid_Y))
  return(list(text = paste0("Mean: ", round(mean_val, 2)), data = list(mean = mean_val)))
}
""")
        
        yield tmpdir, algorithms_dir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def _create_sample_algorithm(self, path: Path, class_name: str):
        """Create a sample Python algorithm file"""
        content = f'''
class {class_name}:
    """Sample {class_name} algorithm"""
    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 10)
        self.max_iter = options.get("max_iter", 100)

    def get_initial_design(self, input_vars, output_vars):
        import random
        random.seed(42)
        samples = []
        for _ in range(min(self.n_samples, 5)):
            sample = {{}}
            for var, (min_val, max_val) in input_vars.items():
                sample[var] = random.uniform(min_val, max_val)
            samples.append(sample)
        return samples

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        mean = sum(valid_Y) / len(valid_Y) if valid_Y else 0
        return {{"text": f"Mean: {{mean:.2f}}", "data": {{"mean": mean}}}}
'''
        path.write_text(content)

    def test_exact_name_resolution(self, temp_workspace):
        """Test resolving algorithm by exact name"""
        from fz.algorithms import resolve_algorithm_path
        
        tmpdir, algorithms_dir = temp_workspace
        
        # Change to temp workspace
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Test exact name
            path = resolve_algorithm_path("montecarlo")
            assert path is not None
            assert path.name == "montecarlo.py"
            # Use resolve() to handle symlinks on macOS (/var -> /private/var)
            assert path.parent.resolve() == algorithms_dir.resolve()
            
            # Test another exact name
            path = resolve_algorithm_path("brent")
            assert path is not None
            assert path.name == "brent.py"
        finally:
            os.chdir(original_cwd)

    def test_glob_pattern_resolution(self, temp_workspace):
        """Test resolving algorithm by glob pattern"""
        from fz.algorithms import resolve_algorithm_path
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Test prefix pattern
            path = resolve_algorithm_path("monte*")
            assert path is not None
            assert path.name in ["montecarlo.py", "montecarlo_uniform.py"]
            # Use resolve() to handle symlinks on macOS (/var -> /private/var)
            assert path.parent.resolve() == algorithms_dir.resolve()
            
            # Test wildcard in middle
            path = resolve_algorithm_path("*optimization*")
            assert path is not None
            assert "optimization" in path.name
            # Use resolve() to handle symlinks on macOS (/var -> /private/var)
            assert path.parent.resolve() == algorithms_dir.resolve()
            
            # Test prefix for specific algorithm
            path = resolve_algorithm_path("gradient*")
            assert path is not None
            assert path.name == "gradientdescent.py"
        finally:
            os.chdir(original_cwd)

    def test_direct_path_resolution(self, temp_workspace):
        """Test that direct paths are not resolved (return None)"""
        from fz.algorithms import resolve_algorithm_path
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Direct path should return None (caller handles it)
            path = resolve_algorithm_path(".fz/algorithms/montecarlo.py")
            assert path is None
            
            # Relative path with directory
            path = resolve_algorithm_path("algorithms/brent.py")
            assert path is None
            
            # File with extension
            path = resolve_algorithm_path("myalgo.py")
            assert path is None
        finally:
            os.chdir(original_cwd)

    def test_load_algorithm_with_exact_name(self, temp_workspace):
        """Test loading algorithm by exact name"""
        from fz.algorithms import load_algorithm
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Load by exact name
            algo = load_algorithm("montecarlo", n_samples=5)
            assert algo is not None
            assert hasattr(algo, 'get_initial_design')
            assert algo.n_samples == 5
        finally:
            os.chdir(original_cwd)

    def test_load_algorithm_with_glob_pattern(self, temp_workspace):
        """Test loading algorithm by glob pattern"""
        from fz.algorithms import load_algorithm
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Load by glob pattern
            algo = load_algorithm("monte*", n_samples=3)
            assert algo is not None
            assert hasattr(algo, 'get_initial_design')
            assert algo.n_samples == 3
            
            # Load by pattern matching specific algorithm
            algo = load_algorithm("gradient*", n_samples=7)
            assert algo is not None
            assert algo.n_samples == 7
        finally:
            os.chdir(original_cwd)

    def test_load_algorithm_with_direct_path(self, temp_workspace):
        """Test loading algorithm by direct path"""
        from fz.algorithms import load_algorithm
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Load by direct path
            algo_path = str(algorithms_dir / "brent.py")
            algo = load_algorithm(algo_path, n_samples=8)
            assert algo is not None
            assert hasattr(algo, 'get_initial_design')
            assert algo.n_samples == 8
        finally:
            os.chdir(original_cwd)

    def test_r_algorithm_resolution(self, temp_workspace):
        """Test resolving R algorithm files"""
        from fz.algorithms import resolve_algorithm_path
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Test R file resolution
            path = resolve_algorithm_path("montecarlo")
            assert path is not None
            # Should prefer .py over .R
            assert path.suffix == ".py"
            
        finally:
            os.chdir(original_cwd)

    def test_nonexistent_algorithm(self, temp_workspace):
        """Test error when algorithm doesn't exist"""
        from fz.algorithms import load_algorithm
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="not found"):
                load_algorithm("nonexistent")
        finally:
            os.chdir(original_cwd)

    def test_glob_no_match(self, temp_workspace):
        """Test glob pattern with no matches"""
        from fz.algorithms import load_algorithm
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="not found"):
                load_algorithm("xyz*")
        finally:
            os.chdir(original_cwd)

    def test_case_sensitivity_windows(self, temp_workspace):
        """Test that resolution works on Windows (case-insensitive filesystem)"""
        from fz.algorithms import resolve_algorithm_path
        import platform
        
        tmpdir, algorithms_dir = temp_workspace
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # On Windows, both should work
            path1 = resolve_algorithm_path("montecarlo")
            path2 = resolve_algorithm_path("MonteCarlo")
            
            if platform.system() == "Windows":
                # Both should resolve (case-insensitive)
                assert path1 is not None or path2 is not None
            else:
                # Only exact case should work
                assert path1 is not None
        finally:
            os.chdir(original_cwd)

    def test_priority_order(self, temp_workspace):
        """Test that project-level algorithms have priority over global"""
        from fz.algorithms import resolve_algorithm_path
        
        tmpdir, algorithms_dir = temp_workspace
        
        # Create a global algorithms directory with conflicting name
        home_dir = os.environ.get('HOME') or os.environ.get('USERPROFILE') or os.path.expanduser('~')
        global_algo_dir = Path(home_dir) / ".fz" / "algorithms"
        
        # Skip if we can't create global dir (permissions)
        try:
            global_algo_dir.mkdir(parents=True, exist_ok=True)
            global_algo = global_algo_dir / "testpriority.py"
            global_algo.write_text("# global")
            
            # Create project-level with same name
            local_algo = algorithms_dir / "testpriority.py"
            local_algo.write_text("# local")
            
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Should resolve to project-level (priority)
                path = resolve_algorithm_path("testpriority")
                assert path is not None
                assert path == local_algo
                assert "local" in path.read_text()
            finally:
                os.chdir(original_cwd)
                # Cleanup
                if global_algo.exists():
                    global_algo.unlink()
        except (PermissionError, OSError):
            pytest.skip("Cannot create global .fz directory for test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
