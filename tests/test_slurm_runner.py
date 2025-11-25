"""
Test SLURM runner functionality
"""
import pytest
import tempfile
from pathlib import Path
from fz.runners import parse_slurm_uri, _validate_calculator_uri


class TestSlurmUriParsing:
    """Test SLURM URI parsing functionality"""

    def test_parse_slurm_uri_local_simple(self):
        """Test parsing simple local SLURM URI"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://:compute/run.sh"
        )
        assert host is None
        assert port is None
        assert username is None
        assert password is None
        assert partition == "compute"
        assert script == "run.sh"

    def test_parse_slurm_uri_remote_with_host(self):
        """Test parsing remote SLURM URI with host"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://cluster.edu:gpu/run.sh"
        )
        assert host == "cluster.edu"
        assert port == 22
        assert username is None
        assert password is None
        assert partition == "gpu"
        assert script == "run.sh"

    def test_parse_slurm_uri_remote_with_user(self):
        """Test parsing remote SLURM URI with user"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://user@cluster.edu:gpu/run.sh"
        )
        assert host == "cluster.edu"
        assert port == 22
        assert username == "user"
        assert password is None
        assert partition == "gpu"
        assert script == "run.sh"

    def test_parse_slurm_uri_remote_with_user_and_port(self):
        """Test parsing remote SLURM URI with user and custom port"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://user@cluster.edu:2222:gpu/run.sh"
        )
        assert host == "cluster.edu"
        assert port == 2222
        assert username == "user"
        assert password is None
        assert partition == "gpu"
        assert script == "run.sh"

    def test_parse_slurm_uri_remote_with_password(self):
        """Test parsing remote SLURM URI with password"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://user:pass123@cluster.edu:gpu/run.sh"
        )
        assert host == "cluster.edu"
        assert port == 22
        assert username == "user"
        assert password == "pass123"
        assert partition == "gpu"
        assert script == "run.sh"

    def test_parse_slurm_uri_remote_host_port_partition(self):
        """Test parsing remote SLURM URI with host:port:partition"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://cluster.edu:2222:gpu/run.sh"
        )
        assert host == "cluster.edu"
        assert port == 2222
        assert username is None
        assert password is None
        assert partition == "gpu"
        assert script == "run.sh"

    def test_parse_slurm_uri_script_with_path(self):
        """Test parsing SLURM URI with script path"""
        host, port, username, password, partition, script = parse_slurm_uri(
            "slurm://:compute/path/to/script.sh"
        )
        assert host is None
        assert partition == "compute"
        assert script == "path/to/script.sh"

    def test_parse_slurm_uri_missing_script(self):
        """Test parsing SLURM URI without script raises error"""
        with pytest.raises(ValueError, match="script path is required"):
            parse_slurm_uri("slurm://:compute/")

    def test_parse_slurm_uri_missing_slash(self):
        """Test parsing SLURM URI without slash raises error"""
        with pytest.raises(ValueError, match="Expected format"):
            parse_slurm_uri("slurm://:compute")

    def test_parse_slurm_uri_missing_partition(self):
        """Test parsing SLURM URI with empty partition raises error"""
        # This case: slurm:///script.sh (empty partition)
        with pytest.raises(ValueError, match="partition is required"):
            parse_slurm_uri("slurm:///script.sh")

    def test_parse_slurm_uri_user_without_host(self):
        """Test parsing SLURM URI with user but no host raises error"""
        with pytest.raises(ValueError, match="host must also be provided"):
            parse_slurm_uri("slurm://user@gpu/script.sh")

    def test_parse_slurm_uri_old_format_without_colon(self):
        """Test parsing SLURM URI without colon prefix (old format) raises error"""
        with pytest.raises(ValueError, match="note the colon before partition"):
            parse_slurm_uri("slurm://compute/run.sh")


class TestSlurmUriValidation:
    """Test SLURM URI validation functionality"""

    def test_validate_slurm_uri_valid(self):
        """Test validation of valid SLURM URI"""
        # Should not raise
        _validate_calculator_uri("slurm://:compute/run.sh")

    def test_validate_slurm_uri_invalid_format(self):
        """Test validation of invalid SLURM URI format"""
        with pytest.raises(ValueError, match="Invalid SLURM calculator URI"):
            _validate_calculator_uri("slurm://:compute")

    def test_validate_calculator_uri_slurm_scheme(self):
        """Test that slurm:// is a supported scheme"""
        # Should not raise
        _validate_calculator_uri("slurm://:partition/script.sh")

    def test_validate_slurm_uri_missing_partition(self):
        """Test validation catches missing partition"""
        with pytest.raises(ValueError, match="Invalid SLURM calculator URI"):
            _validate_calculator_uri("slurm:///script.sh")


class TestSlurmCalculatorIntegration:
    """Integration tests for SLURM calculator"""

    def test_slurm_local_simple_calculation(self):
        """Test simple local SLURM calculation (requires srun)"""
        pytest.skip("Requires SLURM installation - skipping in CI")
        # This test would require an actual SLURM installation
        # Example implementation:
        # from fz import fzr
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     input_file = Path(tmpdir) / "input.txt"
        #     input_file.write_text("x = ${x}\n")
        #     model = {"output": {"result": "cat output.txt"}}
        #     results = fzr(
        #         input_file,
        #         model=model,
        #         variables={"x": [1, 2]},
        #         calculator="slurm://debug/echo"
        #     )
        #     assert len(results) == 2

    def test_slurm_remote_calculation(self):
        """Test remote SLURM calculation via SSH (requires SLURM cluster)"""
        pytest.skip("Requires remote SLURM cluster - skipping in CI")
        # This test would require access to a remote SLURM cluster
        # Example implementation:
        # from fz import fzr
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     input_file = Path(tmpdir) / "input.txt"
        #     input_file.write_text("x = ${x}\n")
        #     model = {"output": {"result": "cat output.txt"}}
        #     results = fzr(
        #         input_file,
        #         model=model,
        #         variables={"x": [1, 2]},
        #         calculator="slurm://user@cluster.edu:compute/submit.sh"
        #     )
        #     assert len(results) == 2


class TestSlurmErrorHandling:
    """Test SLURM error handling"""

    def test_invalid_partition_name(self):
        """Test error handling for invalid partition names"""
        # This would require SLURM to be installed
        pytest.skip("Requires SLURM installation - skipping in CI")

    def test_timeout_handling(self):
        """Test timeout handling for SLURM jobs"""
        # This would require SLURM to be installed
        pytest.skip("Requires SLURM installation - skipping in CI")

    def test_job_failure_handling(self):
        """Test handling of failed SLURM jobs"""
        # This would require SLURM to be installed
        pytest.skip("Requires SLURM installation - skipping in CI")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
