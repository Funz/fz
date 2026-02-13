"""
Test algorithm options resolution with various formats

Tests that algorithm_options can be provided as:
- Dict (direct)
- JSON string
- JSON file path
"""
import os
import tempfile
import json
from pathlib import Path
import shutil

import pytest


class TestAlgorithmOptionsResolution:
    """Test algorithm options resolution patterns"""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace"""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    def test_dict_options(self, temp_workspace):
        """Test passing options as a dict"""
        from fz.helpers import _resolve_algorithm_options

        options = {"batch_size": 10, "max_iter": 100, "seed": 42}
        result = _resolve_algorithm_options(options)
        
        assert result == options
        assert result["batch_size"] == 10
        assert result["max_iter"] == 100
        assert result["seed"] == 42

    def test_json_string_options(self, temp_workspace):
        """Test passing options as a JSON string"""
        from fz.helpers import _resolve_algorithm_options

        json_str = '{"batch_size": 10, "max_iter": 100, "seed": 42}'
        result = _resolve_algorithm_options(json_str)
        
        assert isinstance(result, dict)
        assert result["batch_size"] == 10
        assert result["max_iter"] == 100
        assert result["seed"] == 42

    def test_json_file_options(self, temp_workspace):
        """Test passing options as a JSON file path"""
        from fz.helpers import _resolve_algorithm_options

        # Create a JSON file
        options_file = temp_workspace / "algo_options.json"
        options_data = {"batch_size": 10, "max_iter": 100, "seed": 42}
        with open(options_file, 'w') as f:
            json.dump(options_data, f)

        result = _resolve_algorithm_options(str(options_file))
        
        assert isinstance(result, dict)
        assert result["batch_size"] == 10
        assert result["max_iter"] == 100
        assert result["seed"] == 42

    def test_none_options(self, temp_workspace):
        """Test None returns empty dict"""
        from fz.helpers import _resolve_algorithm_options

        result = _resolve_algorithm_options(None)
        
        assert result == {}

    def test_empty_dict_options(self, temp_workspace):
        """Test empty dict is preserved"""
        from fz.helpers import _resolve_algorithm_options

        result = _resolve_algorithm_options({})
        
        assert result == {}

    def test_json_string_with_nested_objects(self, temp_workspace):
        """Test JSON string with nested objects"""
        from fz.helpers import _resolve_algorithm_options

        json_str = '{"bounds": {"x": [0, 10], "y": [0, 5]}, "tol": 1e-6}'
        result = _resolve_algorithm_options(json_str)
        
        assert isinstance(result, dict)
        assert result["bounds"]["x"] == [0, 10]
        assert result["bounds"]["y"] == [0, 5]
        assert result["tol"] == 1e-6

    def test_json_file_with_complex_types(self, temp_workspace):
        """Test JSON file with various data types"""
        from fz.helpers import _resolve_algorithm_options

        options_file = temp_workspace / "complex_options.json"
        options_data = {
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "string_val": "test",
            "list_val": [1, 2, 3],
            "nested": {"a": 1, "b": 2}
        }
        with open(options_file, 'w') as f:
            json.dump(options_data, f)

        result = _resolve_algorithm_options(str(options_file))
        
        assert result["int_val"] == 42
        assert result["float_val"] == 3.14
        assert result["bool_val"] is True
        assert result["string_val"] == "test"
        assert result["list_val"] == [1, 2, 3]
        assert result["nested"]["a"] == 1

    def test_invalid_json_string(self, temp_workspace):
        """Test error handling for invalid JSON string"""
        from fz.helpers import _resolve_algorithm_options

        invalid_json = '{"batch_size": 10, "max_iter": }'
        
        with pytest.raises(ValueError, match="Could not parse algorithm_options"):
            _resolve_algorithm_options(invalid_json)

    def test_nonexistent_json_file(self, temp_workspace):
        """Test error handling for non-existent JSON file"""
        from fz.helpers import _resolve_algorithm_options

        nonexistent_file = str(temp_workspace / "nonexistent.json")
        
        with pytest.raises(ValueError, match="Could not parse algorithm_options"):
            _resolve_algorithm_options(nonexistent_file)

    def test_invalid_type(self, temp_workspace):
        """Test error handling for invalid type"""
        from fz.helpers import _resolve_algorithm_options

        with pytest.raises(TypeError, match="Algorithm options must be"):
            _resolve_algorithm_options(123)

        with pytest.raises(TypeError, match="Algorithm options must be"):
            _resolve_algorithm_options([1, 2, 3])

    def test_json_file_with_invalid_content(self, temp_workspace):
        """Test error handling for JSON file with invalid content"""
        from fz.helpers import _resolve_algorithm_options

        # Create a file with invalid JSON
        invalid_file = temp_workspace / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write("not valid json {")

        with pytest.raises(ValueError, match="Could not parse algorithm_options"):
            _resolve_algorithm_options(str(invalid_file))

    def test_json_string_returns_non_dict(self, temp_workspace):
        """Test error when JSON string doesn't parse to dict"""
        from fz.helpers import _resolve_algorithm_options

        # Array instead of dict
        json_str = '[1, 2, 3]'
        
        with pytest.raises(TypeError, match="Algorithm options must be a dict"):
            _resolve_algorithm_options(json_str)

    def test_json_file_returns_non_dict(self, temp_workspace):
        """Test error when JSON file doesn't contain dict"""
        from fz.helpers import _resolve_algorithm_options

        # Create a JSON file with an array
        array_file = temp_workspace / "array.json"
        with open(array_file, 'w') as f:
            json.dump([1, 2, 3], f)

        with pytest.raises(TypeError, match="Algorithm options must be a dict"):
            _resolve_algorithm_options(str(array_file))


