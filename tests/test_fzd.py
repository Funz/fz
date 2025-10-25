"""
Tests for fzd (iterative design of experiments with algorithms)
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

# Add parent directory to path for importing fz
sys.path.insert(0, str(Path(__file__).parent.parent))

import fz
from fz.algorithms import parse_input_vars, evaluate_output_expression, load_algorithm


class TestParseInputVars:
    """Test input variable range parsing"""

    def test_parse_simple_range(self):
        """Test parsing simple ranges"""
        result = parse_input_vars({"x": "[0;1]", "y": "[-5;5]"})
        assert result == {"x": (0.0, 1.0), "y": (-5.0, 5.0)}

    def test_parse_mixed_range_and_fixed(self):
        """Test parsing mix of ranges and fixed values"""
        from fz.algorithms import parse_fixed_vars

        input_vars = {"x": "[0;1]", "y": "0.5", "z": "[-2;2]"}

        # Variable ranges
        ranges = parse_input_vars(input_vars)
        assert ranges == {"x": (0.0, 1.0), "z": (-2.0, 2.0)}

        # Fixed values
        fixed = parse_fixed_vars(input_vars)
        assert fixed == {"y": 0.5}

    def test_parse_comma_delimiter(self):
        """Test parsing with comma delimiter"""
        result = parse_input_vars({"x": "[0,1]"})
        assert result == {"x": (0.0, 1.0)}

    def test_parse_float_range(self):
        """Test parsing float ranges"""
        result = parse_input_vars({"x": "[0.5;1.5]"})
        assert result == {"x": (0.5, 1.5)}

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises error"""
        with pytest.raises(ValueError, match="Invalid format"):
            parse_input_vars({"x": "0;1"})  # Missing brackets - not a valid range or fixed value

    def test_parse_invalid_order(self):
        """Test parsing invalid order raises error"""
        with pytest.raises(ValueError, match="min .* must be < max"):
            parse_input_vars({"x": "[1;0]"})  # min > max


class TestEvaluateOutputExpression:
    """Test output expression evaluation"""

    def test_simple_addition(self):
        """Test simple addition"""
        result = evaluate_output_expression("x + y", {"x": 1.0, "y": 2.0})
        assert result == 3.0

    def test_multiplication(self):
        """Test multiplication"""
        result = evaluate_output_expression("x * 2", {"x": 3.0})
        assert result == 6.0

    def test_complex_expression(self):
        """Test complex expression"""
        result = evaluate_output_expression("x + y * 2", {"x": 1.0, "y": 3.0})
        assert result == 7.0

    def test_math_functions(self):
        """Test math functions"""
        result = evaluate_output_expression("sqrt(x)", {"x": 4.0})
        assert result == 2.0

    def test_invalid_expression(self):
        """Test invalid expression raises error"""
        with pytest.raises(ValueError):
            evaluate_output_expression("x + z", {"x": 1.0})  # z not defined

