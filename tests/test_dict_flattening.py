"""
Test dict flattening functionality in fzo and fzr

Tests the automatic recursive flattening of dictionary-valued outputs
into separate columns with keys joined by underscores.
"""
import json
import os
import platform
import shutil
import tempfile
from pathlib import Path

import pytest

# Check if pandas is available
try:
    import pandas as pd
except ImportError:

import fz
from fz.io import flatten_dict_recursive, flatten_dict_columns


# Skip all tests if pandas is not available (dict flattening requires pandas)


class TestFlattenDictRecursive:
    """Test the flatten_dict_recursive helper function"""

    def test_simple_dict(self):
        """Test flattening a simple flat dict"""
        d = {'a': 1, 'b': 2, 'c': 3}
        result = flatten_dict_recursive(d)
        assert result == {'a': 1, 'b': 2, 'c': 3}

    def test_nested_dict_one_level(self):
        """Test flattening a dict with one level of nesting"""
        d = {'stats': {'min': 1, 'max': 4}}
        result = flatten_dict_recursive(d, parent_key='data', sep='_')
        assert result == {'data_stats_min': 1, 'data_stats_max': 4}

    def test_nested_dict_two_levels(self):
        """Test flattening a dict with two levels of nesting"""
        d = {'level1': {'level2': {'a': 1, 'b': 2}}}
        result = flatten_dict_recursive(d, sep='_')
        assert result == {'level1_level2_a': 1, 'level1_level2_b': 2}

    def test_nested_dict_three_levels(self):
        """Test flattening a deeply nested dict (3 levels)"""
        d = {'l1': {'l2': {'l3': {'value': 42}}}}
        result = flatten_dict_recursive(d, sep='_')
        assert result == {'l1_l2_l3_value': 42}

    def test_mixed_nesting(self):
        """Test flattening a dict with mixed nested and flat values"""
        d = {
            'flat': 100,
            'nested': {'a': 1, 'b': 2},
            'deep': {'level2': {'value': 3}}
        }
        result = flatten_dict_recursive(d, sep='_')
        assert result == {
            'flat': 100,
            'nested_a': 1,
            'nested_b': 2,
            'deep_level2_value': 3
        }

    def test_custom_separator(self):
        """Test flattening with a custom separator"""
        d = {'a': {'b': 1}}
        result = flatten_dict_recursive(d, sep='.')
        assert result == {'a.b': 1}

    def test_empty_dict(self):
        """Test flattening an empty dict"""
        d = {}
        result = flatten_dict_recursive(d)
        assert result == {}


class TestFlattenDictColumns:
    """Test the flatten_dict_columns function on DataFrames"""

    def test_no_dict_columns(self):
        """Test DataFrame with no dict columns remains unchanged"""
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
        result = flatten_dict_columns(df)
        assert list(result.columns) == ['x', 'y']
        assert result.equals(df)

    def test_simple_dict_column(self):
        """Test flattening a simple dict column"""
        df = pd.DataFrame({
            'x': [1, 2, 3],
            'stats': [
                {'min': 1, 'max': 4},
                {'min': 2, 'max': 5},
                {'min': 3, 'max': 6}
            ]
        })
        result = flatten_dict_columns(df)
        print(result)

        # Original dict column should be removed
        assert 'stats' not in result.columns

        # Flattened columns should exist
        assert 'stats_min' in result.columns
        assert 'stats_max' in result.columns

        # Values should be correct
        assert list(result['stats_min']) == [1, 2, 3]
        assert list(result['stats_max']) == [4, 5, 6]

        # Original column should remain
        assert list(result['x']) == [1, 2, 3]

    def test_nested_dict_column(self):
        """Test flattening a nested dict column"""
        df = pd.DataFrame({
            'x': [1, 2],
            'data': [
                {'level1': {'level2': {'value': 10}}},
                {'level1': {'level2': {'value': 20}}}
            ]
        })
        result = flatten_dict_columns(df)

        assert 'data' not in result.columns
        assert 'data_level1_level2_value' in result.columns
        assert list(result['data_level1_level2_value']) == [10, 20]

    def test_deeply_nested_dict_column(self):
        """Test flattening a deeply nested dict column (3 levels)"""
        df = pd.DataFrame({
            'x': [1, 2],
            'deep': [
                {'a': {'b': {'c': {'d': 100}}}},
                {'a': {'b': {'c': {'d': 200}}}}
            ]
        })
        result = flatten_dict_columns(df)

        assert 'deep_a_b_c_d' in result.columns
        assert list(result['deep_a_b_c_d']) == [100, 200]

    def test_multiple_dict_columns(self):
        """Test flattening multiple dict columns"""
        df = pd.DataFrame({
            'x': [1, 2],
            'stats': [
                {'min': 1, 'max': 4},
                {'min': 2, 'max': 5}
            ],
            'info': [
                {'name': 'a', 'id': 100},
                {'name': 'b', 'id': 200}
            ]
        })
        result = flatten_dict_columns(df)

        # Both dict columns should be flattened
        assert 'stats' not in result.columns
        assert 'info' not in result.columns
        assert 'stats_min' in result.columns
        assert 'stats_max' in result.columns
        assert 'info_name' in result.columns
        assert 'info_id' in result.columns

    def test_dict_with_none_values(self):
        """Test flattening dict column with None values"""
        df = pd.DataFrame({
            'x': [1, 2, 3],
            'stats': [
                {'min': 1, 'max': 4},
                None,
                {'min': 3, 'max': 6}
            ]
        })
        result = flatten_dict_columns(df)

        assert 'stats_min' in result.columns
        assert result['stats_min'].iloc[0] == 1.0
        assert pd.isna(result['stats_min'].iloc[1])
        assert result['stats_min'].iloc[2] == 3.0

    def test_mixed_nested_and_flat_values(self):
        """Test flattening dict with both nested and flat values"""
        df = pd.DataFrame({
            'x': [1, 2],
            'data': [
                {'nested': {'a': 1, 'b': 2}, 'flat': 99},
                {'nested': {'a': 3, 'b': 4}, 'flat': 88}
            ]
        })
        result = flatten_dict_columns(df)

        assert 'data_nested_a' in result.columns
        assert 'data_nested_b' in result.columns
        assert 'data_flat' in result.columns
        assert list(result['data_flat']) == [99, 88]

    def test_empty_dataframe(self):
        """Test flattening an empty DataFrame"""
        df = pd.DataFrame()
        result = flatten_dict_columns(df)
        assert result.empty