class TestFzdWithAlgorithmOptions:
    """Test fzd function with different algorithm_options formats"""

    @pytest.fixture
    def simple_model_setup(self):
        """Create a simple test model and input files"""
        tmpdir = tempfile.mkdtemp()
        workspace = Path(tmpdir)
        original_cwd = os.getcwd()
        
        # Create input file
        input_file = workspace / "input.txt"
        input_file.write_text("x = {x}\ny = {y}\n")
        
        # Create model
        model = {
            "id": "testmodel",
            "input": {
                "files": ["input.txt"]
            },
            "output": {
                "result": {
                    "pattern": r"result:\s*([\d.]+)"
                }
            }
        }
        
        # Create a simple algorithm
        algorithms_dir = workspace / ".fz" / "algorithms"
        algorithms_dir.mkdir(parents=True)
        
        algo_file = algorithms_dir / "testalgo.py"
        algo_file.write_text("""
class TestAlgorithm:
    def __init__(self, **options):
        self.options = options
        self.batch_size = options.get('batch_size', 5)
        self.max_iter = options.get('max_iter', 2)
        
    def get_initial_design(self, input_variables, output_expression):
        # Return simple design
        designs = []
        for i in range(self.batch_size):
            designs.append({k: v.split(';')[0].strip('[') for k, v in input_variables.items()})
        return designs
        
    def get_next_design(self, X, Y):
        return []  # No more iterations
        
    def get_analysis(self, X, Y):
        return {"text": f"Completed with options: {self.options}"}
""")
        
        yield workspace, model
        
        # Ensure we're not in the temp directory before cleanup (Windows compatibility)
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir)

    def test_fzd_with_dict_options(self, simple_model_setup):
        """Test fzd with dict algorithm_options"""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas required for fzd")
        
        import fz
        
        workspace, model = simple_model_setup
        os.chdir(workspace)
        
        # Skip test if bc command not available
        if shutil.which("bc") is None:
            pytest.skip("bc command not available")
        
        # This test just verifies options are passed correctly
        # We won't run actual calculations, just load the algorithm
        from fz.algorithms import load_algorithm
        
        algo = load_algorithm("testalgo", batch_size=10, max_iter=100)
        assert algo.options["batch_size"] == 10
        assert algo.options["max_iter"] == 100

    def test_fzd_with_json_string_options(self, simple_model_setup):
        """Test fzd with JSON string algorithm_options"""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas required for fzd")
        
        workspace, model = simple_model_setup
        os.chdir(workspace)
        
        from fz.helpers import _resolve_algorithm_options
        
        # Test resolution
        json_str = '{"batch_size": 15, "max_iter": 200}'
        options = _resolve_algorithm_options(json_str)
        
        # Load algorithm with resolved options
        from fz.algorithms import load_algorithm
        algo = load_algorithm("testalgo", **options)
        
        assert algo.options["batch_size"] == 15
        assert algo.options["max_iter"] == 200

    def test_fzd_with_json_file_options(self, simple_model_setup):
        """Test fzd with JSON file algorithm_options"""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas required for fzd")
        
        workspace, model = simple_model_setup
        os.chdir(workspace)
        
        # Create options file
        options_file = workspace / "algo_opts.json"
        options_data = {"batch_size": 20, "max_iter": 300}
        with open(options_file, 'w') as f:
            json.dump(options_data, f)
        
        from fz.helpers import _resolve_algorithm_options
        
        # Test resolution
        options = _resolve_algorithm_options(str(options_file))
        
        # Load algorithm with resolved options
        from fz.algorithms import load_algorithm
        algo = load_algorithm("testalgo", **options)
        
        assert algo.options["batch_size"] == 20
        assert algo.options["max_iter"] == 300


class TestCLIAlgorithmOptions:
    """Test CLI already supports algorithm options via parse_algorithm_options"""

    def test_cli_parse_algorithm_options_json_string(self):
        """Test CLI parse_algorithm_options with JSON string"""
        from fz.cli import parse_algorithm_options
        
        json_str = '{"batch_size": 10, "seed": 42}'
        result = parse_algorithm_options(json_str)
        
        assert isinstance(result, dict)
        assert result["batch_size"] == 10
        assert result["seed"] == 42

    def test_cli_parse_algorithm_options_json_file(self):
        """Test CLI parse_algorithm_options with JSON file"""
        from fz.cli import parse_algorithm_options
        
        tmpdir = tempfile.mkdtemp()
        try:
            options_file = Path(tmpdir) / "options.json"
            with open(options_file, 'w') as f:
                json.dump({"max_iter": 100}, f)
            
            result = parse_algorithm_options(str(options_file))
            
            assert isinstance(result, dict)
            assert result["max_iter"] == 100
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
