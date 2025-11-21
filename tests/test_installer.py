"""
Tests for the installer module to verify recursive .fz subdirectory copying
"""

import os
import json
import tempfile
import zipfile
from pathlib import Path
import pytest

from fz.installer import (
    install_model,
    extract_model_files,
    uninstall_model,
    list_installed_models
)


def create_test_plugin_zip(zip_path: Path, plugin_name: str = "testmodel"):
    """
    Create a test plugin zip with nested .fz directory structure

    Structure:
    fz-testmodel-main/
      .fz/
        models/
          testmodel.json
        calculators/
          calc.sh
          scripts/
            helper.sh
            utils/
              common.sh
        algorithms/
          algo.py
          data/
            config.json
    """
    with zipfile.ZipFile(zip_path, 'w') as zf:
        # Create model definition
        model_def = {
            "id": plugin_name,
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "output": {
                "result": "grep 'result' output.txt"
            }
        }

        # Add model JSON
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/models/{plugin_name}.json",
            json.dumps(model_def, indent=2)
        )

        # Add calculator files with nested structure
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/calculators/calc.sh",
            "#!/bin/bash\necho 'Calculator script'\n"
        )
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/calculators/scripts/helper.sh",
            "#!/bin/bash\necho 'Helper script'\n"
        )
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/calculators/scripts/utils/common.sh",
            "#!/bin/bash\necho 'Common utilities'\n"
        )

        # Add algorithm files with nested structure
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/algorithms/algo.py",
            "# Algorithm implementation\nclass TestAlgorithm:\n    pass\n"
        )
        zf.writestr(
            f"fz-{plugin_name}-main/.fz/algorithms/data/config.json",
            json.dumps({"param": "value"})
        )

        # Add a README for completeness
        zf.writestr(
            f"fz-{plugin_name}-main/README.md",
            f"# Test Plugin {plugin_name}\n"
        )


def test_install_model_with_nested_directories():
    """Test that install_model recursively copies all .fz subdirectories"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test plugin zip
        zip_path = tmpdir / "fz-testmodel.zip"
        create_test_plugin_zip(zip_path, "testmodel")

        # Create a fake project directory
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        # Change to project directory and install
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Install the model (local installation)
            result = install_model(str(zip_path), global_install=False)

            # Verify basic installation
            assert result['model_name'] == 'testmodel'
            assert Path(result['install_path']).exists()

            # Verify model JSON was installed
            model_json = project_dir / '.fz' / 'models' / 'testmodel.json'
            assert model_json.exists()

            # Verify calculators directory and nested files
            calculators_dir = project_dir / '.fz' / 'calculators'
            assert calculators_dir.exists()
            assert (calculators_dir / 'calc.sh').exists()
            assert (calculators_dir / 'scripts' / 'helper.sh').exists()
            assert (calculators_dir / 'scripts' / 'utils' / 'common.sh').exists()

            # Verify algorithms directory and nested files
            algorithms_dir = project_dir / '.fz' / 'algorithms'
            assert algorithms_dir.exists()
            assert (algorithms_dir / 'algo.py').exists()
            assert (algorithms_dir / 'data' / 'config.json').exists()

            # Verify shell scripts are executable
            calc_sh = calculators_dir / 'calc.sh'
            assert os.access(calc_sh, os.X_OK), "calc.sh should be executable"

            helper_sh = calculators_dir / 'scripts' / 'helper.sh'
            assert os.access(helper_sh, os.X_OK), "helper.sh should be executable"

            common_sh = calculators_dir / 'scripts' / 'utils' / 'common.sh'
            assert os.access(common_sh, os.X_OK), "common.sh should be executable"

            # Verify installed_files list contains all files
            assert result.get('installed_files') is not None
            installed_files = result['installed_files']

            # Check that all expected files are in the installed_files list
            expected_files = [
                'calculators/calc.sh',
                'calculators/scripts/helper.sh',
                'calculators/scripts/utils/common.sh',
                'algorithms/algo.py',
                'algorithms/data/config.json'
            ]

            for expected in expected_files:
                # if window paths are used, convert to posix style for comparison:
                if os.name == 'nt':
                    expected = expected.replace('/', '\\')
                assert any(expected in f for f in installed_files), \
                    f"{expected} not found in installed_files: {installed_files}"

            print(f"✓ Successfully installed {len(installed_files)} files")
            print(f"✓ All nested directories copied correctly")

        finally:
            os.chdir(original_cwd)


def test_install_model_global():
    """Test global installation to ~/.fz/"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test plugin zip
        zip_path = tmpdir / "fz-globaltest.zip"
        create_test_plugin_zip(zip_path, "globaltest")

        # Mock the home directory
        fake_home = tmpdir / "fake_home"
        fake_home.mkdir()

        # Temporarily override Path.home()
        import fz.installer
        original_home = Path.home
        fz.installer.Path.home = lambda: fake_home

        try:
            # Install globally
            result = install_model(str(zip_path), global_install=True)

            # Verify installation in fake home directory
            assert result['model_name'] == 'globaltest'

            model_json = fake_home / '.fz' / 'models' / 'globaltest.json'
            assert model_json.exists()

            # Verify nested files in global location
            assert (fake_home / '.fz' / 'calculators' / 'calc.sh').exists()
            assert (fake_home / '.fz' / 'calculators' / 'scripts' / 'helper.sh').exists()
            assert (fake_home / '.fz' / 'algorithms' / 'algo.py').exists()

            print("✓ Global installation works correctly")

        finally:
            # Restore original Path.home
            fz.installer.Path.home = original_home


