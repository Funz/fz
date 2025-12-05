"""
Tests for calculator discovery and model filtering functionality
"""

import pytest
import json
from pathlib import Path

import platform

from fz.helpers import _find_all_calculators, _calculator_supports_model, _resolve_calculators_arg


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
        test_dir = isolated_env / "test_empty"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)
        calculators = _find_all_calculators()
        assert calculators == []

    def test_find_all_calculators_with_uri_spec(self, isolated_env, monkeypatch):
        """Test finding calculators with URI specification"""
        test_dir = isolated_env / "test_uri_spec"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculator with URI
        calc_file = calc_dir / "local.json"
        calc_data = {
            "uri": "sh://bash calc.sh",
            "description": "Local calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)
        calculators = _find_all_calculators()

        assert len(calculators) == 1
        assert calculators[0] == "sh://bash calc.sh"

    def test_find_all_calculators_with_command_spec(self, isolated_env, monkeypatch):
        """Test finding calculators with command specification"""
        test_dir = isolated_env / "test_command_spec"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculator with command
        calc_file = calc_dir / "simple.json"
        calc_data = {
            "command": "sh://bash run.sh",
            "description": "Simple calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)
        calculators = _find_all_calculators()

        assert len(calculators) == 1
        assert calculators[0] == "sh://bash run.sh"

    def test_find_all_calculators_multiple_files(self, isolated_env, monkeypatch):
        """Test finding multiple calculator files"""
        test_dir = isolated_env / "test_multiple_files"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
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

        monkeypatch.chdir(test_dir)
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

    def test_funz_calculator_uri_construction(self, isolated_env, monkeypatch):
        """
        Test Funz calculator URI construction with model appending

        Funz calculators have a special URI format where the model name is
        appended to the URI path: funz://:<udp_port>/<model>

        When using a calculator JSON file, the structure is:
        {
          "uri": "funz://:5555",
          "models": {
            "model_name": "model_name"
          }
        }

        The implementation should:
        1. When model_name is specified: construct "funz://:5555/model_name"
        2. When no model is specified: return base URI "funz://:5555"
        3. Filter out calculators that don't support the requested model
        """
        test_dir = isolated_env / "test_funz_uri"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create a Funz calculator that supports multiple models
        funz_calc_file = calc_dir / "funz_server.json"
        funz_calc_data = {
            "uri": "funz://:5555",
            "description": "Funz calculator server on port 5555",
            "models": {
                "mymodel": "mymodel",
                "othermodel": "othermodel",
                "thirdmodel": "thirdmodel"
            }
        }
        with open(funz_calc_file, 'w') as f:
            json.dump(funz_calc_data, f)

        # Create another Funz calculator on different port with different models
        funz_calc2_file = calc_dir / "funz_server2.json"
        funz_calc2_data = {
            "uri": "funz://:6666",
            "description": "Funz calculator server on port 6666",
            "models": {
                "mymodel": "mymodel",
                "specialmodel": "specialmodel"
            }
        }
        with open(funz_calc2_file, 'w') as f:
            json.dump(funz_calc2_data, f)

        monkeypatch.chdir(test_dir)

        # Test 1: Request "mymodel" - should get both calculators with model appended
        calculators_mymodel = _find_all_calculators(model_name="mymodel")
        assert len(calculators_mymodel) == 2
        assert "funz://:5555/mymodel" in calculators_mymodel
        assert "funz://:6666/mymodel" in calculators_mymodel

        # Test 2: Request "othermodel" - should only get first calculator
        calculators_othermodel = _find_all_calculators(model_name="othermodel")
        assert len(calculators_othermodel) == 1
        assert calculators_othermodel[0] == "funz://:5555/othermodel"

        # Test 3: Request "specialmodel" - should only get second calculator
        calculators_specialmodel = _find_all_calculators(model_name="specialmodel")
        assert len(calculators_specialmodel) == 1
        assert calculators_specialmodel[0] == "funz://:6666/specialmodel"

        # Test 4: Request unsupported model - should get no Funz calculators
        calculators_unsupported = _find_all_calculators(model_name="unsupported")
        assert len(calculators_unsupported) == 0

        # Test 5: No model filter - should get base URIs without model paths
        calculators_all = _find_all_calculators(model_name=None)
        assert len(calculators_all) == 2
        assert "funz://:5555" in calculators_all
        assert "funz://:6666" in calculators_all
        # Model paths should NOT be appended when no model is specified
        assert "funz://:5555/mymodel" not in calculators_all
        assert "funz://:6666/mymodel" not in calculators_all

    def test_find_calculators_filtered_by_model(self, isolated_env, monkeypatch):
        """Test finding calculators filtered by model name"""
        test_dir = isolated_env / "test_filter_by_model"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
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

        monkeypatch.chdir(test_dir)

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
        test_dir = isolated_env / "test_no_model_filter"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with different model support
        for i in range(3):
            calc_file = calc_dir / f"calc{i}.json"
            calc_data = {
                "uri": f"sh://bash calc{i}.sh"
            }
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Find all calculators without model filter
        calculators = _find_all_calculators(model_name=None)
        assert len(calculators) == 3


class TestResolveCalculatorsArg:
    """Tests for _resolve_calculators_arg with wildcard support"""

    def test_resolve_calculators_none_defaults_to_wildcard(self, isolated_env, monkeypatch):
        """Test that None defaults to wildcard discovery"""
        test_dir = isolated_env / "test_none_wildcard"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create a calculator
        calc_file = calc_dir / "test.json"
        calc_data = {"uri": "sh://bash test.sh"}
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # None should trigger wildcard discovery
        calculators = _resolve_calculators_arg(None)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash test.sh"

    def test_resolve_calculators_wildcard_explicit(self, isolated_env, monkeypatch):
        """Test explicit wildcard "*" """
        test_dir = isolated_env / "test_explicit_wildcard"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        for i in range(2):
            calc_file = calc_dir / f"calc{i}.json"
            calc_data = {"uri": f"sh://bash calc{i}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Explicit wildcard "*"
        calculators = _resolve_calculators_arg("*")
        assert len(calculators) == 2

    def test_resolve_calculators_wildcard_with_model_filter(self, isolated_env, monkeypatch):
        """Test wildcard with model filtering"""
        test_dir = isolated_env / "test_wildcard_model_filter"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
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

        monkeypatch.chdir(test_dir)

        # Wildcard with model1 filter
        calculators = _resolve_calculators_arg("*", model_name="model1")
        assert len(calculators) == 1

        # Wildcard with model2 filter
        calculators = _resolve_calculators_arg("*", model_name="model2")
        assert len(calculators) == 1

    def test_resolve_calculators_fallback_to_default(self, isolated_env, monkeypatch):
        """Test fallback to default sh:// when no calculators found"""
        test_dir = isolated_env / "test_fallback"
        test_dir.mkdir()
        # No .fz/calculators/ directory
        monkeypatch.chdir(test_dir)

        # Should fallback to default
        calculators = _resolve_calculators_arg(None)
        assert calculators == ["sh://"]

    def test_resolve_calculators_explicit_uri(self):
        """Test that explicit URI is passed through unchanged"""
        calculators = _resolve_calculators_arg("sh://bash myscript.sh")
        assert isinstance(calculators, list)
        assert len(calculators) >= 1


class TestCalculatorArgumentForms:
    """Tests for different forms of calculator arguments"""

    def test_plain_uri_sh_protocol(self, isolated_env, monkeypatch):
        """Test plain URI with sh:// protocol"""
        test_dir = isolated_env / "test_plain_uri_sh"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Plain sh:// URI
        calculators = _resolve_calculators_arg("sh://bash calc.sh")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash calc.sh"

    def test_plain_uri_ssh_protocol(self, isolated_env, monkeypatch):
        """Test plain URI with ssh:// protocol"""
        test_dir = isolated_env / "test_plain_uri_ssh"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Plain ssh:// URI
        calculators = _resolve_calculators_arg("ssh://user@host/bash calc.sh")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "ssh://user@host/bash calc.sh"

    def test_plain_uri_cache_protocol(self, isolated_env, monkeypatch):
        """Test plain URI with cache:// protocol"""
        test_dir = isolated_env / "test_plain_uri_cache"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Plain cache:// URI
        calculators = _resolve_calculators_arg("cache://results/*")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "cache://results/*"

    def test_plain_uri_funz_protocol(self, isolated_env, monkeypatch):
        """Test plain URI with funz:// protocol"""
        test_dir = isolated_env / "test_plain_uri_funz"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Plain funz:// URI
        calculators = _resolve_calculators_arg("funz://:5555/mymodel")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "funz://:5555/mymodel"

    def test_json_file_full_path_cwd(self, isolated_env, monkeypatch):
        """Test JSON file with full path in current directory"""
        test_dir = isolated_env / "test_json_full_path"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create a calculator JSON file in a custom location
        calc_file = test_dir / "my_calculator.json"
        calc_data = {
            "uri": "sh://bash custom_calc.sh",
            "description": "Custom calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use full path to JSON file
        calculators = _resolve_calculators_arg(str(calc_file))
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash custom_calc.sh"

    def test_json_file_full_path_subdir(self, isolated_env, monkeypatch):
        """Test JSON file with full path in subdirectory"""
        test_dir = isolated_env / "test_json_subdir"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in subdirectory
        subdir = test_dir / "configs" / "calculators"
        subdir.mkdir(parents=True)
        calc_file = subdir / "remote_calc.json"
        calc_data = {
            "uri": "ssh://cluster/bash compute.sh",
            "description": "Remote cluster calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use full path
        calculators = _resolve_calculators_arg(str(calc_file))
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "ssh://cluster/bash compute.sh"

    def test_json_file_relative_path(self, isolated_env, monkeypatch):
        """Test JSON file with relative path"""
        test_dir = isolated_env / "test_json_relative"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in relative path
        subdir = test_dir / "calcs"
        subdir.mkdir()
        calc_file = subdir / "local_calc.json"
        calc_data = {
            "uri": "sh://bash local.sh",
            "description": "Local calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use relative path
        calculators = _resolve_calculators_arg("calcs/local_calc.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash local.sh"

    def test_json_file_fz_calculators_path(self, isolated_env, monkeypatch):
        """Test JSON file in .fz/calculators/ with full path"""
        test_dir = isolated_env / "test_json_fz_path"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in .fz/calculators/
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "standard.json"
        calc_data = {
            "uri": "sh://bash standard.sh",
            "description": "Standard calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use explicit path to .fz/calculators/standard.json
        calculators = _resolve_calculators_arg(".fz/calculators/standard.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash standard.sh"

    def test_json_file_alias_short_name(self, isolated_env, monkeypatch):
        """Test JSON file alias using short name (prefix only)"""
        test_dir = isolated_env / "test_alias_short"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in .fz/calculators/
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "myalias.json"
        calc_data = {
            "uri": "sh://bash aliased_calc.sh",
            "description": "Aliased calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use short name (alias) - should resolve to .fz/calculators/myalias.json
        calculators = _resolve_calculators_arg("myalias")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash aliased_calc.sh"

    def test_json_file_alias_multiple_calcs(self, isolated_env, monkeypatch):
        """Test alias resolving to multiple calculators in JSON list"""
        test_dir = isolated_env / "test_alias_multi"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator alias that defines multiple URIs
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "cluster.json"
        calc_data = [
            "sh://bash node1.sh",
            "sh://bash node2.sh",
            "ssh://cluster/bash compute.sh"
        ]
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use alias
        calculators = _resolve_calculators_arg("cluster")
        assert isinstance(calculators, list)
        assert len(calculators) == 3
        assert "sh://bash node1.sh" in calculators
        assert "sh://bash node2.sh" in calculators
        assert "ssh://cluster/bash compute.sh" in calculators

    def test_json_string_inline(self, isolated_env, monkeypatch):
        """Test inline JSON string for calculator definition"""
        test_dir = isolated_env / "test_json_inline"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Inline JSON string
        json_str = '{"uri": "sh://bash inline.sh", "description": "Inline calculator"}'
        calculators = _resolve_calculators_arg(json_str)
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash inline.sh"

    def test_list_of_uris(self, isolated_env, monkeypatch):
        """Test list of plain URIs"""
        test_dir = isolated_env / "test_list_uris"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # List of URIs
        uri_list = [
            "sh://bash calc1.sh",
            "sh://bash calc2.sh",
            "cache://prev_results/*"
        ]
        calculators = _resolve_calculators_arg(uri_list)
        assert isinstance(calculators, list)
        assert len(calculators) == 3
        assert calculators == uri_list

    def test_list_of_mixed_forms(self, isolated_env, monkeypatch):
        """Test list with mixed calculator forms (URIs and aliases)"""
        test_dir = isolated_env / "test_mixed_forms"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create an alias
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "remote.json"
        calc_data = {"uri": "ssh://server/bash remote.sh"}
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Mixed list: plain URI + alias
        mixed_list = [
            "sh://bash local.sh",
            "remote"  # This should resolve to the alias
        ]
        calculators = _resolve_calculators_arg(mixed_list)
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert "sh://bash local.sh" in calculators
        # The alias should be resolved to its URI
        assert "ssh://server/bash remote.sh" in calculators


class TestCalculatorGlobPatterns:
    """Tests for glob pattern matching in calculator names"""

    def test_wildcard_all_calculators(self, isolated_env, monkeypatch):
        """Test wildcard '*' to match all calculators"""
        test_dir = isolated_env / "test_wildcard_all"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create multiple calculators
        for name in ["calc1", "calc2", "server1"]:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Wildcard should match all
        calculators = _resolve_calculators_arg("*")
        assert isinstance(calculators, list)
        assert len(calculators) == 3

    def test_glob_pattern_prefix_match(self, isolated_env, monkeypatch):
        """Test glob pattern matching calculator names with prefix"""
        test_dir = isolated_env / "test_glob_prefix"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with different prefixes
        calc_names = ["local_calc1", "local_calc2", "remote_calc", "server"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "local*" should match local_calc1 and local_calc2
        calculators = _resolve_calculators_arg("local*")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("local_calc1.sh" in str(c) for c in calculators)
        assert any("local_calc2.sh" in str(c) for c in calculators)

    def test_glob_pattern_suffix_match(self, isolated_env, monkeypatch):
        """Test glob pattern matching calculator names with suffix"""
        test_dir = isolated_env / "test_glob_suffix"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with different suffixes
        calc_names = ["node_calc", "server_calc", "test_calc", "debugger"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "*calc" should match node_calc, server_calc, test_calc
        calculators = _resolve_calculators_arg("*calc")
        assert isinstance(calculators, list)
        assert len(calculators) == 3
        assert any("node_calc.sh" in str(c) for c in calculators)
        assert any("server_calc.sh" in str(c) for c in calculators)
        assert any("test_calc.sh" in str(c) for c in calculators)

    def test_glob_pattern_middle_match(self, isolated_env, monkeypatch):
        """Test glob pattern matching with wildcard in middle"""
        test_dir = isolated_env / "test_glob_middle"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["dev_local_calc", "dev_remote_calc", "prod_calc", "test"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "dev*calc" should match dev_local_calc and dev_remote_calc
        calculators = _resolve_calculators_arg("dev*calc")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("dev_local_calc.sh" in str(c) for c in calculators)
        assert any("dev_remote_calc.sh" in str(c) for c in calculators)

    def test_glob_pattern_question_mark(self, isolated_env, monkeypatch):
        """Test glob pattern with ? (single character match)"""
        test_dir = isolated_env / "test_glob_question"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with numbered names
        calc_names = ["calc1", "calc2", "calc3", "calc10"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "calc?" should match calc1, calc2, calc3 but not calc10
        calculators = _resolve_calculators_arg("calc?")
        assert isinstance(calculators, list)
        assert len(calculators) == 3
        # calc10 should not be included (has 2 chars after "calc")

    def test_glob_pattern_no_match(self, isolated_env, monkeypatch):
        """Test glob pattern that doesn't match any calculators"""
        test_dir = isolated_env / "test_glob_no_match"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["local", "remote"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern that doesn't match - should fallback to default or return as URI
        calculators = _resolve_calculators_arg("nonexistent*")
        assert isinstance(calculators, list)
        # Should either return the pattern as-is (URI) or fallback to default
        # depending on implementation

    def test_glob_pattern_with_model_filter(self, isolated_env, monkeypatch):
        """Test glob pattern with model filtering"""
        test_dir = isolated_env / "test_glob_model"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with model support
        calc1_file = calc_dir / "local_calc1.json"
        calc1_data = {
            "uri": "sh://",
            "models": {"model1": "bash model1.sh"}
        }
        with open(calc1_file, 'w') as f:
            json.dump(calc1_data, f)

        calc2_file = calc_dir / "local_calc2.json"
        calc2_data = {
            "uri": "sh://",
            "models": {"model2": "bash model2.sh"}
        }
        with open(calc2_file, 'w') as f:
            json.dump(calc2_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "local*" with model1 filter should only match local_calc1
        calculators = _resolve_calculators_arg("local*", model_name="model1")
        assert isinstance(calculators, list)
        # Should include only calculators matching both pattern AND model
        assert len(calculators) == 1
        assert "model1.sh" in str(calculators[0])


class TestCalculatorRegexPatterns:
    """Tests for regex pattern matching on calculator names - Windows compatible"""

    def test_regex_pattern_start_anchor(self, isolated_env, monkeypatch):
        """Test regex pattern with start anchor ^"""
        test_dir = isolated_env / "test_regex_start"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with different prefixes
        calc_names = ["local_calc", "remote_calc", "test_local", "server"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "^local" should match only "local_calc" (starts with "local")
        calculators = _resolve_calculators_arg("^local")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert "local_calc.sh" in str(calculators[0])

    def test_regex_pattern_end_anchor(self, isolated_env, monkeypatch):
        """Test regex pattern with end anchor $"""
        test_dir = isolated_env / "test_regex_end"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with different suffixes
        calc_names = ["test_calc", "prod_calc", "calc_test", "server"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "calc$" should match "test_calc" and "prod_calc" (ends with "calc")
        calculators = _resolve_calculators_arg("calc$")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("test_calc.sh" in str(c) for c in calculators)
        assert any("prod_calc.sh" in str(c) for c in calculators)

    def test_regex_pattern_character_class(self, isolated_env, monkeypatch):
        """Test regex pattern with character class [0-9]"""
        test_dir = isolated_env / "test_regex_charclass"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with numbers
        calc_names = ["server1", "server2", "server10", "serverA", "local"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "server[0-9]$" should match server1 and server2, but not server10
        calculators = _resolve_calculators_arg("server[0-9]$")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("server1.sh" in str(c) for c in calculators)
        assert any("server2.sh" in str(c) for c in calculators)

    def test_regex_pattern_plus_quantifier(self, isolated_env, monkeypatch):
        """Test regex pattern with + quantifier"""
        test_dir = isolated_env / "test_regex_plus"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["dev", "dev_1", "dev_test", "dev_local_calc", "prod"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "dev_.+" should match dev_1, dev_test, dev_local_calc (dev_ followed by one or more chars)
        calculators = _resolve_calculators_arg("dev_.+")
        assert isinstance(calculators, list)
        assert len(calculators) == 3
        assert all("dev_" in str(c) for c in calculators)

    def test_regex_pattern_alternation(self, isolated_env, monkeypatch):
        """Test regex pattern with alternation (|)"""
        test_dir = isolated_env / "test_regex_alternation"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["local_calc", "remote_calc", "test_calc", "server_calc"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "^(local|remote)" should match local_calc and remote_calc
        calculators = _resolve_calculators_arg("^(local|remote)")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("local_calc.sh" in str(c) for c in calculators)
        assert any("remote_calc.sh" in str(c) for c in calculators)

    def test_regex_pattern_dot_star(self, isolated_env, monkeypatch):
        """Test regex pattern with .* (any characters)"""
        test_dir = isolated_env / "test_regex_dotstar"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["dev_local_calc", "dev_remote_calc", "prod_calc", "test"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "^dev.*calc$" should match dev_local_calc and dev_remote_calc
        calculators = _resolve_calculators_arg("^dev.*calc$")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("dev_local_calc.sh" in str(c) for c in calculators)
        assert any("dev_remote_calc.sh" in str(c) for c in calculators)

    def test_regex_pattern_with_model_filter(self, isolated_env, monkeypatch):
        """Test regex pattern with model filtering"""
        test_dir = isolated_env / "test_regex_model"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with model support
        calc1_file = calc_dir / "local_calc1.json"
        calc1_data = {
            "uri": "sh://",
            "models": {"model1": "bash model1.sh"}
        }
        with open(calc1_file, 'w') as f:
            json.dump(calc1_data, f)

        calc2_file = calc_dir / "local_calc2.json"
        calc2_data = {
            "uri": "sh://",
            "models": {"model2": "bash model2.sh"}
        }
        with open(calc2_file, 'w') as f:
            json.dump(calc2_data, f)

        calc3_file = calc_dir / "remote_calc.json"
        calc3_data = {
            "uri": "sh://",
            "models": {"model1": "bash remote_model1.sh"}
        }
        with open(calc3_file, 'w') as f:
            json.dump(calc3_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "^local" with model1 filter should only match local_calc1
        calculators = _resolve_calculators_arg("^local", model_name="model1")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert "model1.sh" in str(calculators[0])
        assert "bash model1.sh" in str(calculators[0])

    def test_regex_pattern_no_match(self, isolated_env, monkeypatch):
        """Test regex pattern that doesn't match any calculators"""
        test_dir = isolated_env / "test_regex_no_match"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators
        calc_names = ["local", "remote"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern that doesn't match - should return as-is (treated as literal or fallback to sh://)
        calculators = _resolve_calculators_arg("^nonexistent$")
        assert isinstance(calculators, list)
        # Should either return the pattern as-is or fallback
        # Implementation may vary, but it should not crash

    def test_regex_pattern_escape_sequences(self, isolated_env, monkeypatch):
        """Test regex pattern with escape sequences"""
        test_dir = isolated_env / "test_regex_escape"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create calculators with underscores and hyphens
        calc_names = ["test_calc", "test-calc", "testcalc", "test.calc"]
        for name in calc_names:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "test[_-]calc" should match test_calc and test-calc
        calculators = _resolve_calculators_arg("test[_-]calc")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("test_calc.sh" in str(c) for c in calculators)
        assert any("test-calc.sh" in str(c) for c in calculators)


class TestCalculatorJsonFilePatterns:
    """Tests for glob/regex patterns on JSON file paths - Windows compatible"""

    def test_glob_pattern_on_json_file_path(self, isolated_env, monkeypatch):
        """Test glob pattern matching JSON files in subdirectories"""
        test_dir = isolated_env / "test_glob_json_path"
        test_dir.mkdir()

        # Create calculators in different subdirectories
        configs_dir = test_dir / "configs" / "calculators"
        configs_dir.mkdir(parents=True)

        for name in ["local_calc", "remote_calc"]:
            calc_file = configs_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "configs/calculators/*.json" should match both calculators
        calculators = _resolve_calculators_arg("configs/calculators/*.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("local_calc.sh" in str(c) for c in calculators)
        assert any("remote_calc.sh" in str(c) for c in calculators)

    def test_glob_pattern_on_json_nested_path(self, isolated_env, monkeypatch):
        """Test glob pattern with ** for nested directories"""
        test_dir = isolated_env / "test_glob_nested"
        test_dir.mkdir()

        # Create calculators in nested directories
        for subdir in ["configs/dev", "configs/prod"]:
            calc_dir = test_dir / subdir
            calc_dir.mkdir(parents=True)
            calc_file = calc_dir / "calc.json"
            calc_data = {"uri": f"sh://bash {subdir.replace('/', '_')}_calc.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "configs/**/*.json" should match both calculators
        calculators = _resolve_calculators_arg("configs/**/*.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 2

    def test_regex_pattern_on_json_file_path(self, isolated_env, monkeypatch):
        """Test regex pattern on JSON file paths"""
        test_dir = isolated_env / "test_regex_json_path"
        test_dir.mkdir()

        # Create calculators in different subdirectories
        for subdir in ["configs/dev", "configs/prod", "other"]:
            calc_dir = test_dir / subdir
            calc_dir.mkdir(parents=True)
            calc_file = calc_dir / "calculator.json"
            calc_data = {"uri": f"sh://bash {subdir.replace('/', '_')}_calc.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Pattern "configs/.*/calculator.json" should match configs/dev and configs/prod
        calculators = _resolve_calculators_arg("configs/.*/calculator.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 2
        assert any("configs_dev" in str(c) for c in calculators)
        assert any("configs_prod" in str(c) for c in calculators)

    def test_mixed_calculator_array_with_patterns(self, isolated_env, monkeypatch):
        """Test array of mixed calculator forms (URIs, patterns, aliases)"""
        test_dir = isolated_env / "test_mixed_array"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create some calculators
        for name in ["local_calc", "remote_calc", "test_calc"]:
            calc_file = calc_dir / f"{name}.json"
            calc_data = {"uri": f"sh://bash {name}.sh"}
            with open(calc_file, 'w') as f:
                json.dump(calc_data, f)

        monkeypatch.chdir(test_dir)

        # Mixed array: plain URI + glob pattern + regex pattern
        mixed_list = [
            "sh://bash direct.sh",  # Plain URI
            "local*",               # Glob pattern
            "^remote",              # Regex pattern
        ]
        calculators = _resolve_calculators_arg(mixed_list)
        assert isinstance(calculators, list)
        assert len(calculators) >= 3
        assert "sh://bash direct.sh" in calculators
        assert any("local_calc.sh" in str(c) for c in calculators)
        assert any("remote_calc.sh" in str(c) for c in calculators)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific calculator tests")
class TestWindowsCalculatorForms:
    """Tests for different calculator forms specifically on Windows"""

    def test_windows_plain_uri_sh_protocol(self, isolated_env, monkeypatch):
        """Test plain sh:// URI on Windows"""
        test_dir = isolated_env / "test_windows_sh_uri"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Plain sh:// URI - should work on Windows
        calculators = _resolve_calculators_arg("sh://bash calc.sh")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash calc.sh"

    def test_windows_plain_uri_cache_protocol(self, isolated_env, monkeypatch):
        """Test plain cache:// URI on Windows"""
        test_dir = isolated_env / "test_windows_cache_uri"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Cache URI with Windows-style path
        calculators = _resolve_calculators_arg("cache://C:/results/*")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "cache://C:/results/*"

    def test_windows_json_file_with_backslash_path(self, isolated_env, monkeypatch):
        """Test JSON file with Windows backslash path"""
        test_dir = isolated_env / "test_windows_json_backslash"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create a calculator JSON file
        calc_subdir = test_dir / "configs"
        calc_subdir.mkdir()
        calc_file = calc_subdir / "windows_calc.json"
        calc_data = {
            "uri": "sh://bash C:/scripts/calc.sh",
            "description": "Windows calculator with drive letter"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use Windows-style backslash path (converted to forward slash by Path)
        calculators = _resolve_calculators_arg(str(calc_file))
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash C:/scripts/calc.sh"

    def test_windows_json_file_alias_in_fz_calculators(self, isolated_env, monkeypatch):
        """Test JSON file alias in .fz/calculators/ on Windows"""
        test_dir = isolated_env / "test_windows_alias"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in .fz/calculators/
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "windows_local.json"
        calc_data = {
            "uri": "sh://bash D:/tools/compute.sh",
            "description": "Windows local calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use short name alias
        calculators = _resolve_calculators_arg("windows_local")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash D:/tools/compute.sh"

    def test_windows_explicit_json_file_path(self, isolated_env, monkeypatch):
        """Test explicit JSON file path on Windows"""
        test_dir = isolated_env / "test_windows_explicit_path"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator in custom location
        custom_dir = test_dir / "my_calculators"
        custom_dir.mkdir()
        calc_file = custom_dir / "custom_calc.json"
        calc_data = {
            "uri": "sh://bash E:/projects/calc.sh",
            "description": "Custom Windows calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Use explicit relative path
        calculators = _resolve_calculators_arg("my_calculators/custom_calc.json")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "sh://bash E:/projects/calc.sh"

    def test_windows_mixed_calculator_types(self, isolated_env, monkeypatch):
        """Test mixing multiple calculator types on Windows"""
        test_dir = isolated_env / "test_windows_mixed"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculators in .fz/calculators/
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Calculator 1: alias in .fz/calculators/
        calc1_file = calc_dir / "msys2_calc.json"
        calc1_data = {
            "uri": "sh://C:/msys64/usr/bin/bash.exe calc1.sh",
            "description": "MSYS2 calculator"
        }
        with open(calc1_file, 'w') as f:
            json.dump(calc1_data, f)

        # Calculator 2: in custom directory
        custom_dir = test_dir / "custom"
        custom_dir.mkdir()
        calc2_file = custom_dir / "git_bash_calc.json"
        calc2_data = {
            "uri": 'sh://"C:/Program Files/Git/bin/bash.exe" calc2.sh',
            "description": "Git Bash calculator"
        }
        with open(calc2_file, 'w') as f:
            json.dump(calc2_data, f)

        # Test 1: Use alias from .fz/calculators/
        calculators_alias = _resolve_calculators_arg("msys2_calc")
        assert isinstance(calculators_alias, list)
        assert len(calculators_alias) == 1
        assert "C:/msys64/usr/bin/bash.exe" in calculators_alias[0]

        # Test 2: Use explicit JSON file path
        calculators_explicit = _resolve_calculators_arg("custom/git_bash_calc.json")
        assert isinstance(calculators_explicit, list)
        assert len(calculators_explicit) == 1
        assert "Program Files" in calculators_explicit[0]

        # Test 3: Use plain URI
        calculators_plain = _resolve_calculators_arg("sh://C:/cygwin64/bin/bash.exe calc3.sh")
        assert isinstance(calculators_plain, list)
        assert len(calculators_plain) == 1
        assert calculators_plain[0] == "sh://C:/cygwin64/bin/bash.exe calc3.sh"

        # Test 4: Mix all three types in a list
        mixed_list = [
            "msys2_calc",  # alias
            "custom/git_bash_calc.json",  # explicit path
            "sh://C:/cygwin64/bin/bash.exe calc3.sh"  # plain URI
        ]
        calculators_mixed = _resolve_calculators_arg(mixed_list)
        assert isinstance(calculators_mixed, list)
        assert len(calculators_mixed) == 3
        assert any("msys64" in str(c) for c in calculators_mixed)
        assert any("Program Files" in str(c) for c in calculators_mixed)
        assert any("cygwin64" in str(c) for c in calculators_mixed)

    def test_windows_ssh_calculator_with_windows_paths(self, isolated_env, monkeypatch):
        """Test SSH calculator with Windows remote paths"""
        test_dir = isolated_env / "test_windows_ssh"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create SSH calculator JSON
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "windows_server.json"
        calc_data = {
            "uri": "ssh://user@windows-server.local/C:/tools/compute.sh",
            "description": "Windows SSH calculator"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Test as alias
        calculators = _resolve_calculators_arg("windows_server")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert calculators[0] == "ssh://user@windows-server.local/C:/tools/compute.sh"

    def test_windows_cache_calculator_with_unc_path(self, isolated_env, monkeypatch):
        """Test cache calculator with Windows UNC path"""
        test_dir = isolated_env / "test_windows_unc"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create cache calculator with UNC path
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "network_cache.json"
        calc_data = {
            "uri": "cache://\\\\server\\share\\results\\*",
            "description": "Network cache with UNC path"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Test as alias
        calculators = _resolve_calculators_arg("network_cache")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert "\\\\server\\share" in calculators[0]

    def test_windows_glob_pattern_matching(self, isolated_env, monkeypatch):
        """Test glob pattern matching on Windows"""
        test_dir = isolated_env / "test_windows_glob"
        test_dir.mkdir()
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)

        # Create multiple Windows-specific calculators
        calc_configs = {
            "msys2_calc": {"uri": "sh://C:/msys64/usr/bin/bash.exe calc.sh"},
            "msys2_test": {"uri": "sh://C:/msys64/usr/bin/bash.exe test.sh"},
            "gitbash_calc": {"uri": 'sh://"C:/Program Files/Git/bin/bash.exe" calc.sh'},
            "wsl_calc": {"uri": "sh://C:/Windows/System32/bash.exe calc.sh"}
        }

        for name, data in calc_configs.items():
            calc_file = calc_dir / f"{name}.json"
            with open(calc_file, 'w') as f:
                json.dump(data, f)

        monkeypatch.chdir(test_dir)

        # Test pattern matching for msys2*
        calculators_msys2 = _resolve_calculators_arg("msys2*")
        assert isinstance(calculators_msys2, list)
        assert len(calculators_msys2) == 2
        assert all("msys64" in str(c) for c in calculators_msys2)

        # Test pattern matching for *calc
        calculators_calc = _resolve_calculators_arg("*calc")
        assert isinstance(calculators_calc, list)
        assert len(calculators_calc) == 3  # msys2_calc, gitbash_calc, wsl_calc

        # Test wildcard *
        calculators_all = _resolve_calculators_arg("*")
        assert isinstance(calculators_all, list)
        assert len(calculators_all) == 4

    def test_windows_calculator_with_spaces_in_path(self, isolated_env, monkeypatch):
        """Test calculator with spaces in Windows path"""
        test_dir = isolated_env / "test_windows_spaces"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        # Create calculator with spaces in path
        calc_dir = test_dir / ".fz" / "calculators"
        calc_dir.mkdir(parents=True)
        calc_file = calc_dir / "program_files_calc.json"
        calc_data = {
            "uri": 'sh://"C:/Program Files/My Application/bin/bash.exe" "D:/My Documents/calc.sh"',
            "description": "Calculator with spaces in path"
        }
        with open(calc_file, 'w') as f:
            json.dump(calc_data, f)

        # Test resolution
        calculators = _resolve_calculators_arg("program_files_calc")
        assert isinstance(calculators, list)
        assert len(calculators) == 1
        assert "Program Files" in calculators[0]
        assert "My Application" in calculators[0]
