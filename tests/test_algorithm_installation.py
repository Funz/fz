"""
Test algorithm installation functionality

Tests installation, uninstallation, and listing of algorithms
from GitHub repositories, URLs, and local zip files.
"""
import json
import os
import platform
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest


# Determine if we're running on Windows
IS_WINDOWS = platform.system() == "Windows"


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def test_algorithm_zip_py(temp_workspace):
    """Create a test Python algorithm zip file"""
    # Create algorithm structure
    algo_dir = temp_workspace / "fz-testalgo-main"
    algo_dir.mkdir(exist_ok=True)

    # Create algorithm implementation
    algo_code = '''
class TestAlgo:
    """Simple test algorithm"""
    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 10)

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
        return []  # One-shot sampling

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        mean = sum(valid_Y) / len(valid_Y) if valid_Y else 0
        return {"text": f"Mean: {mean:.2f}", "data": {"mean": mean}}
'''

    algo_file = algo_dir / "testalgo.py"
    algo_file.write_text(algo_code)

    # Create zip file
    zip_path = temp_workspace / "fz-testalgo.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(algo_file, arcname="fz-testalgo-main/testalgo.py")

    return zip_path


@pytest.fixture
def test_algorithm_zip_r(temp_workspace):
    """Create a test R algorithm zip file"""
    # Create algorithm structure
    algo_dir = temp_workspace / "fz-testalgor-main"
    algo_dir.mkdir(exist_ok=True)

    # Create R algorithm implementation
    algo_code = '''
TestAlgoR <- function(...) {
  opts <- list(...)
  state <- new.env(parent = emptyenv())
  state$n_samples <- 0

  obj <- list(
    options = list(
      n_samples = as.integer(ifelse(is.null(opts$n_samples), 10, opts$n_samples))
    ),
    state = state
  )

  class(obj) <- "TestAlgoR"
  return(obj)
}

get_initial_design.TestAlgoR <- function(obj, input_variables, output_variables) {
  set.seed(42)
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

get_next_design.TestAlgoR <- function(obj, X, Y) {
  return(list())
}

get_analysis.TestAlgoR <- function(obj, X, Y) {
  valid_Y <- Y[!sapply(Y, is.null)]
  mean_val <- mean(unlist(valid_Y))
  return(list(text = paste0("Mean: ", round(mean_val, 2)), data = list(mean = mean_val)))
}
'''

    algo_file = algo_dir / "testalgor.R"
    algo_file.write_text(algo_code)

    # Create zip file
    zip_path = temp_workspace / "fz-testalgor.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(algo_file, arcname="fz-testalgor-main/testalgor.R")

    return zip_path


@pytest.fixture
def test_algorithm_zip_fz_structure(temp_workspace):
    """Create algorithm zip with .fz/algorithms/ structure"""
    # Create algorithm structure matching fz repository structure
    algo_dir = temp_workspace / "fz-advanced-main"
    fz_dir = algo_dir / ".fz" / "algorithms"
    fz_dir.mkdir(parents=True, exist_ok=True)

    # Create algorithm implementation
    algo_code = '''
class AdvancedAlgo:
    """Advanced test algorithm"""
    def __init__(self, **options):
        self.batch_size = options.get("batch_size", 5)

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}] * self.batch_size

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Analysis complete", "data": {"count": len(X)}}
'''

    algo_file = fz_dir / "advanced.py"
    algo_file.write_text(algo_code)

    # Create zip file
    zip_path = temp_workspace / "fz-advanced.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(algo_file, arcname="fz-advanced-main/.fz/algorithms/advanced.py")

    return zip_path


@pytest.fixture
def install_workspace(temp_workspace):
    """Create a workspace with .fz directories for installation"""
    fz_dir = temp_workspace / ".fz"
    algo_dir = fz_dir / "algorithms"
    algo_dir.mkdir(parents=True, exist_ok=True)

    return temp_workspace


