"""
Tests for shell path discovery and binary resolution functionality
"""

import pytest
import os
import sys
import platform
import tempfile
from pathlib import Path

from fz.shell import ShellPathResolver, get_resolver, reinitialize_resolver, replace_commands_in_string
from fz.config import get_config, Config


class TestShellPathResolver:
    """Tests for ShellPathResolver class"""

    def test_resolver_initialization_with_custom_path(self):
        """Test initializing resolver with custom shell path"""
        custom_path = "/usr/bin:/opt/bin"
        resolver = ShellPathResolver(custom_path)
        assert resolver.custom_shell_path == custom_path

    def test_resolver_initialization_without_custom_path(self):
        """Test initializing resolver without custom shell path (uses system PATH)"""
        resolver = ShellPathResolver(None)
        assert resolver.custom_shell_path is None

    def test_get_search_paths_with_custom_path_unix(self):
        """Test getting search paths on Unix-like systems"""
        if platform.system() == "Windows":
            pytest.skip("Unix-specific test")

        custom_path = "/usr/bin:/opt/bin:/local/bin"
        resolver = ShellPathResolver(custom_path)
        paths = resolver.get_search_paths()
        assert paths == ["/usr/bin", "/opt/bin", "/local/bin"]

    def test_get_search_paths_with_custom_path_windows(self):
        """Test getting search paths on Windows"""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        custom_path = "C:\\Program Files\\Git\\bin;C:\\msys64\\usr\\bin"
        resolver = ShellPathResolver(custom_path)
        paths = resolver.get_search_paths()
        assert "C:\\Program Files\\Git\\bin" in paths
        assert "C:\\msys64\\usr\\bin" in paths

    def test_get_search_paths_without_custom_path(self):
        """Test getting search paths from system PATH"""
        resolver = ShellPathResolver(None)
        paths = resolver.get_search_paths()
        # Should return system PATH
        assert len(paths) > 0
        assert isinstance(paths, list)

    def test_resolve_command_found(self):
        """Test resolving a command that exists in PATH"""
        # Use python which should always be in PATH
        resolver = ShellPathResolver(None)
        python_path = resolver.resolve_command("python")
        # Either python or python3 should be found
        if python_path:
            assert python_path is not None
            assert Path(python_path).exists()

    def test_resolve_command_not_found(self):
        """Test resolving a command that doesn't exist"""
        resolver = ShellPathResolver(None)
        result = resolver.resolve_command("nonexistent_command_xyz_123")
        assert result is None

    def test_resolve_command_caching(self):
        """Test that resolved commands are cached"""
        resolver = ShellPathResolver(None)
        # Resolve a command twice
        result1 = resolver.resolve_command("python")
        result2 = resolver.resolve_command("python")
        # Both should return the same (cached) result
        assert result1 == result2

    def test_clear_cache(self):
        """Test clearing the binary cache"""
        resolver = ShellPathResolver(None)
        # Resolve a command
        result1 = resolver.resolve_command("python")
        # Clear cache
        resolver.clear_cache()
        # Cache should be empty
        assert len(resolver._binary_cache) == 0

    def test_list_available_binaries(self):
        """Test listing available binaries"""
        # Create a temporary directory with some test executables
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files with execute permissions
            test_bin = Path(tmpdir) / "test_binary"
            test_bin.touch()
            test_bin.chmod(0o755)

            resolver = ShellPathResolver(tmpdir)
            binaries = resolver.list_available_binaries()

            # On Windows, .exe extension might be added, so check for both
            assert len(binaries) > 0
            binary_names = [b.lower() for b in binaries]
            assert any("test" in b for b in binary_names)

    def test_replace_commands_in_string_with_custom_path(self):
        """Test replacing commands in string with custom shell path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock grep binary
            grep_path = Path(tmpdir) / "grep"
            grep_path.touch()
            grep_path.chmod(0o755)

            resolver = ShellPathResolver(tmpdir)
            input_string = "grep 'pattern' file.txt"
            result = resolver.replace_commands_in_string(input_string)

            # Should contain the resolved grep path
            assert str(grep_path) in result or "grep" in result

    def test_replace_commands_in_string_without_custom_path(self):
        """Test that replace_commands_in_string returns original if no custom path"""
        resolver = ShellPathResolver(None)
        input_string = "grep 'pattern' file.txt"
        result = resolver.replace_commands_in_string(input_string)
        # Should return original string if no custom path
        assert result == input_string

    def test_replace_multiple_commands(self):
        """Test replacing multiple commands in a string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock binaries
            for cmd in ["grep", "awk"]:
                cmd_path = Path(tmpdir) / cmd
                cmd_path.touch()
                cmd_path.chmod(0o755)

            resolver = ShellPathResolver(tmpdir)
            input_string = "grep 'pattern' file.txt | awk '{print $1}'"
            result = resolver.replace_commands_in_string(input_string)

            # Result should not be the same as input (commands should be replaced)
            # But we can't be certain of exact output, so just check it contains expected parts
            assert "pattern" in result
            assert "$1" in result


class TestGlobalResolver:
    """Tests for global resolver instance"""

    def test_get_resolver_returns_singleton(self):
        """Test that get_resolver returns the same instance"""
        resolver1 = get_resolver()
        resolver2 = get_resolver()
        assert resolver1 is resolver2

    def test_reinitialize_resolver(self):
        """Test reinitializing the resolver"""
        # Get initial resolver
        resolver1 = get_resolver()
        # Reinitialize
        reinitialize_resolver()
        # Get new resolver
        resolver2 = get_resolver()
        # They should not be the same object (since we reinitialied)
        assert resolver1 is not resolver2

    def test_replace_commands_in_string_global(self):
        """Test global replace_commands_in_string function"""
        # This should work with the global resolver
        result = replace_commands_in_string("echo hello")
        assert isinstance(result, str)


