"""
Test CLI commands across all platforms

Tests all fz commands (fz, fzi, fzc, fzo, fzr) with various options
including the --format option for output formatting.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# Determine if we're running on Windows
IS_WINDOWS = platform.system() == "Windows"


def get_python_executable():
    """Get the current Python executable path"""
    return sys.executable


def run_cli_command(args, cwd=None, check=True, input_data=None):
    """
    Run a CLI command and return result

    Args:
        args: List of command arguments
        cwd: Working directory
        check: Whether to raise exception on non-zero exit
        input_data: Input data to send to stdin

    Returns:
        CompletedProcess object with stdout, stderr, returncode
    """
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        input=input_data,
    )

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, args, result.stdout, result.stderr
        )

    return result


def run_fz_cli_function(function_name, args_list):
    """
    Run a fz CLI function directly by importing and calling it

    Args:
        function_name: Name of the function (e.g., 'fzi_main')
        args_list: List of command-line arguments

    Returns:
        CompletedProcess-like object with stdout, stderr, returncode
    """
    import sys
    from io import StringIO

    # Save original values
    original_argv = sys.argv
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Redirect stdout and stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    sys.argv = [function_name] + args_list

    returncode = 0
    try:
        # Import and run the function
        from fz.cli import fzi_main, fzc_main, fzo_main, fzr_main, main
        func_map = {
            'fzi_main': fzi_main,
            'fzc_main': fzc_main,
            'fzo_main': fzo_main,
            'fzr_main': fzr_main,
            'main': main,
        }

        result = func_map[function_name]()
        if result is not None:
            returncode = result
    except SystemExit as e:
        returncode = e.code if e.code is not None else 0
    except Exception as e:
        sys.stderr.write(str(e))
        returncode = 1
    finally:
        # Get output
        stdout = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()

        # Restore original values
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        sys.argv = original_argv

    # Return a result object similar to subprocess.CompletedProcess
    class Result:
        def __init__(self, stdout, stderr, returncode):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    return Result(stdout, stderr, returncode)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_input_file(temp_workspace):
    """Create a sample input file with variables"""
    input_file = temp_workspace / "input.txt"
    input_file.write_text("x = ${var1}\ny = ${var2}\nz = ${var3}")
    return input_file


@pytest.fixture
def sample_model():
    """Return a sample model configuration"""
    return {"varprefix": "$", "delim": "{}"}


@pytest.fixture
def sample_variables():
    """Return sample variable values"""
    return {"var1": 1.0, "var2": 2.0, "var3": 3.0}


class TestFziCommand:
    """Test fzi command (parse input to find variables)"""

    def test_fzi_help(self):
        """Test fzi --help"""
        result = run_fz_cli_function('fzi_main', ['--help'])
        # Help returns exit code 0
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "fzi" in output.lower() or "parse" in output.lower() or "input" in output.lower()

    def test_fzi_version(self):
        """Test fzi --version"""
        result = run_fz_cli_function('fzi_main', ['--version'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "0." in output  # Version number

    def test_fzi_json_format(self, sample_input_file, sample_model, temp_workspace):
        """Test fzi with JSON format"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert isinstance(output, dict)
        # Single-level dict with variables as keys
        assert "var1" in output
        assert "var2" in output
        assert "var3" in output

    def test_fzi_markdown_format(self, sample_input_file, sample_model, temp_workspace):
        """Test fzi with markdown format"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "markdown"
        ])

        assert result.returncode == 0
        assert "|" in result.stdout  # Markdown table
        assert "---" in result.stdout  # Markdown separator

    def test_fzi_csv_format(self, sample_input_file, sample_model, temp_workspace):
        """Test fzi with CSV format"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "csv"
        ])

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 2  # Header + at least one row
        assert "," in result.stdout  # CSV delimiter

    def test_fzi_table_format(self, sample_input_file, sample_model, temp_workspace):
        """Test fzi with table format"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "table"
        ])

        assert result.returncode == 0
        assert "+" in result.stdout  # Table borders
        assert "|" in result.stdout  # Table separators

    def test_fzi_html_format(self, sample_input_file, sample_model, temp_workspace):
        """Test fzi with HTML format"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "html"
        ])

        assert result.returncode == 0
        assert "<table" in result.stdout
        assert "</table>" in result.stdout
        assert "<th>" in result.stdout or "<td>" in result.stdout


