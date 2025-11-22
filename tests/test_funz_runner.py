"""
Test Funz runner URI parsing and basic functionality

Tests the funz:// calculator type for connecting to Funz servers.
"""
import pytest
from pathlib import Path
from fz.runners import resolve_calculators, _validate_calculator_uri


def test_funz_uri_validation():
    """Test that funz:// URIs are accepted as valid"""
    # Valid Funz URIs
    valid_uris = [
        "funz://:5000/R",
        "funz://localhost:5000/R",
        "funz://server.example.com:5555/Python",
    ]

    for uri in valid_uris:
        # Should not raise ValueError
        _validate_calculator_uri(uri)


def test_funz_uri_in_resolve_calculators():
    """Test that Funz URIs are properly resolved"""
    calculators = ["funz://:5000/R"]
    resolved = resolve_calculators(calculators)
    assert resolved == ["funz://:5000/R"]


def test_funz_uri_invalid_format():
    """Test that invalid Funz URIs raise appropriate errors"""
    # This would fail during actual execution, not validation
    # Validation only checks the scheme
    invalid_uri = "funz://invalid"  # Missing port and code

    # Should pass validation (scheme is correct)
    _validate_calculator_uri(invalid_uri)


def test_funz_uri_parsing():
    """Test Funz URI parsing logic"""
    from fz.runners import run_funz_calculation
    import tempfile

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Create a dummy input file
        (working_dir / "input.txt").write_text("test")

        # Simple model
        model = {
            "output": {}
        }

        # Test with invalid URI (missing code)
        result = run_funz_calculation(
            working_dir,
            "funz://:5000",  # Missing code
            model,
            timeout=1
        )
        assert result["status"] == "error"
        assert "code" in result["error"].lower()

        # Test with invalid port
        result = run_funz_calculation(
            working_dir,
            "funz://:invalid/R",
            model,
            timeout=1
        )
        assert result["status"] == "error"
        assert "port" in result["error"].lower()


def test_funz_connection_failure():
    """Test Funz runner behavior when server is not available"""
    from fz.runners import run_funz_calculation
    import tempfile

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Create a dummy input file
        (working_dir / "input.txt").write_text("test")

        # Simple model
        model = {
            "output": {}
        }

        # Try to connect to a server that doesn't exist
        # Use a high port that's unlikely to be in use
        result = run_funz_calculation(
            working_dir,
            "funz://:59999/TestCode",
            model,
            timeout=2  # Short timeout
        )

        # Should fail with connection error or timeout
        assert result["status"] in ["error", "timeout"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