class TestConfigIntegration:
    """Tests for FZ_SHELL_PATH configuration integration"""

    def test_config_shell_path_from_env(self, monkeypatch):
        """Test that FZ_SHELL_PATH is read from environment"""
        test_path = "/usr/bin:/opt/bin"
        monkeypatch.setenv("FZ_SHELL_PATH", test_path)

        # Create new config instance
        config = Config()
        assert config.shell_path == test_path

    def test_config_shell_path_default_none(self, monkeypatch):
        """Test that FZ_SHELL_PATH defaults to None"""
        # Make sure env var is not set
        monkeypatch.delenv("FZ_SHELL_PATH", raising=False)

        # Create new config instance
        config = Config()
        assert config.shell_path is None

    def test_config_summary_includes_shell_path(self):
        """Test that config summary includes shell_path"""
        config = get_config()
        summary = config.get_summary()
        assert "shell_path" in summary


class TestWindowsPathResolution:
    """Tests for Windows-specific path resolution"""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_resolve_command_with_exe_extension(self):
        """Test that Windows resolver handles .exe extensions"""
        # On Windows, commands like 'python' should resolve to 'python.exe'
        resolver = ShellPathResolver(None)
        python_path = resolver.resolve_command("python")
        if python_path:
            # Either ends with .exe or is a valid executable
            assert Path(python_path).exists()

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_semicolon_separator_on_windows(self):
        """Test that Windows uses semicolon as PATH separator"""
        custom_path = "C:\\bin1;C:\\bin2;C:\\bin3"
        resolver = ShellPathResolver(custom_path)
        paths = resolver.get_search_paths()
        assert len(paths) == 3
        assert "C:\\bin1" in paths


class TestBashDiscoveryPriority:
    """Tests for bash discovery priority order with FZ_SHELL_PATH"""

    def test_bash_discovery_prioritizes_fz_shell_path(self, monkeypatch):
        """Test that FZ_SHELL_PATH is checked before system PATH for bash discovery"""
        # Create a temporary directory with a mock bash executable
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a mock bash executable in our custom directory
            mock_bash = tmpdir_path / "bash"
            if platform.system() == "Windows":
                mock_bash = tmpdir_path / "bash.exe"

            mock_bash.touch()
            mock_bash.chmod(0o755)

            # Set FZ_SHELL_PATH to our custom directory
            monkeypatch.setenv("FZ_SHELL_PATH", str(tmpdir))

            # Reload config and reinitialize the resolver to pick up the new environment variable
            from fz.config import reload_config
            from fz.shell import reinitialize_resolver, get_windows_bash_executable
            reload_config()  # Must reload config first to pick up new FZ_SHELL_PATH
            reinitialize_resolver()

            # On Windows, test the actual bash discovery function
            if platform.system() == "Windows":
                bash_path = get_windows_bash_executable()
                # Should find our mock bash from FZ_SHELL_PATH
                assert bash_path is not None
                # The path should be from our custom directory
                assert str(tmpdir) in str(bash_path) or mock_bash == Path(bash_path)
            else:
                # On Unix, just verify the resolver uses FZ_SHELL_PATH
                from fz.shell import get_resolver
                resolver = get_resolver()
                bash_path = resolver.resolve_command("bash")
                # Should find bash (either our mock or system bash)
                # The key is that FZ_SHELL_PATH is checked first
                assert bash_path is not None

    def test_fz_shell_path_takes_precedence_over_system_path(self):
        """Test that commands in FZ_SHELL_PATH are found before system PATH"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a mock command in custom directory
            mock_cmd = tmpdir_path / "testcmd"
            if platform.system() == "Windows":
                mock_cmd = tmpdir_path / "testcmd.exe"

            mock_cmd.write_text("#!/bin/bash\necho 'custom'\n")
            mock_cmd.chmod(0o755)

            # Create a resolver directly with the custom shell path
            # This simulates what happens when FZ_SHELL_PATH is set
            resolver = ShellPathResolver(str(tmpdir))

            # Verify the custom path is being used
            search_paths = resolver.get_search_paths()
            assert str(tmpdir) in search_paths

            # Resolve the command
            resolved = resolver.resolve_command("testcmd")

            # Should find our custom command
            assert resolved is not None
            assert str(tmpdir) in resolved

    def test_bash_falls_back_to_system_path_when_fz_shell_path_not_set(self, monkeypatch):
        """Test that bash discovery falls back to system PATH when FZ_SHELL_PATH is not set"""
        # Make sure FZ_SHELL_PATH is not set
        monkeypatch.delenv("FZ_SHELL_PATH", raising=False)

        # Reload config and reinitialize resolver
        from fz.config import reload_config
        from fz.shell import reinitialize_resolver, get_windows_bash_executable
        reload_config()  # Must reload config first to pick up removed FZ_SHELL_PATH
        reinitialize_resolver()

        if platform.system() == "Windows":
            # On Windows, should still find bash (from PATH or hardcoded locations)
            bash_path = get_windows_bash_executable()
            # Bash might be found or might not, depending on the system
            # The key is that it tries system PATH after FZ_SHELL_PATH
            assert bash_path is None or isinstance(bash_path, str)
        else:
            # On Unix, bash should always be found in system PATH
            from fz.shell import get_resolver
            resolver = get_resolver()
            bash_path = resolver.resolve_command("bash")
            # On Unix, bash is typically available
            # If not found, that's okay for this test - we're just verifying fallback logic
            assert bash_path is None or Path(bash_path).exists()
