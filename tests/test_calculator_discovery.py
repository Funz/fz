"""
Tests for calculator discovery and model filtering functionality
"""

import pytest
import json
import tempfile
from pathlib import Path

from fz.core import _find_all_calculators, _calculator_supports_model, _resolve_calculators_arg


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Create isolated environment with no calculators in home directory"""
    # Mock Path.home() to return temp directory to avoid finding real calculators
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    return tmp_path


class TestCalculatorDiscovery:
    """Tests for wildcard calculator discovery"""

    def test_find_all_calculators_empty_directory(self, isolated_env, monkeypatch):
        """Test finding calculators when .fz/calculators/ doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            calculators = _find_all_calculators()
            assert calculators == []

    def test_find_all_calculators_with_uri_spec(self, isolated_env, monkeypatch):
        """Test finding calculators with URI specification"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create calculator with URI
            calc_file = calc_dir / "local.json"
            calc_data = {
                "uri": "sh://bash calc.sh",
                "description": "Local calculator"
            }
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)
            calculators = _find_all_calculators()

            assert len(calculators) == 1
            assert calculators[0] == "sh://bash calc.sh"

    def test_find_all_calculators_with_command_spec(self, isolated_env, monkeypatch):
        """Test finding calculators with command specification"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create calculator with command
            calc_file = calc_dir / "simple.json"
            calc_data = {
                "command": "sh://bash run.sh",
                "description": "Simple calculator"
            }
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)
            calculators = _find_all_calculators()

            assert len(calculators) == 1
            assert calculators[0] == "sh://bash run.sh"

    def test_find_all_calculators_multiple_files(self, isolated_env, monkeypatch):
        """Test finding multiple calculator files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create multiple calculators
            for i, name in enumerate(["calc1", "calc2", "calc3"]):
                calc_file = calc_dir / f"{name}.json"
                calc_data = {
                    "uri": f"sh://bash {name}.sh",
                    "description": f"Calculator {i+1}"
                }
                with open(calc_file, 'w') as f:
                    json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)
            calculators = _find_all_calculators()

            assert len(calculators) == 3
            # Check all calculators are present (order not guaranteed)
            assert "sh://bash calc1.sh" in calculators
            assert "sh://bash calc2.sh" in calculators
            assert "sh://bash calc3.sh" in calculators


class TestCalculatorModelSupport:
    """Tests for checking if calculators support specific models"""

    def test_calculator_supports_model_no_models_field(self):
        """Test calculator with no models field (supports all models)"""
        calc_data = {
            "uri": "sh://",
            "description": "Universal calculator"
        }
        assert _calculator_supports_model(calc_data, "anymodel") == True

    def test_calculator_supports_model_dict_match(self):
        """Test calculator with models dict - model is supported"""
        calc_data = {
            "uri": "sh://",
            "models": {
                "model1": "bash model1.sh",
                "model2": "bash model2.sh"
            }
        }
        assert _calculator_supports_model(calc_data, "model1") == True
        assert _calculator_supports_model(calc_data, "model2") == True

    def test_calculator_supports_model_dict_no_match(self):
        """Test calculator with models dict - model is not supported"""
        calc_data = {
            "uri": "sh://",
            "models": {
                "model1": "bash model1.sh",
                "model2": "bash model2.sh"
            }
        }
        assert _calculator_supports_model(calc_data, "model3") == False

    def test_calculator_supports_model_list_match(self):
        """Test calculator with models list - model is supported"""
        calc_data = {
            "uri": "sh://",
            "models": ["model1", "model2", "model3"]
        }
        assert _calculator_supports_model(calc_data, "model1") == True
        assert _calculator_supports_model(calc_data, "model2") == True

    def test_calculator_supports_model_list_no_match(self):
        """Test calculator with models list - model is not supported"""
        calc_data = {
            "uri": "sh://",
            "models": ["model1", "model2"]
        }
        assert _calculator_supports_model(calc_data, "model3") == False


class TestModelFiltering:
    """Tests for filtering calculators by model"""

    def test_find_calculators_filtered_by_model(self, isolated_env, monkeypatch):
        """Test finding calculators filtered by model name"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create calculator that supports model1
            calc1_file = calc_dir / "calc_model1.json"
            calc1_data = {
                "uri": "sh://",
                "models": {"model1": "bash model1.sh"}
            }
            with open(calc1_file, 'w') as f:
                json.dump(calc1_data, f)

            # Create calculator that supports model2
            calc2_file = calc_dir / "calc_model2.json"
            calc2_data = {
                "uri": "sh://",
                "models": {"model2": "bash model2.sh"}
            }
            with open(calc2_file, 'w') as f:
                json.dump(calc2_data, f)

            # Create calculator that supports all models
            calc3_file = calc_dir / "calc_all.json"
            calc3_data = {
                "uri": "sh://bash universal.sh"
            }
            with open(calc3_file, 'w') as f:
                json.dump(calc3_data, f)

            monkeypatch.chdir(tmpdir)

            # Find calculators for model1
            calculators_model1 = _find_all_calculators(model_name="model1")
            assert len(calculators_model1) == 2  # calc1 and calc3
            # Check that model-specific command is included for calc1
            assert any("model1.sh" in str(c) or "universal.sh" in str(c) for c in calculators_model1)

            # Find calculators for model2
            calculators_model2 = _find_all_calculators(model_name="model2")
            assert len(calculators_model2) == 2  # calc2 and calc3

            # Find calculators for model3 (not explicitly supported)
            calculators_model3 = _find_all_calculators(model_name="model3")
            assert len(calculators_model3) == 1  # Only calc3 (supports all)

    def test_find_calculators_no_model_filter(self, isolated_env, monkeypatch):
        """Test finding all calculators without model filtering"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create calculators with different model support
            for i in range(3):
                calc_file = calc_dir / f"calc{i}.json"
                calc_data = {
                    "uri": f"sh://bash calc{i}.sh"
                }
                with open(calc_file, 'w') as f:
                    json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)

            # Find all calculators without model filter
            calculators = _find_all_calculators(model_name=None)
            assert len(calculators) == 3


class TestResolveCalculatorsArg:
    """Tests for _resolve_calculators_arg with wildcard support"""

    def test_resolve_calculators_none_defaults_to_wildcard(self, isolated_env, monkeypatch):
        """Test that None defaults to wildcard discovery"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create a calculator
            calc_file = calc_dir / "test.json"
            calc_data = {"uri": "sh://bash test.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)

            # None should trigger wildcard discovery
            calculators = _resolve_calculators_arg(None)
            assert len(calculators) == 1
            assert calculators[0] == "sh://bash test.sh"

    def test_resolve_calculators_wildcard_explicit(self, isolated_env, monkeypatch):
        """Test explicit wildcard "*" """
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Create calculators
            for i in range(2):
                calc_file = calc_dir / f"calc{i}.json"
                calc_data = {"uri": f"sh://bash calc{i}.sh"}
                with open(calc_file, 'w') as f:
                    json.dump(calc_data, f)

            monkeypatch.chdir(tmpdir)

            # Explicit wildcard "*"
            calculators = _resolve_calculators_arg("*")
            assert len(calculators) == 2

    def test_resolve_calculators_wildcard_with_model_filter(self, isolated_env, monkeypatch):
        """Test wildcard with model filtering"""
        with tempfile.TemporaryDirectory() as tmpdir:
            calc_dir = Path(tmpdir) / ".fz" / "calculators"
            calc_dir.mkdir(parents=True)

            # Calculator for model1
            calc1_file = calc_dir / "calc1.json"
            calc1_data = {
                "uri": "sh://",
                "models": {"model1": "bash model1.sh"}
            }
            with open(calc1_file, 'w') as f:
                json.dump(calc1_data, f)

            # Calculator for model2
            calc2_file = calc_dir / "calc2.json"
            calc2_data = {
                "uri": "sh://",
                "models": {"model2": "bash model2.sh"}
            }
            with open(calc2_file, 'w') as f:
                json.dump(calc2_data, f)

            monkeypatch.chdir(tmpdir)

            # Wildcard with model1 filter
            calculators = _resolve_calculators_arg("*", model_name="model1")
            assert len(calculators) == 1

            # Wildcard with model2 filter
            calculators = _resolve_calculators_arg("*", model_name="model2")
            assert len(calculators) == 1

    def test_resolve_calculators_fallback_to_default(self, isolated_env, monkeypatch):
        """Test fallback to default sh:// when no calculators found"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .fz/calculators/ directory
            monkeypatch.chdir(tmpdir)

            # Should fallback to default
            calculators = _resolve_calculators_arg(None)
            assert calculators == ["sh://"]

    def test_resolve_calculators_explicit_uri(self):
        """Test that explicit URI is passed through unchanged"""
        calculators = _resolve_calculators_arg("sh://bash myscript.sh")
        assert isinstance(calculators, list)
        assert len(calculators) >= 1