class TestAlgorithmInstallation:
    """Test algorithm installation functions"""

    def test_install_algorithm_from_local_zip_py(self, test_algorithm_zip_py, install_workspace):
        """Test installing Python algorithm from local zip file"""
        from fz.installer import install_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = install_algorithm(str(test_algorithm_zip_py), global_install=False)

            assert result['algorithm_name'] == 'testalgo'
            assert 'install_path' in result

            # Verify algorithm file was created
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert algo_file.exists()

            # Verify can load the algorithm
            from fz.algorithms import load_algorithm
            algo = load_algorithm("testalgo", n_samples=5)
            assert algo is not None
        finally:
            os.chdir(original_cwd)

    def test_install_algorithm_from_local_zip_r(self, test_algorithm_zip_r, install_workspace):
        """Test installing R algorithm from local zip file"""
        from fz.installer import install_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = install_algorithm(str(test_algorithm_zip_r), global_install=False)

            assert result['algorithm_name'] == 'testalgor'
            assert 'install_path' in result

            # Verify algorithm file was created
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgor.R"
            assert algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_install_algorithm_fz_structure(self, test_algorithm_zip_fz_structure, install_workspace):
        """Test installing algorithm from .fz/algorithms/ structure"""
        from fz.installer import install_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = install_algorithm(str(test_algorithm_zip_fz_structure), global_install=False)

            assert result['algorithm_name'] == 'advanced'

            # Verify algorithm file was created
            algo_file = install_workspace / ".fz" / "algorithms" / "advanced.py"
            assert algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_install_global_algorithm(self, test_algorithm_zip_py):
        """Test installing algorithm globally to ~/.fz/algorithms/"""
        from fz.installer import install_algorithm, uninstall_algorithm

        try:
            result = install_algorithm(str(test_algorithm_zip_py), global_install=True)

            assert result['algorithm_name'] == 'testalgo'

            # Verify in global location
            global_algo = Path.home() / ".fz" / "algorithms" / "testalgo.py"
            assert global_algo.exists()

        finally:
            # Cleanup: remove global installation
            uninstall_algorithm('testalgo', global_uninstall=True)

    def test_install_overwrites_existing(self, test_algorithm_zip_py, install_workspace):
        """Test that installing same algorithm twice overwrites"""
        from fz.installer import install_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install first time
            result1 = install_algorithm(str(test_algorithm_zip_py), global_install=False)
            assert result1['algorithm_name'] == 'testalgo'

            # Install again (should overwrite)
            result2 = install_algorithm(str(test_algorithm_zip_py), global_install=False)
            assert result2['algorithm_name'] == 'testalgo'

            # Should still exist
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_install_invalid_zip(self, temp_workspace, install_workspace):
        """Test error handling for invalid zip file"""
        from fz.installer import install_algorithm

        # Create an empty zip file
        invalid_zip = temp_workspace / "invalid.zip"
        with zipfile.ZipFile(invalid_zip, 'w') as zf:
            pass  # Empty zip

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            with pytest.raises(Exception, match="No algorithm files"):
                install_algorithm(str(invalid_zip), global_install=False)
        finally:
            os.chdir(original_cwd)


class TestAlgorithmUninstallation:
    """Test algorithm uninstallation functions"""

    def test_uninstall_algorithm(self, test_algorithm_zip_py, install_workspace):
        """Test uninstalling an algorithm"""
        from fz.installer import install_algorithm, uninstall_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install algorithm first
            install_algorithm(str(test_algorithm_zip_py), global_install=False)

            # Verify it's installed
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert algo_file.exists()

            # Uninstall
            success = uninstall_algorithm('testalgo', global_uninstall=False)
            assert success is True

            # Verify it's removed
            assert not algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_uninstall_nonexistent_algorithm(self, install_workspace):
        """Test uninstalling non-existent algorithm returns False"""
        from fz.installer import uninstall_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            success = uninstall_algorithm('nonexistent', global_uninstall=False)
            assert success is False
        finally:
            os.chdir(original_cwd)

    def test_uninstall_removes_both_py_and_r(self, test_algorithm_zip_py, test_algorithm_zip_r, install_workspace):
        """Test that uninstall removes both .py and .R files if present"""
        from fz.installer import install_algorithm, uninstall_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install Python algorithm
            install_algorithm(str(test_algorithm_zip_py), global_install=False)

            # Manually create an R version with same name
            r_algo = install_workspace / ".fz" / "algorithms" / "testalgo.R"
            r_algo.write_text("# R version")

            # Both should exist
            py_algo = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert py_algo.exists()
            assert r_algo.exists()

            # Uninstall by name (should remove both)
            success = uninstall_algorithm('testalgo', global_uninstall=False)
            assert success is True

            # Both should be removed
            assert not py_algo.exists()
            assert not r_algo.exists()
        finally:
            os.chdir(original_cwd)


