"""
Test numpy array support in input_variables

Tests that input_variables can accept numpy arrays and they are
automatically converted to lists for processing.
"""
import tempfile
from pathlib import Path

import pytest

# Import numpy conditionally
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
class TestNumpyArraySupport:
    """Test numpy array support in fz functions"""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace"""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def sample_input_file(self, temp_workspace):
        """Create a sample input file"""
        input_file = temp_workspace / "input.txt"
        input_file.write_text("x = $x\ny = $y\nz = $z\n")
        return input_file

    @pytest.fixture
    def sample_model(self):
        """Return a sample model"""
        return {"varprefix": "$", "delim": "{}"}

    def test_convert_numpy_to_list(self):
        """Test the numpy array conversion helper"""
        from fz.helpers import _convert_numpy_to_list

        # Test numpy array conversion
        arr = np.array([1, 2, 3])
        converted = _convert_numpy_to_list(arr)
        assert isinstance(converted, list)
        assert converted == [1, 2, 3]

        # Test 2D array
        arr2d = np.array([[1, 2], [3, 4]])
        converted2d = _convert_numpy_to_list(arr2d)
        assert isinstance(converted2d, list)
        assert converted2d == [[1, 2], [3, 4]]

        # Test list stays list
        lst = [1, 2, 3]
        converted_lst = _convert_numpy_to_list(lst)
        assert isinstance(converted_lst, list)
        assert converted_lst == [1, 2, 3]

        # Test scalar stays scalar
        scalar = 5
        converted_scalar = _convert_numpy_to_list(scalar)
        assert converted_scalar == 5

    def test_generate_variable_combinations_with_numpy(self):
        """Test generating variable combinations with numpy arrays"""
        from fz.helpers import generate_variable_combinations

        input_vars = {
            'x': np.array([1, 2]),
            'y': np.array([3, 4]),
            'z': 5
        }

        combos = generate_variable_combinations(input_vars)

        # Should generate 2*2*1 = 4 combinations
        assert len(combos) == 4

        # Check all combinations
        expected = [
            {'x': 1, 'y': 3, 'z': 5},
            {'x': 1, 'y': 4, 'z': 5},
            {'x': 2, 'y': 3, 'z': 5},
            {'x': 2, 'y': 4, 'z': 5},
        ]
        assert combos == expected

    def test_fzc_with_numpy_arrays(self, sample_input_file, sample_model, temp_workspace):
        """Test fzc with numpy arrays in input_variables"""
        import fz

        output_dir = temp_workspace / "output"

        input_vars = {
            'x': np.array([1, 2]),
            'y': np.array([10, 20]),
            'z': 100
        }

        # Should not raise an error
        fz.fzc(str(sample_input_file), input_vars, sample_model, output_dir=str(output_dir))

        # Check generated directories
        subdirs = sorted([d.name for d in output_dir.iterdir() if d.is_dir()])
        
        # Should generate 2*2*1 = 4 directories
        assert len(subdirs) == 4

        # Check first directory content
        first_dir = output_dir / "x=1,y=10,z=100"
        assert first_dir.exists()
        
        compiled = (first_dir / "input.txt").read_text()
        assert "x = 1" in compiled
        assert "y = 10" in compiled
        assert "z = 100" in compiled

    def test_fzc_with_mixed_types(self, sample_input_file, sample_model, temp_workspace):
        """Test fzc with mix of numpy arrays and lists"""
        import fz

        output_dir = temp_workspace / "output"

        input_vars = {
            'x': np.array([1, 2]),  # numpy array
            'y': [10, 20],           # list
            'z': 100                 # scalar
        }

        fz.fzc(str(sample_input_file), input_vars, sample_model, output_dir=str(output_dir))

        subdirs = [d.name for d in output_dir.iterdir() if d.is_dir()]
        assert len(subdirs) == 4  # 2*2*1 combinations

    def test_fzi_with_numpy_context(self, sample_input_file, sample_model):
        """Test that fzi still works (doesn't use numpy in input_variables)"""
        import fz

        # fzi doesn't take input_variables, so just verify it works
        result = fz.fzi(str(sample_input_file), sample_model)
        
        assert 'x' in result
        assert 'y' in result
        assert 'z' in result

    def test_numpy_array_with_floats(self, sample_input_file, sample_model, temp_workspace):
        """Test numpy arrays with float values"""
        import fz

        output_dir = temp_workspace / "output"

        input_vars = {
            'x': np.array([1.5, 2.5]),
            'y': np.array([10.0]),
            'z': 100
        }

        fz.fzc(str(sample_input_file), input_vars, sample_model, output_dir=str(output_dir))

        # Check that float values are preserved
        first_dir = output_dir / "x=1.5,y=10.0,z=100"
        assert first_dir.exists()
        
        compiled = (first_dir / "input.txt").read_text()
        assert "x = 1.5" in compiled

    def test_numpy_arange_and_linspace(self, temp_workspace):
        """Test with numpy's arange and linspace functions"""
        import fz
        from fz.helpers import generate_variable_combinations

        # Test with np.arange
        input_vars_arange = {
            'x': np.arange(0, 3),  # [0, 1, 2]
            'y': [10, 20]
        }
        
        combos = generate_variable_combinations(input_vars_arange)
        assert len(combos) == 6  # 3*2
        assert combos[0] == {'x': 0, 'y': 10}
        assert combos[1] == {'x': 0, 'y': 20}

        # Test with np.linspace
        input_vars_linspace = {
            'x': np.linspace(0, 1, 3),  # [0.0, 0.5, 1.0]
            'y': [1]
        }
        
        combos = generate_variable_combinations(input_vars_linspace)
        assert len(combos) == 3
        assert abs(combos[0]['x'] - 0.0) < 1e-10
        assert abs(combos[1]['x'] - 0.5) < 1e-10
        assert abs(combos[2]['x'] - 1.0) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