class TestFzdIntegration:
    """Integration tests for fzd function"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def simple_model(self, temp_dir):
        """Create a simple test model"""
        # Create input file
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()

        input_file = input_dir / "input.txt"
        input_file.write_text("x = $x\ny = $y\n")

        # Create model
        model = {
            "varprefix": "$",
            "delim": "()",
            "run": "bash -c 'source input.txt && result=$(echo \"scale=6; $x * $x + $y * $y\" | bc) && echo \"result = $result\" > output.txt'",
            "output": {
                "result": "grep 'result = ' output.txt | cut -d '=' -f2 | tr -d ' '"
            }
        }

        return input_dir, model

    def test_fzd_randomsampling(self, simple_model):
        """Test fzd with randomsampling"""
        input_dir, model = simple_model

        # Skip if bc is not available (used in model)
        if shutil.which("bc") is None:
            pytest.skip("bc command not available")

        # Path to randomsampling algorithm
        algo_path = str(Path(__file__).parent.parent / "examples" / "algorithms" / "randomsampling.py")

        # Run fzd with randomsampling
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[0;1]", "y": "[0;1]"},
            model=model,
            output_expression="result",
            algorithm=algo_path,
            algorithm_options={"nvalues": 3, "seed": 42}
        )

        assert result is not None
        assert "XY" in result
        assert len(result["XY"]) == 3
        assert "x" in result["XY"].columns
        assert "y" in result["XY"].columns
        assert "result" in result["XY"].columns  # output_expression as column name
        assert algo_path in result["algorithm"]  # algorithm field contains the path

    def test_fzd_requires_pandas(self, simple_model):
        """Test that fzd raises ImportError when pandas is not available"""
        from unittest.mock import patch
        import fz.core

        input_dir, model = simple_model
        algo_path = str(Path(__file__).parent.parent / "examples" / "algorithms" / "randomsampling.py")

        # Mock PANDAS_AVAILABLE to be False
        with patch.object(fz.core, 'PANDAS_AVAILABLE', False):
            with pytest.raises(ImportError, match="fzd requires pandas"):
                fz.fzd(
                    input_file=str(input_dir),
                    input_variables={"x": "[0;1]"},
                    model=model,
                    output_expression="result",
                    algorithm=algo_path
                )

    def test_fzd_returns_dataframe(self, simple_model):
        """Test that fzd returns XY DataFrame with all X and Y values"""
        input_dir, model = simple_model

        # Skip if bc is not available (used in model)
        if shutil.which("bc") is None:
            pytest.skip("bc command not available")

        # Path to randomsampling algorithm
        algo_path = str(Path(__file__).parent.parent / "examples" / "algorithms" / "randomsampling.py")

        # Run fzd
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={"x": "[0;1]", "y": "[0;1]"},
            model=model,
            output_expression="result",  # This becomes the column name
            algorithm=algo_path,
            algorithm_options={"nvalues": 3, "seed": 42}
        )

        # Check that XY DataFrame is included
        assert 'XY' in result
        assert result['XY'] is not None

        # Check DataFrame structure
        df = result['XY']
        assert len(df) == 3  # 3 evaluations
        assert 'x' in df.columns
        assert 'y' in df.columns
        assert 'result' in df.columns  # Output column named with output_expression

        # Check that input_vars and output_values are not in result
        assert 'input_vars' not in result
        assert 'output_values' not in result

        # Verify data types and structure
        assert df['x'].dtype == 'float64'
        assert df['y'].dtype == 'float64'
        # result column may have None values, so check object type
        assert df['result'].dtype in ['float64', 'object']

    def test_fzd_with_fixed_variables(self, simple_model):
        """Test that fzd only varies non-fixed variables"""
        input_dir, model = simple_model

        # Skip if bc is not available (used in model)
        if shutil.which("bc") is None:
            pytest.skip("bc command not available")

        # Path to randomsampling algorithm
        algo_path = str(Path(__file__).parent.parent / "examples" / "algorithms" / "randomsampling.py")

        # Run fzd with one variable range and one fixed value
        result = fz.fzd(
            input_file=str(input_dir),
            input_variables={
                "x": "[0;1]",  # Variable - will be varied by algorithm
                "y": "0.5"     # Fixed - will NOT be varied
            },
            model=model,
            output_expression="result",
            algorithm=algo_path,
            algorithm_options={"nvalues": 3, "seed": 42}
        )

        # Check that XY DataFrame has both columns
        assert 'XY' in result
        df = result['XY']
        assert 'x' in df.columns
        assert 'y' in df.columns
        assert 'result' in df.columns

        # Check that y is fixed at 0.5 for all rows
        assert len(df) == 3
        assert all(df['y'] == 0.5), "y should be fixed at 0.5 for all evaluations"

        # Check that x varies
        assert len(df['x'].unique()) > 1, "x should vary across evaluations"

    def test_fzd_get_analysis_tmp(self, temp_dir):
        """Test that get_analysis_tmp is called at each iteration if it exists"""
        from unittest.mock import Mock, patch

        # Create a simple model
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        (input_dir / "input.txt").write_text("x = $x\n")

        model = {
            "varprefix": "$",
            "delim": "()",
            "run": "echo 'result = 1.0' > output.txt",
            "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
        }

        # Create algorithm with get_analysis_tmp
        algo_file = Path(temp_dir) / "algo_with_tmp.py"
        algo_file.write_text("""
class TestAlgorithm:
    def __init__(self, **options):
        self.call_count = 0

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        # Run 2 iterations
        self.call_count += 1
        if self.call_count < 2:
            return [{"x": 0.7}]
        return []

    def get_analysis(self, X, Y):
        return {"text": "Final", "data": {}}

    def get_analysis_tmp(self, X, Y):
        return {"text": f"Iteration progress: {len(X)} samples", "data": {}}