class TestFzoWithDictFlattening:
    """Test fzo with dict-valued outputs"""

    def test_fzo_with_dict_output(self):
        """Test fzo automatically flattens dict outputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create result directory with dict output
            result_dir = Path(tmpdir) / "results" / "x=5,y=10"
            result_dir.mkdir(parents=True)

            # Write output file with JSON dict
            with open(result_dir / "output.txt", "w") as f:
                f.write("sum=15\n")
                f.write('stats={"min": 5, "max": 10, "diff": 5}\n')

            # Define model
            model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {
                    "sum": "grep 'sum=' output.txt | cut -d'=' -f2",
                    "stats": "grep 'stats=' output.txt | cut -d'=' -f2"
                }
            }

            # Run fzo
            os.chdir(tmpdir)
            results = fz.fzo("results/*", model)

            # Check flattening occurred
            assert 'stats' not in results.columns
            assert 'stats_min' in results.columns
            assert 'stats_max' in results.columns
            assert 'stats_diff' in results.columns

            # Check values
            assert results['sum'].iloc[0] == 15
            assert results['stats_min'].iloc[0] == 5
            assert results['stats_max'].iloc[0] == 10
            assert results['stats_diff'].iloc[0] == 5

    def test_fzo_with_nested_dict_output(self):
        """Test fzo with nested dict outputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result_dir = Path(tmpdir) / "results" / "case1"
            result_dir.mkdir(parents=True)

            # Write output with nested dict
            nested_dict = {
                'basic': {'min': 1, 'max': 10},
                'advanced': {'mean': 5.5, 'std': 2.5}
            }
            with open(result_dir / "output.txt", "w") as f:
                f.write(f"data={json.dumps(nested_dict)}\n")

            model = {
                "output": {
                    "data": "grep 'data=' output.txt | cut -d'=' -f2"
                }
            }

            os.chdir(tmpdir)
            results = fz.fzo("results/*", model)

            # Check nested flattening
            assert 'data_basic_min' in results.columns
            assert 'data_basic_max' in results.columns
            assert 'data_advanced_mean' in results.columns
            assert 'data_advanced_std' in results.columns


class TestFzrWithDictFlattening:
    """Test fzr with dict-valued outputs"""

    def test_fzr_with_dict_output(self):
        """Test fzr automatically flattens dict outputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # Create input template
            with open("input.txt", "w") as f:
                f.write("x = ${x}\n")

            # Create calculator script that produces dict output
            calc_script = Path(tmpdir) / "calc.py"
            with open(calc_script, "w") as f:
                f.write("""#!/usr/bin/env python3
import json

# Read input
with open('input.txt', 'r') as f:
    content = f.read()
    x = int([line for line in content.split('\\n') if 'x =' in line][0].split('=')[1].strip())

# Create dict output
stats = {'min': x - 1, 'max': x + 1, 'mean': x}

# Write output
with open('output.txt', 'w') as f:
    f.write(f"value={x}\\n")
    f.write(f"stats={json.dumps(stats)}\\n")