class TestAlgorithmListing:
    """Test algorithm listing functions"""

    def test_list_installed_algorithms_empty(self, install_workspace):
        """Test listing when no algorithms are installed"""
        from fz.installer import list_installed_algorithms

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            algorithms = list_installed_algorithms(global_list=False)
            # Should return empty dict or only global algorithms
            assert isinstance(algorithms, dict)
        finally:
            os.chdir(original_cwd)

    def test_list_installed_algorithms(self, test_algorithm_zip_py, test_algorithm_zip_r, install_workspace):
        """Test listing installed algorithms"""
        from fz.installer import install_algorithm, list_installed_algorithms

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install both Python and R algorithms
            install_algorithm(str(test_algorithm_zip_py), global_install=False)
            install_algorithm(str(test_algorithm_zip_r), global_install=False)

            # List algorithms
            algorithms = list_installed_algorithms(global_list=False)

            assert 'testalgo' in algorithms
            assert 'testalgor' in algorithms

            # Check algorithm info
            testalgo_info = algorithms['testalgo']
            assert testalgo_info['type'] == 'Python'
            assert testalgo_info['global'] is False

            testalgor_info = algorithms['testalgor']
            assert testalgor_info['type'] == 'R'
            assert testalgor_info['global'] is False
        finally:
            os.chdir(original_cwd)

    def test_list_shows_global_flag(self, test_algorithm_zip_py, install_workspace):
        """Test that list shows correct global flag"""
        from fz.installer import install_algorithm, list_installed_algorithms, uninstall_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install locally
            install_algorithm(str(test_algorithm_zip_py), global_install=False)

            # Install globally with different name (to avoid conflict)
            # We'll use the same zip but it will show up with same name
            # Just install globally and check the flag
            install_algorithm(str(test_algorithm_zip_py), global_install=True)

            # List all
            algorithms = list_installed_algorithms(global_list=False)

            # Local should have priority, so testalgo should be marked as local
            if 'testalgo' in algorithms:
                # The local one takes priority in listing
                assert algorithms['testalgo']['global'] is False

        finally:
            os.chdir(original_cwd)
            # Cleanup global installation
            uninstall_algorithm('testalgo', global_uninstall=True)

    def test_list_global_only(self, test_algorithm_zip_py, install_workspace):
        """Test listing only global algorithms"""
        from fz.installer import install_algorithm, list_installed_algorithms, uninstall_algorithm

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install locally
            install_algorithm(str(test_algorithm_zip_py), global_install=False)

            # List only global (should not show local algorithm)
            algorithms = list_installed_algorithms(global_list=True)

            # testalgo should not appear in global list
            assert 'testalgo' not in algorithms

        finally:
            os.chdir(original_cwd)


class TestAlgorithmCLIIntegration:
    """Test CLI integration for algorithm installation"""

    def test_cli_install_algorithm_help(self):
        """Test fz install algorithm --help"""
        from fz.cli import main
        import sys
        from io import StringIO

        # Save original
        original_argv = sys.argv
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # Redirect output
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        sys.argv = ['fz', 'install', 'algorithm', '--help']

        returncode = 0
        try:
            returncode = main()
        except SystemExit as e:
            returncode = e.code if e.code is not None else 0
        finally:
            output = sys.stdout.getvalue() + sys.stderr.getvalue()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            sys.argv = original_argv

        assert returncode == 0
        assert 'algorithm' in output.lower()

    def test_cli_list_algorithms_help(self):
        """Test fz list algorithms --help"""
        from fz.cli import main
        import sys
        from io import StringIO

        # Save original
        original_argv = sys.argv
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # Redirect output
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        sys.argv = ['fz', 'list', 'algorithms', '--help']

        returncode = 0
        try:
            returncode = main()
        except SystemExit as e:
            returncode = e.code if e.code is not None else 0
        finally:
            output = sys.stdout.getvalue() + sys.stderr.getvalue()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            sys.argv = original_argv

        assert returncode == 0
        assert 'algorithm' in output.lower()


class TestAlgorithmPythonAPI:
    """Test Python API for algorithm installation"""

    def test_install_algo_function(self, test_algorithm_zip_py, install_workspace):
        """Test fz.install_algo() function"""
        import fz

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            result = fz.install_algo(str(test_algorithm_zip_py), global_install=False)

            assert result['algorithm_name'] == 'testalgo'

            # Verify file exists
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_uninstall_algo_function(self, test_algorithm_zip_py, install_workspace):
        """Test fz.uninstall_algo() function"""
        import fz

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install first
            fz.install_algo(str(test_algorithm_zip_py), global_install=False)

            # Uninstall
            success = fz.uninstall_algo('testalgo', global_uninstall=False)

            assert success is True

            # Verify removed
            algo_file = install_workspace / ".fz" / "algorithms" / "testalgo.py"
            assert not algo_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_list_algorithms_function(self, test_algorithm_zip_py, install_workspace):
        """Test fz.list_algorithms() function"""
        import fz

        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)

            # Install an algorithm
            fz.install_algo(str(test_algorithm_zip_py), global_install=False)

            # List algorithms
            algorithms = fz.list_algorithms(global_list=False)

            assert 'testalgo' in algorithms
            assert algorithms['testalgo']['type'] == 'Python'
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
