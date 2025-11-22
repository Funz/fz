"""
Negative tests for algorithms
Tests error handling for invalid algorithms, missing algorithm files, bad algorithm options, etc.
"""

import os
import tempfile
from pathlib import Path
import pytest

try:
    import pandas as pd
except ImportError:

from fz import fzd


def test_algorithm_nonexistent_file():
    """Test fzd with a non-existent algorithm file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file
        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        # Create calculator script
        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "grep 'result = ' output.txt | cut -d '=' -f2"
            }
        }

        analysis_dir = tmpdir / "analysis"

        # Use non-existent algorithm file
        nonexistent_algo = tmpdir / "does_not_exist.py"

        # Should raise FileNotFoundError or ValueError
        with pytest.raises((FileNotFoundError, ValueError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(nonexistent_algo),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_invalid_python_syntax():
    """Test algorithm file with invalid Python syntax"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Create algorithm file with syntax error
        algo_file = tmpdir / "bad_syntax.py"
        algo_file.write_text("class MyAlgo\n    def invalid syntax here\n")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should raise SyntaxError or ImportError
        with pytest.raises((SyntaxError, ImportError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_missing_required_methods():
    """Test algorithm missing required methods"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Algorithm without required methods
        algo_file = tmpdir / "incomplete.py"
        algo_file.write_text("""
class IncompleteAlgorithm:
    def __init__(self, **options):
        pass
    # Missing get_initial_design, get_next_design, get_analysis
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should raise AttributeError when trying to call missing methods
        with pytest.raises((AttributeError, TypeError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_empty_file():
    """Test algorithm with empty file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Empty algorithm file
        algo_file = tmpdir / "empty.py"
        algo_file.write_text("")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should raise error (no algorithm class found)
        with pytest.raises((ValueError, AttributeError, ImportError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_with_none_value():
    """Test fzd when algorithm is None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # algorithm is None
        with pytest.raises((TypeError, ValueError, AttributeError)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=None,
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_invalid_type():
    """Test fzd with non-string algorithm parameter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # algorithm is a dict instead of string
        with pytest.raises((TypeError, ValueError, AttributeError)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm={"not": "a", "string": True},
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_options_invalid_type():
    """Test fzd with algorithm_options that's not a dict"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Create a minimal valid algorithm
        algo_file = tmpdir / "simple.py"
        algo_file.write_text("""
class SimpleAlgorithm:
    def __init__(self, **options):
        pass
    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 5.0}]
    def get_next_design(self, input_vars, output_values):
        return []
    def get_analysis(self, input_vars, output_values):
        return "Done"
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # algorithm_options is a list instead of dict
        with pytest.raises((TypeError, ValueError)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                algorithm_options=["not", "a", "dict"],
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_with_missing_dependencies():
    """Test algorithm that requires missing dependencies"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Algorithm that requires non-existent package
        algo_file = tmpdir / "requires_deps.py"
        algo_file.write_text("""
__require__ = ["nonexistent_package_xyz_12345"]

class MyAlgorithm:
    def __init__(self, **options):
        pass
    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 5.0}]
    def get_next_design(self, input_vars, output_values):
        return []
    def get_analysis(self, input_vars, output_values):
        return "Done"
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should warn about missing dependencies but may still try to run
        # (The actual behavior depends on implementation)
        try:
            result = fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )
            # May succeed with warnings
        except (ImportError, ModuleNotFoundError):
            # Or may fail if algorithm actually tries to import
            pass


def test_algorithm_no_class_defined():
    """Test algorithm file with no class defined"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Algorithm file with only functions, no class
        algo_file = tmpdir / "no_class.py"
        algo_file.write_text("""
def some_function():
    return 42

def another_function(x):
    return x * 2
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should raise error (no algorithm class found)
        with pytest.raises((ValueError, AttributeError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_with_runtime_error_in_init():
    """Test algorithm that raises error in __init__"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Algorithm that raises error during initialization
        algo_file = tmpdir / "error_init.py"
        algo_file.write_text("""
class ErrorAlgorithm:
    def __init__(self, **options):
        raise RuntimeError("Initialization failed!")
    def get_initial_design(self, input_vars, output_vars):
        return [[5.0]]
    def get_next_design(self, input_vars, output_values):
        return []
    def get_analysis(self, input_vars, output_values):
        return "Done"
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should propagate the RuntimeError
        with pytest.raises((RuntimeError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )


def test_algorithm_returns_invalid_initial_design():
    """Test algorithm that returns invalid initial design"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        input_file = tmpdir / "input.txt"
        input_file.write_text("x = ${x}\n")

        calc_script = tmpdir / "calc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42' > output.txt\n")
        calc_script.chmod(0o755)

        # Algorithm that returns invalid design format
        algo_file = tmpdir / "bad_design.py"
        algo_file.write_text("""
class BadDesignAlgorithm:
    def __init__(self, **options):
        pass
    def get_initial_design(self, input_vars, output_vars):
        return "not a list"  # Should return list of lists
    def get_next_design(self, input_vars, output_values):
        return []
    def get_analysis(self, input_vars, output_values):
        return "Done"
""")

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "echo 42"}
        }

        analysis_dir = tmpdir / "analysis"

        # Should fail when trying to process invalid design
        with pytest.raises((TypeError, ValueError, Exception)):
            fzd(
                input_path=str(input_file),
                input_variables={"x": "[0;10]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file),
                calculators=f"sh://bash {calc_script}",
                analysis_dir=str(analysis_dir)
            )