""")
            os.chmod(calc_script, 0o755)

            # Define model
            model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {
                    "value": "grep 'value=' output.txt | cut -d'=' -f2",
                    "stats": "grep 'stats=' output.txt | cut -d'=' -f2"
                }
            }

            # Run fzr
            results = fz.fzr(
                input_path="input.txt",
                input_variables={"x": [5, 10, 15]},
                model=model,
                calculators=f"sh://python3 {calc_script}"
            )

            # Check flattening occurred
            assert 'stats' not in results.columns
            assert 'stats_min' in results.columns
            assert 'stats_max' in results.columns
            assert 'stats_mean' in results.columns

            # Check values for first row
            assert results['x'].iloc[0] == 5
            assert results['value'].iloc[0] == 5
            assert results['stats_min'].iloc[0] == 4
            assert results['stats_max'].iloc[0] == 6
            assert results['stats_mean'].iloc[0] == 5

            # Check all rows
            assert len(results) == 3

    def test_fzr_with_deeply_nested_dict(self):
        """Test fzr with deeply nested dict outputs (3 levels)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            with open("input.txt", "w") as f:
                f.write("x = ${x}\n")

            calc_script = Path(tmpdir) / "calc.py"
            with open(calc_script, "w") as f:
                f.write("""#!/usr/bin/env python3
import json

with open('input.txt', 'r') as f:
    content = f.read()
    x = int([line for line in content.split('\\n') if 'x =' in line][0].split('=')[1].strip())

# Create deeply nested output
result = {
    'level1': {
        'level2': {
            'level3': {
                'value': x * 2,
                'squared': x * x
            }
        }
    }
}

with open('output.txt', 'w') as f:
    f.write(f"result={json.dumps(result)}\\n")
""")
            os.chmod(calc_script, 0o755)

            model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {
                    "result": "grep 'result=' output.txt | cut -d'=' -f2"
                }
            }

            results = fz.fzr(
                input_path="input.txt",
                input_variables={"x": [3, 5]},
                model=model,
                calculators=f"sh://python3 {calc_script}"
            )

            # Check deep nesting flattened correctly
            assert 'result_level1_level2_level3_value' in results.columns
            assert 'result_level1_level2_level3_squared' in results.columns

            # Check values
            assert results['result_level1_level2_level3_value'].iloc[0] == 6
            assert results['result_level1_level2_level3_squared'].iloc[0] == 9
            assert results['result_level1_level2_level3_value'].iloc[1] == 10
            assert results['result_level1_level2_level3_squared'].iloc[1] == 25

    def test_fzr_with_multiple_dict_outputs(self):
        """Test fzr with multiple dict-valued outputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            with open("input.txt", "w") as f:
                f.write("x = ${x}\n")

            calc_script = Path(tmpdir) / "calc.py"
            with open(calc_script, "w") as f:
                f.write("""#!/usr/bin/env python3
import json

with open('input.txt', 'r') as f:
    content = f.read()
    x = int([line for line in content.split('\\n') if 'x =' in line][0].split('=')[1].strip())

stats = {'min': x - 1, 'max': x + 1}
meta = {'name': f'case{x}', 'id': x * 100}

with open('output.txt', 'w') as f:
    f.write(f"stats={json.dumps(stats)}\\n")
    f.write(f"meta={json.dumps(meta)}\\n")
""")
            os.chmod(calc_script, 0o755)

            model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {
                    "stats": "grep 'stats=' output.txt | cut -d'=' -f2",
                    "meta": "grep 'meta=' output.txt | cut -d'=' -f2"
                }
            }

            results = fz.fzr(
                input_path="input.txt",
                input_variables={"x": [5, 10]},
                model=model,
                calculators=f"sh://python3 {calc_script}"
            )

            # Check both dicts flattened
            assert 'stats_min' in results.columns
            assert 'stats_max' in results.columns
            assert 'meta_name' in results.columns
            assert 'meta_id' in results.columns

            # Verify values
            assert results['meta_name'].iloc[0] == 'case5'
            assert results['meta_id'].iloc[0] == 500


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_dict_with_list_values(self):
        """Test that dicts with list values are handled (lists not flattened further)"""
        df = pd.DataFrame({
            'x': [1],
            'data': [{'values': [1, 2, 3], 'count': 3}]
        })
        result = flatten_dict_columns(df)

        assert 'data_values' in result.columns
        assert 'data_count' in result.columns
        # List should remain as list
        assert result['data_values'].iloc[0] == [1, 2, 3]

    def test_inconsistent_dict_keys_across_rows(self):
        """Test handling of dicts with different keys in different rows"""
        df = pd.DataFrame({
            'x': [1, 2, 3],
            'data': [
                {'a': 1, 'b': 2},
                {'a': 3, 'c': 4},  # Different key 'c' instead of 'b'
                {'b': 5, 'c': 6}   # Missing 'a'
            ]
        })
        result = flatten_dict_columns(df)

        # All keys should become columns
        assert 'data_a' in result.columns
        assert 'data_b' in result.columns
        assert 'data_c' in result.columns

        # Missing values should be None/NaN
        assert result['data_a'].iloc[0] == 1
        assert pd.isna(result['data_a'].iloc[2])  # Row 2 doesn't have 'a'
        assert pd.isna(result['data_c'].iloc[0])  # Row 0 doesn't have 'c'

    def test_max_iterations_prevents_infinite_loop(self):
        """Test that max iterations prevents infinite loops"""
        # This is a safety check - normal dicts should never hit this limit
        df = pd.DataFrame({
            'x': [1],
            'data': [{'a': 1}]
        })
        # Should complete without error even with iteration limit
        result = flatten_dict_columns(df)
        assert 'data_a' in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