""")

        # Mock logging to capture calls
        with patch('fz.core.log_info') as mock_log:
            result = fz.fzd(
                input_file=str(input_dir),
                input_variables={"x": "[0;1]"},
                model=model,
                output_expression="result",
                algorithm=str(algo_file)
            )

            # Verify get_analysis_tmp was called
            # Should be called twice (once after each iteration)
            tmp_calls = [call for call in mock_log.call_args_list
                        if 'intermediate results' in str(call)]
            assert len(tmp_calls) >= 2, "get_analysis_tmp should be called at each iteration"


class TestLoadAlgorithmFromFile:
    """Test loading algorithms from Python files"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir)

    def test_load_algorithm_from_file(self, temp_dir):
        """Test loading an algorithm from a Python file"""
        # Create a simple algorithm file
        algo_file = Path(temp_dir) / "simple_algo.py"
        algo_file.write_text("""
class SimpleAlgorithm:
    def __init__(self, **options):
        self.options = options
        self.nvalues = options.get("nvalues", 5)

    def get_initial_design(self, input_vars, output_vars):
        # Return center point
        return [{var: (bounds[0] + bounds[1]) / 2 for var, bounds in input_vars.items()}]

    def get_next_design(self, X, Y):
        # No next design
        return []

    def get_analysis(self, X, Y):
        return {"text": "Test results", "data": {}}
""")

        # Load algorithm from file
        algo = load_algorithm(str(algo_file), nvalues=10)
        assert algo is not None
        assert algo.nvalues == 10

        # Test initial design
        input_vars = {"x": (0.0, 1.0), "y": (-5.0, 5.0)}
        design = algo.get_initial_design(input_vars, ["output"])
        assert len(design) == 1
        assert design[0]["x"] == 0.5
        assert design[0]["y"] == 0.0

    def test_load_montecarlo_algorithm(self):
        """Test loading the MonteCarlo_Uniform algorithm from file"""
        # Use the test_algorithm_montecarlo.py file we just created
        algo_file = Path(__file__).parent / "test_algorithm_montecarlo.py"

        # Load algorithm from file
        algo = load_algorithm(str(algo_file), batch_sample_size=5, seed=42)
        assert algo is not None

        # Test initial design
        input_vars = {"x": (0.0, 1.0), "y": (-5.0, 5.0)}
        design = algo.get_initial_design(input_vars, ["output"])
        assert len(design) == 5

        # Check that all points are within bounds
        for point in design:
            assert 0.0 <= point["x"] <= 1.0
            assert -5.0 <= point["y"] <= 5.0

    def test_load_algorithm_with_metadata(self, temp_dir):
        """Test loading algorithm with metadata comments"""
        algo_file = Path(temp_dir) / "algo_with_metadata.py"
        algo_file.write_text("""#title: Test Algorithm
#author: Test Author
#type: optimization
#options: param1=10;param2=0.5
#require: numpy

class TestAlgo:
    def __init__(self, **options):
        self.options = options
        self.param1 = int(options.get("param1", 5))
        self.param2 = float(options.get("param2", 0.1))

    def get_initial_design(self, input_vars, output_vars):
        return []

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Test", "data": {}}
""")

        # Load algorithm (should use default options from metadata)
        algo = load_algorithm(str(algo_file))
        assert algo.param1 == 10
        assert algo.param2 == 0.5

        # Load with explicit options (should override metadata)
        algo2 = load_algorithm(str(algo_file), param1=20)
        assert algo2.param1 == 20
        assert algo2.param2 == 0.5  # Still from metadata

    def test_load_algorithm_invalid_file(self):
        """Test loading from non-existent file"""
        with pytest.raises(ValueError, match="Algorithm file not found"):
            load_algorithm("nonexistent_algo.py")

    def test_load_algorithm_non_python_file(self, temp_dir):
        """Test loading from non-.py file"""
        txt_file = Path(temp_dir) / "not_python.txt"
        txt_file.write_text("Not a Python file")

        with pytest.raises(ValueError, match="must be a Python file"):
            load_algorithm(str(txt_file))

    def test_load_algorithm_no_class(self, temp_dir):
        """Test loading from file with no algorithm class"""
        algo_file = Path(temp_dir) / "no_class.py"
        algo_file.write_text("""
# This file has no algorithm class
def some_function():
    pass
""")

        with pytest.raises(ValueError, match="No valid algorithm class found"):
            load_algorithm(str(algo_file))

    def test_load_algorithm_with_require_installed(self, temp_dir):
        """Test loading algorithm with #require: header for already installed packages"""
        algo_file = Path(temp_dir) / "algo_with_require.py"
        algo_file.write_text("""
#title: Test Algorithm
#require: sys;os

class TestAlgorithm:
    def __init__(self, **options):
        import sys
        import os
        self.options = options

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Test", "data": {}}
""")

        # Should load successfully without trying to install sys/os (they're built-in)
        algo = load_algorithm(str(algo_file))
        assert algo is not None

    def test_load_algorithm_with_require_missing(self, temp_dir):
        """Test that missing packages trigger installation attempt"""
        from unittest.mock import patch, MagicMock
        import fz.algorithms

        algo_file = Path(temp_dir) / "algo_missing_pkg.py"
        algo_file.write_text("""
#require: nonexistent_test_package_12345

class TestAlgorithm:
    def __init__(self, **options):
        self.options = options

    def get_initial_design(self, input_vars, output_vars):
        return [{"x": 0.5}]

    def get_next_design(self, X, Y):
        return []

    def get_analysis(self, X, Y):
        return {"text": "Test", "data": {}}
""")

        # Mock subprocess.check_call to fail (package doesn't exist)
        with patch('fz.algorithms.subprocess.check_call') as mock_call:
            mock_call.side_effect = fz.algorithms.subprocess.CalledProcessError(1, 'pip')

            # Should raise RuntimeError about failed installation
            with pytest.raises(RuntimeError, match="Failed to install required package"):
                load_algorithm(str(algo_file))


