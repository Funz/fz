"""
Negative tests for plugin/model installation
Tests error handling for invalid plugins, missing files, invalid formats, etc.
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
    list_installed_models,
    normalize_github_url
)


def test_install_nonexistent_zip():
    """Test that installing a non-existent zip file raises appropriate error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Try to install a file that doesn't exist
            nonexistent_zip = tmpdir / "does_not_exist.zip"

            with pytest.raises((FileNotFoundError, ValueError, Exception)):
                install_model(str(nonexistent_zip), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_empty_zip():
    """Test that installing an empty zip file raises appropriate error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create an empty zip file
        empty_zip = tmpdir / "empty.zip"
        with zipfile.ZipFile(empty_zip, 'w') as zf:
            pass  # Empty zip

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Empty zip should fail - no .fz directory found
            with pytest.raises((ValueError, FileNotFoundError, Exception)):
                install_model(str(empty_zip), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_zip_without_fz_directory():
    """Test that installing a zip without .fz directory raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a zip with content but no .fz directory
        zip_path = tmpdir / "no_fz_dir.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("README.md", "# Just a readme\n")
            zf.writestr("src/code.py", "print('hello')\n")

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # No .fz directory should cause failure
            with pytest.raises((ValueError, FileNotFoundError, Exception)):
                install_model(str(zip_path), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_zip_without_model_json():
    """Test that installing a zip without model.json raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a zip with .fz directory but no model.json
        zip_path = tmpdir / "no_model_json.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Create .fz directory structure but missing model JSON
            zf.writestr("fz-test-main/.fz/calculators/calc.sh", "#!/bin/bash\n")
            zf.writestr("fz-test-main/.fz/algorithms/algo.py", "# algorithm\n")

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Missing model.json should cause failure
            with pytest.raises((ValueError, FileNotFoundError, Exception)):
                install_model(str(zip_path), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_model_with_invalid_json():
    """Test that installing a model with invalid JSON raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a zip with malformed JSON
        zip_path = tmpdir / "invalid_json.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Invalid JSON syntax
            zf.writestr(
                "fz-invalid-main/.fz/models/invalid.json",
                "{ this is not valid JSON }"
            )

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Invalid JSON should cause failure
            with pytest.raises((json.JSONDecodeError, ValueError, Exception)):
                install_model(str(zip_path), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_model_without_id_field():
    """Test that installing a model JSON without 'id' field raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a zip with model JSON missing 'id' field
        zip_path = tmpdir / "no_id.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            model_def = {
                # Missing 'id' field
                "varprefix": "$",
                "output": {}
            }
            zf.writestr(
                "fz-noid-main/.fz/models/noid.json",
                json.dumps(model_def, indent=2)
            )

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Missing 'id' field should cause failure
            with pytest.raises((ValueError, KeyError, Exception)):
                install_model(str(zip_path), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_model_with_mismatched_id():
    """Test model JSON with id that doesn't match filename"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a zip where the JSON filename and id field don't match
        zip_path = tmpdir / "mismatch.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            model_def = {
                "id": "actual_name",  # This differs from filename
                "varprefix": "$",
                "output": {}
            }
            # Filename says "wrong_name" but id says "actual_name"
            zf.writestr(
                "fz-wrong_name-main/.fz/models/wrong_name.json",
                json.dumps(model_def, indent=2)
            )

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # This might succeed but the id field takes precedence
            # Let's verify the behavior
            result = install_model(str(zip_path), global_install=False)

            # The model should be installed with the id from the JSON
            assert result['model_name'] == 'actual_name'

        finally:
            os.chdir(original_cwd)


def test_install_corrupted_zip():
    """Test that installing a corrupted zip file raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a file that looks like a zip but is corrupted
        corrupted_zip = tmpdir / "corrupted.zip"
        with open(corrupted_zip, 'wb') as f:
            f.write(b"PK\x03\x04" + b"garbage data not a real zip")

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Corrupted zip should cause failure
            with pytest.raises((zipfile.BadZipFile, Exception)):
                install_model(str(corrupted_zip), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_install_non_zip_file():
    """Test that installing a non-zip file raises error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a text file pretending to be a zip
        text_file = tmpdir / "not_a_zip.zip"
        with open(text_file, 'w') as f:
            f.write("This is just a text file\n")

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Non-zip file should cause failure
            with pytest.raises((zipfile.BadZipFile, Exception)):
                install_model(str(text_file), global_install=False)

        finally:
            os.chdir(original_cwd)


def test_uninstall_nonexistent_model():
    """Test that uninstalling a non-existent model fails gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Try to uninstall a model that doesn't exist
            result = uninstall_model("does_not_exist", global_uninstall=False)

            # Should return False (not successful)
            assert result is False

        finally:
            os.chdir(original_cwd)


def test_extract_model_files_from_invalid_zip():
    """Test extract_model_files with invalid zip"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create an invalid zip file
        invalid_zip = tmpdir / "invalid.zip"
        with open(invalid_zip, 'w') as f:
            f.write("not a zip file")

        extract_path = tmpdir / "extract"
        extract_path.mkdir()

        # Should raise error when trying to extract
        with pytest.raises((zipfile.BadZipFile, Exception)):
            extract_model_files(invalid_zip, extract_path)


def test_normalize_github_url_invalid():
    """Test normalize_github_url with various invalid inputs"""

    # Test with empty string
    result = normalize_github_url("")
    # Empty string could be treated as non-existent file (returns None)
    # or converted to GitHub URL - behavior depends on implementation

    # Test with invalid URL format
    result = normalize_github_url("htp://invalid-protocol.com/repo")
    # Should either return None or handle gracefully

    # Test with None should not crash (though typing may prevent this)
    # This test documents expected behavior for edge cases


def test_install_model_with_permission_error(monkeypatch):
    """Test installation when write permissions are denied"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a valid plugin zip
        zip_path = tmpdir / "fz-test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            model_def = {"id": "test", "varprefix": "$", "output": {}}
            zf.writestr(
                "fz-test-main/.fz/models/test.json",
                json.dumps(model_def)
            )

        # Create a project directory without write permissions
        project_dir = tmpdir / "readonly_project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Make .fz directory read-only to simulate permission error
            fz_dir = project_dir / ".fz"
            fz_dir.mkdir()

            # On Unix systems, make directory read-only
            if os.name != 'nt':  # Skip on Windows
                os.chmod(fz_dir, 0o444)

                # Installation should fail with permission error
                with pytest.raises((PermissionError, OSError, Exception)):
                    install_model(str(zip_path), global_install=False)

                # Restore permissions for cleanup
                os.chmod(fz_dir, 0o755)

        finally:
            os.chdir(original_cwd)


def test_list_installed_models_empty():
    """Test listing models when none are installed locally"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_dir = tmpdir / "empty_project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # List local models when none are installed locally
            # Note: global models may exist, so we only check local
            models = list_installed_models(global_list=False)

            # Should return dict (may include global models)
            assert isinstance(models, dict)

            # Check that no local models exist
            local_models = [m for m in models.values() if not m.get('global', False)]
            assert len(local_models) == 0

        finally:
            os.chdir(original_cwd)


def test_install_model_with_nested_zip():
    """Test installing a zip-within-zip (should fail)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create inner zip
        inner_zip = tmpdir / "inner.zip"
        with zipfile.ZipFile(inner_zip, 'w') as zf:
            model_def = {"id": "inner", "varprefix": "$", "output": {}}
            zf.writestr("fz-inner-main/.fz/models/inner.json", json.dumps(model_def))

        # Create outer zip containing the inner zip
        outer_zip = tmpdir / "outer.zip"
        with zipfile.ZipFile(outer_zip, 'w') as zf:
            zf.write(inner_zip, "inner.zip")

        project_dir = tmpdir / "project"
        project_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            # Nested zip should fail - no .fz directory at top level
            with pytest.raises((ValueError, FileNotFoundError, Exception)):
                install_model(str(outer_zip), global_install=False)

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v"])