def test_install_model_merge_directories():
    """Test that installing multiple plugins merges directories correctly"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create two test plugin zips with unique filenames
        zip_path1 = tmpdir / "fz-plugin1.zip"
        zip_path2 = tmpdir / "fz-plugin2.zip"

        # Create plugin1 with standard structure
        with zipfile.ZipFile(zip_path1, 'w') as zf:
            model_def = {"id": "plugin1", "varprefix": "$", "output": {}}
            zf.writestr("fz-plugin1-main/.fz/models/plugin1.json", json.dumps(model_def))
            zf.writestr("fz-plugin1-main/.fz/calculators/plugin1_calc.sh", "#!/bin/bash\necho 'plugin1'\n")
            zf.writestr("fz-plugin1-main/.fz/algorithms/plugin1_algo.py", "# Plugin 1 algorithm\n")

        # Create plugin2 with unique filenames to avoid overwriting
        with zipfile.ZipFile(zip_path2, 'w') as zf:
            model_def = {"id": "plugin2", "varprefix": "$", "output": {}}
            zf.writestr("fz-plugin2-main/.fz/models/plugin2.json", json.dumps(model_def))
            zf.writestr("fz-plugin2-main/.fz/calculators/plugin2_calc.sh", "#!/bin/bash\necho 'plugin2'\n")
            zf.writestr("fz-plugin2-main/.fz/algorithms/plugin2_algo.py", "# Plugin 2 algorithm\n")

        # Create a fake project directory
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Install first plugin
            result1 = install_model(str(zip_path1), global_install=False)
            assert result1['model_name'] == 'plugin1'

            # Install second plugin
            result2 = install_model(str(zip_path2), global_install=False)
            assert result2['model_name'] == 'plugin2'

            # Verify both plugins' model files exist
            assert (project_dir / '.fz' / 'models' / 'plugin1.json').exists()
            assert (project_dir / '.fz' / 'models' / 'plugin2.json').exists()

            # Verify both plugins' calculator files exist (merged in same directory)
            calculators_dir = project_dir / '.fz' / 'calculators'
            assert (calculators_dir / 'plugin1_calc.sh').exists()
            assert (calculators_dir / 'plugin2_calc.sh').exists()

            # Verify both plugins' algorithm files exist
            algorithms_dir = project_dir / '.fz' / 'algorithms'
            assert (algorithms_dir / 'plugin1_algo.py').exists()
            assert (algorithms_dir / 'plugin2_algo.py').exists()

            print("✓ Multiple plugins merge correctly without overwriting each other")

        finally:
            os.chdir(original_cwd)


def test_extract_model_files():
    """Test that extract_model_files correctly finds .fz directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test plugin zip
        zip_path = tmpdir / "fz-extracttest.zip"
        create_test_plugin_zip(zip_path, "extracttest")

        # Extract the model files
        extract_path = tmpdir / "extract"
        extract_path.mkdir()

        model_info = extract_model_files(zip_path, extract_path)

        # Verify the returned information
        assert model_info['model_name'] == 'extracttest'
        assert model_info['model_json'].exists()
        assert model_info['fz_dir'] is not None
        assert model_info['fz_dir'].exists()
        assert model_info['fz_dir'].name == '.fz'

        # Verify the .fz directory contains expected subdirectories
        fz_dir = model_info['fz_dir']
        assert (fz_dir / 'models').exists()
        assert (fz_dir / 'calculators').exists()
        assert (fz_dir / 'algorithms').exists()

        print("✓ extract_model_files correctly identifies .fz directory")


def test_install_model_no_additional_files():
    """Test installation of a model with only model.json (no calculators, algorithms, etc.)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a minimal plugin zip with only model.json
        zip_path = tmpdir / "fz-minimal.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            model_def = {
                "id": "minimal",
                "varprefix": "$",
                "output": {}
            }
            zf.writestr(
                "fz-minimal-main/.fz/models/minimal.json",
                json.dumps(model_def, indent=2)
            )

        # Create a fake project directory
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Install the minimal model
            result = install_model(str(zip_path), global_install=False)

            # Verify basic installation
            assert result['model_name'] == 'minimal'
            assert Path(result['install_path']).exists()

            # Verify installed_files is empty or has no entries
            assert len(result.get('installed_files', [])) == 0

            print("✓ Minimal model (only model.json) installs correctly")

        finally:
            os.chdir(original_cwd)


def test_list_installed_models():
    """Test listing installed models"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test plugin zip
        zip_path = tmpdir / "fz-listtest.zip"
        create_test_plugin_zip(zip_path, "listtest")

        # Create a fake project directory
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Install the model
            install_model(str(zip_path), global_install=False)

            # List installed models
            models = list_installed_models(global_list=False)

            # Verify the model appears in the list
            assert 'listtest' in models
            assert models['listtest']['id'] == 'listtest'
            assert models['listtest']['global'] is False

            print("✓ list_installed_models works correctly")

        finally:
            os.chdir(original_cwd)


def test_uninstall_model():
    """Test uninstalling a model"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a test plugin zip
        zip_path = tmpdir / "fz-uninstalltest.zip"
        create_test_plugin_zip(zip_path, "uninstalltest")

        # Create a fake project directory
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Install the model
            result = install_model(str(zip_path), global_install=False)
            model_path = Path(result['install_path'])
            assert model_path.exists()

            # Uninstall the model
            success = uninstall_model("uninstalltest", global_uninstall=False)
            assert success is True

            # Verify model JSON was removed
            assert not model_path.exists()

            # Note: uninstall_model currently only removes the model JSON,
            # not the calculator/algorithm files. This is expected behavior.

            print("✓ uninstall_model works correctly")

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests manually for debugging
    test_install_model_with_nested_directories()
    test_install_model_global()
    test_install_model_merge_directories()
    test_extract_model_files()
    test_install_model_no_additional_files()
    test_list_installed_models()
    test_uninstall_model()
    print("\n✅ All installer tests passed!")