class TestContentDetection:
    """Test content type detection and processing"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir)

    def test_detect_html_content(self):
        """Test HTML content detection"""
        from fz.io import detect_content_type

        html_text = "<div><p>Hello</p></div>"
        assert detect_content_type(html_text) == 'html'

        html_text2 = "<html><body>Test</body></html>"
        assert detect_content_type(html_text2) == 'html'

    def test_detect_json_content(self):
        """Test JSON content detection"""
        from fz.io import detect_content_type

        json_text = '{"key": "value", "number": 42}'
        assert detect_content_type(json_text) == 'json'

        json_array = '[1, 2, 3, 4]'
        assert detect_content_type(json_array) == 'json'

    def test_detect_keyvalue_content(self):
        """Test key=value content detection"""
        from fz.io import detect_content_type

        kv_text = """name = John
age = 30
city = Paris"""
        assert detect_content_type(kv_text) == 'keyvalue'

    def test_detect_markdown_content(self):
        """Test markdown content detection"""
        from fz.io import detect_content_type

        md_text = """# Header
## Subheader
* Item 1
* Item 2"""
        assert detect_content_type(md_text) == 'markdown'

    def test_parse_keyvalue(self):
        """Test parsing key=value text"""
        from fz.io import parse_keyvalue_text

        kv_text = """name = John Doe
age = 30
city = Paris"""
        result = parse_keyvalue_text(kv_text)
        assert result == {'name': 'John Doe', 'age': '30', 'city': 'Paris'}

    def test_process_analysis_content_with_json(self, temp_dir):
        """Test processing analysis content with JSON"""
        from fz.io import process_analysis_content

        results_dir = Path(temp_dir)
        analysis_dict = {
            'text': '{"mean": 1.5, "std": 0.3}',
            'data': {'samples': 10}
        }

        processed = process_analysis_content(analysis_dict, 1, results_dir)

        assert 'json_data' in processed
        assert processed['json_data']['mean'] == 1.5
        assert 'json_file' in processed
        assert (results_dir / processed['json_file']).exists()

    def test_process_analysis_content_with_html(self, temp_dir):
        """Test processing analysis content with HTML"""
        from fz.io import process_analysis_content

        results_dir = Path(temp_dir)
        analysis_dict = {
            'html': '<div><h1>Results</h1><p>Test</p></div>',
            'data': {}
        }

        processed = process_analysis_content(analysis_dict, 1, results_dir)

        assert 'html_file' in processed
        assert (results_dir / processed['html_file']).exists()

    def test_process_analysis_content_with_markdown(self, temp_dir):
        """Test processing analysis content with markdown"""
        from fz.io import process_analysis_content

        results_dir = Path(temp_dir)
        analysis_dict = {
            'text': '# Results\n\n* Item 1\n* Item 2',
            'data': {}
        }

        processed = process_analysis_content(analysis_dict, 1, results_dir)

        assert 'md_file' in processed
        assert (results_dir / processed['md_file']).exists()

    def test_process_analysis_content_with_keyvalue(self, temp_dir):
        """Test processing analysis content with key=value"""
        from fz.io import process_analysis_content

        results_dir = Path(temp_dir)
        analysis_dict = {
            'text': 'mean = 1.5\nstd = 0.3\nsamples = 100',
            'data': {}
        }

        processed = process_analysis_content(analysis_dict, 1, results_dir)

        assert 'keyvalue_data' in processed
        assert processed['keyvalue_data']['mean'] == '1.5'
        assert 'txt_file' in processed
        assert (results_dir / processed['txt_file']).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