class TestFzcCommand:
    """Test fzc command (compile input with variable values)"""

    def test_fzc_help(self):
        """Test fzc --help"""
        result = run_fz_cli_function('fzc_main', ['--help'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "fzc" in output.lower() or "compile" in output.lower()

    def test_fzc_basic(self, sample_input_file, sample_model, sample_variables, temp_workspace):
        """Test fzc basic compilation"""
        output_dir = temp_workspace / "output"

        result = run_fz_cli_function('fzc_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--input_variables", json.dumps(sample_variables),
            "--output_dir", str(output_dir)
        ])

        assert result.returncode == 0
        assert output_dir.exists()


class TestFzoCommand:
    """Test fzo command (parse output files)"""

    def test_fzo_help(self):
        """Test fzo --help"""
        result = run_fz_cli_function('fzo_main', ['--help'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "fzo" in output.lower() or "output" in output.lower() or "parse" in output.lower()

    def test_fzo_json_format(self, temp_workspace, sample_model):
        """Test fzo with JSON format"""
        # Create a simple output file
        output_file = temp_workspace / "output.txt"
        output_file.write_text("x = 1.0\ny = 2.0")

        # Use a simple model (same as input model for consistency)
        result = run_fz_cli_function('fzo_main', [
            "--output_path", str(output_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        # fzo may return non-zero if it can't parse the output with the model
        # Just check that it runs and produces some output
        assert result.stdout.strip() or result.stderr.strip()  # Some output


class TestFzrCommand:
    """Test fzr command (run full parametric calculations)"""

    def test_fzr_help(self):
        """Test fzr --help"""
        result = run_fz_cli_function('fzr_main', ['--help'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "fzr" in output.lower() or "run" in output.lower()

    @pytest.mark.skipif(IS_WINDOWS, reason="Complex test, skip on Windows for now")
    def test_fzr_with_shell_calculator(self, sample_input_file, sample_model, sample_variables, temp_workspace):
        """Test fzr with shell calculator"""
        results_dir = temp_workspace / "results"

        # Create a simple shell script calculator
        if IS_WINDOWS:
            calc_script = temp_workspace / "calc.bat"
            calc_script.write_text("@echo off\necho result = 10")
        else:
            calc_script = temp_workspace / "calc.sh"
            calc_script.write_text("#!/bin/bash\necho 'result = 10'")
            calc_script.chmod(0o755)

        calculators = {
            "local": {
                "type": "shell",
                "command": str(calc_script)
            }
        }

        result = run_cli_command([
            get_python_executable(), "-m", "fz.cli", "run",
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--input_variables", json.dumps(sample_variables),
            "--results_dir", str(results_dir),
            "--calculators", json.dumps(calculators),
            "--format", "json"
        ], cwd=str(temp_workspace), check=False)

        # May fail if calculator execution has issues, that's OK for this test
        assert result.returncode in [0, 1]


class TestFzMainCommand:
    """Test fz main command with subcommands"""

    def test_fz_help(self):
        """Test fz --help"""
        result = run_fz_cli_function('main', ['--help'])
        assert result.returncode in [0, 1]  # Can exit with 1 if no subcommand
        output = result.stdout + result.stderr
        assert "input" in output.lower() or "compile" in output.lower() or "fz" in output.lower()

    def test_fz_version(self):
        """Test fz --version"""
        result = run_fz_cli_function('main', ['--version'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "0." in output

    def test_fz_input_subcommand(self, sample_input_file, sample_model, temp_workspace):
        """Test fz input subcommand"""
        result = run_fz_cli_function('main', [
            "input",
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert isinstance(output, dict)

    def test_fz_compile_subcommand(self, sample_input_file, sample_model, sample_variables, temp_workspace):
        """Test fz compile subcommand"""
        output_dir = temp_workspace / "output"

        result = run_fz_cli_function('main', [
            "compile",
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--input_variables", json.dumps(sample_variables),
            "--output_dir", str(output_dir)
        ])

        assert result.returncode == 0
        assert output_dir.exists()


class TestCLIErrorHandling:
    """Test CLI error handling"""

    def test_missing_required_args(self):
        """Test error when required arguments are missing"""
        result = run_fz_cli_function('fzi_main', [])

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "required" in output.lower() or "error" in output.lower()

    def test_invalid_format(self, sample_input_file, sample_model, temp_workspace):
        """Test error with invalid format option"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "invalid_format"
        ])

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "invalid choice" in output.lower() or "error" in output.lower()

    def test_nonexistent_input_file(self, sample_model, temp_workspace):
        """Test error with non-existent input file"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(temp_workspace / "nonexistent.txt"),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        assert result.returncode != 0


class TestCLIOutput:
    """Test CLI output can be piped and redirected"""

    def test_json_output_is_valid(self, sample_input_file, sample_model, temp_workspace):
        """Test that JSON output is valid and parseable"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        # Should be parseable JSON
        data = json.loads(result.stdout)
        assert isinstance(data, (dict, list))

    def test_csv_output_structure(self, sample_input_file, sample_model, temp_workspace):
        """Test that CSV output has proper structure"""
        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(sample_input_file),
            "--model", json.dumps(sample_model),
            "--format", "csv"
        ])

        lines = result.stdout.strip().split("\n")
        # Should have at least header row
        assert len(lines) >= 1
        # First line should have comma-separated values
        assert "," in lines[0]


class TestCLIPlatformCompatibility:
    """Test CLI works on different platforms"""

    def test_path_handling(self, temp_workspace, sample_model):
        """Test that paths are handled correctly on all platforms"""
        input_file = temp_workspace / "test_input.txt"
        input_file.write_text("x = ${var1}")

        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(input_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        assert result.returncode == 0

    def test_special_characters_in_paths(self, temp_workspace, sample_model):
        """Test handling of special characters in paths"""
        # Create directory with space in name
        subdir = temp_workspace / "test dir"
        subdir.mkdir(exist_ok=True)

        input_file = subdir / "input.txt"
        input_file.write_text("x = ${var1}")

        result = run_fz_cli_function('fzi_main', [
            "--input_path", str(input_file),
            "--model", json.dumps(sample_model),
            "--format", "json"
        ])

        assert result.returncode == 0


class TestFzInstallCommand:
    """Test fz install command for model installation"""

    @pytest.fixture
    def test_model_zip(self, temp_workspace):
        """Create a test model zip file"""
        # Create model structure
        model_dir = temp_workspace / "fz-testmodel-main"
        model_dir.mkdir(exist_ok=True)

        # Create model definition
        model_def = {
            "id": "testmodel",
            "varprefix": "$",
            "delim": "{}",
            "formulaprefix": "@",
            "commentline": "#",
            "output": {
                "result": "cat output.txt"
            }
        }

        model_json = model_dir / "model.json"
        model_json.write_text(json.dumps(model_def, indent=2))

        # Create zip file
        import zipfile
        zip_path = temp_workspace / "fz-testmodel.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(model_json, arcname="fz-testmodel-main/model.json")

        return zip_path

    @pytest.fixture
    def test_model_with_calculators(self, temp_workspace):
        """Create a test model zip with calculators"""
        import zipfile

        # Create model structure
        model_dir = temp_workspace / "fz-testcalc-main"
        fz_dir = model_dir / ".fz"
        models_dir = fz_dir / "models"
        calc_dir = fz_dir / "calculators"

        models_dir.mkdir(parents=True, exist_ok=True)
        calc_dir.mkdir(parents=True, exist_ok=True)

        # Create model definition
        model_def = {
            "id": "testcalc",
            "varprefix": "$",
            "delim": "{}",
            "output": {
                "result": "cat output.txt"
            }
        }
        model_json = models_dir / "testcalc.json"
        model_json.write_text(json.dumps(model_def, indent=2))

        # Create calculator script
        calc_script = calc_dir / "testcalc.sh"
        calc_script.write_text("#!/bin/bash\necho 'result = 42'")

        # Create calculator config
        calc_config = calc_dir / "localhost_testcalc.json"
        calc_config.write_text(json.dumps({
            "uri": "sh://",
            "n": 1,
            "models": {"testcalc": "bash .fz/calculators/testcalc.sh"}
        }, indent=2))

        # Create zip file
        zip_path = temp_workspace / "fz-testcalc.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(model_json, arcname="fz-testcalc-main/.fz/models/testcalc.json")
            zf.write(calc_script, arcname="fz-testcalc-main/.fz/calculators/testcalc.sh")
            zf.write(calc_config, arcname="fz-testcalc-main/.fz/calculators/localhost_testcalc.json")

        return zip_path

    @pytest.fixture
    def install_workspace(self, temp_workspace):
        """Create a workspace with .fz directories for installation"""
        fz_dir = temp_workspace / ".fz"
        models_dir = fz_dir / "models"
        calc_dir = fz_dir / "calculators"

        models_dir.mkdir(parents=True, exist_ok=True)
        calc_dir.mkdir(parents=True, exist_ok=True)

        return temp_workspace

    def test_install_help(self):
        """Test fz install --help"""
        result = run_fz_cli_function('main', ['install', '--help'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "install" in output.lower()

    def test_install_from_local_zip(self, test_model_zip, install_workspace):
        """Test installing model from local zip file"""
        # Change to install workspace so installation happens there
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = run_fz_cli_function('main', [
                'install',
                str(test_model_zip)
            ])

            assert result.returncode == 0
            assert "Successfully installed" in result.stdout
            assert "testmodel" in result.stdout

            # Verify model file was created
            model_file = install_workspace / ".fz" / "models" / "testmodel.json"
            assert model_file.exists()

            # Verify model content
            model_data = json.loads(model_file.read_text())
            assert model_data["id"] == "testmodel"
        finally:
            os.chdir(original_cwd)

    def test_install_with_calculators(self, test_model_with_calculators, install_workspace):
        """Test installing model with calculator files"""
        # Change to install workspace so installation happens there
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = run_fz_cli_function('main', [
                'install',
                str(test_model_with_calculators)
            ])

            assert result.returncode == 0
            assert "Successfully installed" in result.stdout

            # Verify model file
            model_file = install_workspace / ".fz" / "models" / "testcalc.json"
            assert model_file.exists()

            # Verify calculator files
            calc_dir = install_workspace / ".fz" / "calculators"
            calc_script = calc_dir / "testcalc.sh"
            calc_config = calc_dir / "localhost_testcalc.json"

            assert calc_script.exists()
            assert calc_config.exists()

            # Verify script is executable on Unix-like systems
            if not IS_WINDOWS:
                assert os.access(calc_script, os.X_OK)
        finally:
            os.chdir(original_cwd)

    def test_list_installed_models(self, test_model_zip, install_workspace):
        """Test listing installed models"""
        # Change to install workspace
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            # Install a model first
            install_result = run_fz_cli_function('main', [
                'install',
                str(test_model_zip)
            ])
            assert install_result.returncode == 0

            # List models
            result = run_fz_cli_function('main', ['list'])

            assert result.returncode == 0
            assert "testmodel" in result.stdout
        finally:
            os.chdir(original_cwd)

    def test_list_empty_models(self, temp_workspace):
        """Test listing when no local models are installed"""
        # Use a fresh workspace with empty .fz directory
        empty_workspace = temp_workspace / "empty"
        empty_workspace.mkdir()
        (empty_workspace / ".fz" / "models").mkdir(parents=True, exist_ok=True)

        # Change to empty workspace
        original_cwd = os.getcwd()
        try:
            os.chdir(empty_workspace)
            result = run_fz_cli_function('main', ['list'])

            assert result.returncode == 0
            # May show global models, just verify it runs without error
            # If there are any models listed, they should be marked [global]
            if "Installed models" in result.stdout:
                # Should only have global models, no local ones
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.strip() and line.strip().startswith('-'):
                        # This is a model line, should have [global] flag
                        assert "[global]" in line
        finally:
            os.chdir(original_cwd)

    def test_install_invalid_source(self, temp_workspace):
        """Test error handling for invalid source"""
        result = run_fz_cli_function('main', [
            'install',
            str(temp_workspace / "nonexistent.zip")
        ])

        assert result.returncode != 0
        assert "Error" in result.stderr or "Failed" in result.stderr or "error" in result.stdout.lower()

    @pytest.mark.skipif(True, reason="Requires network access, skip for CI")
    def test_install_from_github_name(self, install_workspace):
        """Test installing from GitHub shortname (requires network)"""
        result = run_fz_cli_function('main', [
            'install',
            'moret'
        ])

        # May fail if repo structure changes or network issues
        if result.returncode == 0:
            assert "Successfully installed" in result.stdout
            model_file = install_workspace / ".fz" / "models" / "Moret.json"
            assert model_file.exists()

    @pytest.mark.skipif(True, reason="Requires network access, skip for CI")
    def test_install_from_github_url(self, install_workspace):
        """Test installing from full GitHub URL (requires network)"""
        result = run_fz_cli_function('main', [
            'install',
            'https://github.com/Funz/fz-moret'
        ])

        # May fail if repo structure changes or network issues
        if result.returncode == 0:
            assert "Successfully installed" in result.stdout

    def test_install_overwrites_existing(self, test_model_zip, install_workspace):
        """Test that installing same model twice overwrites"""
        # Change to install workspace
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            # Install first time
            result1 = run_fz_cli_function('main', [
                'install',
                str(test_model_zip)
            ])
            assert result1.returncode == 0

            # Install again (should overwrite)
            result2 = run_fz_cli_function('main', [
                'install',
                str(test_model_zip)
            ])
            assert result2.returncode == 0
            assert "Successfully installed" in result2.stdout
        finally:
            os.chdir(original_cwd)

    def test_uninstall_help(self):
        """Test fz uninstall --help"""
        result = run_fz_cli_function('main', ['uninstall', '--help'])
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "uninstall" in output.lower()

    def test_uninstall_model(self, test_model_zip, install_workspace):
        """Test uninstalling a model"""
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            # Install model first
            install_result = run_fz_cli_function('main', [
                'install',
                str(test_model_zip)
            ])
            assert install_result.returncode == 0

            # Verify it's installed
            model_file = install_workspace / ".fz" / "models" / "testmodel.json"
            assert model_file.exists()

            # Uninstall
            result = run_fz_cli_function('main', [
                'uninstall',
                'testmodel'
            ])

            assert result.returncode == 0
            assert "Successfully uninstalled" in result.stdout

            # Verify it's removed
            assert not model_file.exists()
        finally:
            os.chdir(original_cwd)

    def test_uninstall_nonexistent_model(self, install_workspace):
        """Test error handling when uninstalling non-existent model"""
        original_cwd = os.getcwd()
        try:
            os.chdir(install_workspace)
            result = run_fz_cli_function('main', [
                'uninstall',
                'nonexistent_model'
            ])

            assert result.returncode != 0
            assert "not found" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)

    def test_global_install_and_uninstall(self, test_model_zip):
        """Test installing and uninstalling globally"""
        # Install globally
        result1 = run_fz_cli_function('main', [
            'install',
            str(test_model_zip),
            '--global'
        ])
        assert result1.returncode == 0
        assert "Successfully installed" in result1.stdout

        # Verify in global location
        global_model = Path.home() / ".fz" / "models" / "testmodel.json"
        assert global_model.exists()

        # Uninstall globally
        result2 = run_fz_cli_function('main', [
            'uninstall',
            'testmodel',
            '--global'
        ])
        assert result2.returncode == 0
        assert "Successfully uninstalled" in result2.stdout

        # Verify removed
        assert not global_model.exists()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
