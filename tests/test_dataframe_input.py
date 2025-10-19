"""
Test DataFrame input support for non-factorial designs

Tests the ability to use pandas DataFrames as input_variables,
where each row represents one case (non-factorial design).
"""
import pytest
import tempfile
import shutil
from pathlib import Path

# Check if pandas is available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from fz.helpers import generate_variable_combinations
import fz


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
class TestDataFrameInput:
    """Test DataFrame input for non-factorial designs"""

    def test_dataframe_basic(self):
        """Test basic DataFrame input with 3 cases"""
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [10, 20, 30]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 3
        assert var_combinations[0] == {"x": 1, "y": 10}
        assert var_combinations[1] == {"x": 2, "y": 20}
        assert var_combinations[2] == {"x": 3, "y": 30}

    def test_dataframe_non_factorial(self):
        """Test that DataFrame allows non-factorial combinations"""
        # Non-factorial: only specific combinations
        df = pd.DataFrame({
            "temp": [100, 200, 100, 300],
            "pressure": [1.0, 1.0, 2.0, 1.5]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 4
        assert var_combinations[0] == {"temp": 100, "pressure": 1.0}
        assert var_combinations[1] == {"temp": 200, "pressure": 1.0}
        assert var_combinations[2] == {"temp": 100, "pressure": 2.0}
        assert var_combinations[3] == {"temp": 300, "pressure": 1.5}

    def test_dataframe_vs_dict_factorial(self):
        """Test that dict creates factorial design while DataFrame doesn't"""
        # Dict with lists creates Cartesian product (factorial)
        dict_input = {"x": [1, 2], "y": [10, 20]}
        dict_combinations = generate_variable_combinations(dict_input)
        assert len(dict_combinations) == 4  # 2 x 2 = 4 cases

        # DataFrame with same values creates only specified combinations
        df = pd.DataFrame({
            "x": [1, 2],
            "y": [10, 20]
        })
        df_combinations = generate_variable_combinations(df)
        assert len(df_combinations) == 2  # Only 2 cases (rows)

        assert df_combinations[0] == {"x": 1, "y": 10}
        assert df_combinations[1] == {"x": 2, "y": 20}

    def test_dataframe_single_row(self):
        """Test DataFrame with single row"""
        df = pd.DataFrame({
            "a": [42],
            "b": [99]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 1
        assert var_combinations[0] == {"a": 42, "b": 99}

    def test_dataframe_many_columns(self):
        """Test DataFrame with many variables"""
        df = pd.DataFrame({
            "var1": [1, 2],
            "var2": [10, 20],
            "var3": [100, 200],
            "var4": [1000, 2000],
            "var5": [10000, 20000]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 2
        assert var_combinations[0] == {"var1": 1, "var2": 10, "var3": 100, "var4": 1000, "var5": 10000}
        assert var_combinations[1] == {"var1": 2, "var2": 20, "var3": 200, "var4": 2000, "var5": 20000}

    def test_dataframe_mixed_types(self):
        """Test DataFrame with mixed data types"""
        df = pd.DataFrame({
            "int_var": [1, 2, 3],
            "float_var": [1.5, 2.5, 3.5],
            "str_var": ["a", "b", "c"]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 3
        assert var_combinations[0] == {"int_var": 1, "float_var": 1.5, "str_var": "a"}
        assert var_combinations[1] == {"int_var": 2, "float_var": 2.5, "str_var": "b"}
        assert var_combinations[2] == {"int_var": 3, "float_var": 3.5, "str_var": "c"}

    def test_dataframe_with_repeated_values(self):
        """Test DataFrame where same value appears multiple times"""
        df = pd.DataFrame({
            "x": [1, 1, 2, 2, 2],
            "y": [10, 20, 10, 20, 30]
        })

        var_combinations = generate_variable_combinations(df)

        assert len(var_combinations) == 5
        assert var_combinations[0] == {"x": 1, "y": 10}
        assert var_combinations[1] == {"x": 1, "y": 20}
        assert var_combinations[2] == {"x": 2, "y": 10}
        assert var_combinations[3] == {"x": 2, "y": 20}
        assert var_combinations[4] == {"x": 2, "y": 30}


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
class TestDataFrameWithFzr:
    """Integration tests using DataFrame with fzr()"""

    def setup_method(self):
        """Create temporary directory and test files for each test"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

        # Create input template
        # The sum formula will be evaluated by fz, so the result is already in input.txt
        self.input_file = self.test_path / "input.txt"
        with open(self.input_file, "w", newline='\n') as f:
            f.write("x=$x\n")
            f.write("y=$y\n")
            f.write("sum=@{$x + $y}\n")

        # Create simple calculator script that reads from input.txt and computes result
        # Use source and bash arithmetic like test_fzo_fzr_coherence.py does
        self.calc_script = self.test_path / "calc.sh"
        with open(self.calc_script, "w", newline='\n') as f:
            f.write('#!/bin/bash\n')
            f.write('source input.txt\n')
            f.write('result=$((x + y))\n')
            f.write('echo "result = $result" > output.txt\n')
        self.calc_script.chmod(0o755)

    def teardown_method(self):
        """Clean up temporary directory after each test"""
        if self.test_path.exists():
            shutil.rmtree(self.test_path)

    def test_fzr_with_dataframe_basic(self):
        """Test fzr() with DataFrame input"""
        df = pd.DataFrame({
            "x": [1, 2, 3],
            "y": [10, 20, 30]
        })

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "result": "grep 'result = ' output.txt | cut -d '=' -f2"
            }
        }

        results = fz.fzr(
            str(self.input_file),
            df,
            model,
            calculators=f"sh://bash {self.calc_script}",
            results_dir=str(self.test_path / "results")
        )

        # Should have 3 cases from DataFrame
        assert len(results) == 3

        # Check that we got the expected x, y combinations (not factorial)
        results_sorted = results.sort_values("x").reset_index(drop=True)
        assert results_sorted["x"].tolist() == [1, 2, 3]
        assert results_sorted["y"].tolist() == [10, 20, 30]

        # Results should be x + y
        assert results_sorted["result"].tolist() == [11, 22, 33]

    def test_fzr_dataframe_vs_dict(self):
        """Compare DataFrame (non-factorial) vs dict (factorial) behavior"""
        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "result": "grep 'result = ' output.txt | cut -d '=' -f2"
            }
        }

        # DataFrame: only 2 specific combinations
        df = pd.DataFrame({
            "x": [1, 2],
            "y": [10, 20]
        })

        results_df = fz.fzr(
            str(self.input_file),
            df,
            model,
            calculators=f"sh://bash {self.calc_script}",
            results_dir=str(self.test_path / "results_df")
        )

        # Dict: 2x2 = 4 combinations (factorial)
        dict_input = {"x": [1, 2], "y": [10, 20]}

        results_dict = fz.fzr(
            str(self.input_file),
            dict_input,
            model,
            calculators=f"sh://bash {self.calc_script}",
            results_dir=str(self.test_path / "results_dict")
        )

        # DataFrame gives 2 cases
        assert len(results_df) == 2
        assert results_df["x"].tolist() == [1, 2]
        assert results_df["y"].tolist() == [10, 20]
        assert results_df["result"].tolist() == [11, 22]

        # Dict gives 4 cases (factorial)
        assert len(results_dict) == 4
        results_dict_sorted = results_dict.sort_values(["x", "y"]).reset_index(drop=True)
        assert results_dict_sorted["x"].tolist() == [1, 1, 2, 2]
        assert results_dict_sorted["y"].tolist() == [10, 20, 10, 20]
        assert results_dict_sorted["result"].tolist() == [11, 21, 12, 22]

    def test_fzr_dataframe_non_factorial_pattern(self):
        """Test DataFrame with non-factorial pattern (can't be created with dict)"""
        # This pattern can't be created with a dict:
        # x=1,y=10 and x=1,y=20 and x=2,y=20 (but NOT x=2,y=10)
        df = pd.DataFrame({
            "x": [1, 1, 2],
            "y": [10, 20, 20]
        })

        model = {
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#",
            "output": {
                "result": "grep 'result = ' output.txt | cut -d '=' -f2"
            }
        }

        results = fz.fzr(
            str(self.input_file),
            df,
            model,
            calculators=f"sh://bash {self.calc_script}",
            results_dir=str(self.test_path / "results")
        )

        assert len(results) == 3
        results_sorted = results.sort_values(["x", "y"]).reset_index(drop=True)
        assert results_sorted["x"].tolist() == [1, 1, 2]
        assert results_sorted["y"].tolist() == [10, 20, 20]
        assert results_sorted["result"].tolist() == [11, 21, 22]


class TestInputValidation:
    """Test input validation for input_variables"""

    def test_dict_input_still_works(self):
        """Test that dict input still works as before"""
        dict_input = {"x": [1, 2], "y": 3}
        var_combinations = generate_variable_combinations(dict_input)

        assert len(var_combinations) == 2
        assert var_combinations[0] == {"x": 1, "y": 3}
        assert var_combinations[1] == {"x": 2, "y": 3}

    def test_invalid_input_type(self):
        """Test that invalid input type raises error"""
        with pytest.raises(TypeError, match="input_variables must be a dict or pandas DataFrame"):
            generate_variable_combinations([1, 2, 3])

        with pytest.raises(TypeError, match="input_variables must be a dict or pandas DataFrame"):
            generate_variable_combinations("invalid")

        with pytest.raises(TypeError, match="input_variables must be a dict or pandas DataFrame"):
            generate_variable_combinations(42)


if __name__ == "__main__":
    # Run tests
    print("=" * 70)
    print("Testing DataFrame Input Support")
    print("=" * 70)

    if not HAS_PANDAS:
        print("⚠️  pandas not installed, skipping DataFrame tests")
    else:
        test_df = TestDataFrameInput()

        print("\n1. Testing basic DataFrame input...")
        test_df.test_dataframe_basic()
        print("✓ Passed")

        print("\n2. Testing non-factorial combinations...")
        test_df.test_dataframe_non_factorial()
        print("✓ Passed")

        print("\n3. Testing DataFrame vs dict factorial...")
        test_df.test_dataframe_vs_dict_factorial()
        print("✓ Passed")

        print("\n4. Testing single row DataFrame...")
        test_df.test_dataframe_single_row()
        print("✓ Passed")

        print("\n5. Testing mixed data types...")
        test_df.test_dataframe_mixed_types()
        print("✓ Passed")

        print("\n6. Testing repeated values...")
        test_df.test_dataframe_with_repeated_values()
        print("✓ Passed")

    # Test input validation (doesn't require pandas)
    test_validation = TestInputValidation()

    print("\n7. Testing dict input still works...")
    test_validation.test_dict_input_still_works()
    print("✓ Passed")

    print("\n8. Testing invalid input type...")
    test_validation.test_invalid_input_type()
    print("✓ Passed")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
