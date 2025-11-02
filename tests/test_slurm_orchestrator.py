"""
Unit tests for SLURM Orchestrator
Tests: deployment, job submission, status checking, log retrieval
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
import tempfile
import yaml
import os
import subprocess

from ubenchai.servers.slurm_orchestrator import SlurmOrchestrator
from ubenchai.servers.services import (
    ServiceRecipe,
    ServiceStatus,
    ResourceSpec,
    Port,
    VolumeMount,
)


class TestSlurmOrchestratorInitialization:
    """Tests for SlurmOrchestrator initialization"""

    def test_initialization_with_account(self):
        """Test initialization with account parameter"""
        orchestrator = SlurmOrchestrator(account="p12345")
        assert orchestrator.account == "p12345"

    def test_initialization_from_env(self):
        """Test initialization from environment variables"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            orchestrator = SlurmOrchestrator()
            assert orchestrator.account == "p12345"

    def test_initialization_from_config_file(self):
        """Test initialization from config file"""
        config_data = {
            "slurm": {
                "account": "p12345",
                "partition": "gpu",
                "qos": "default",
                "time_limit": "01:00:00",
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            orchestrator = SlurmOrchestrator(config_file=temp_path)
            assert orchestrator.account == "p12345"
            assert orchestrator.partition == "gpu"
        finally:
            Path(temp_path).unlink()

    def test_initialization_no_account_raises(self):
        """Test initialization without account raises error"""
        with patch.dict(os.environ, clear=True):
            with pytest.raises(ValueError, match="SLURM account must be provided"):
                SlurmOrchestrator()

    def test_initialization_priority_order(self):
        """Test parameter priority: arg > env > config > default"""
        config_data = {"slurm": {"partition": "config-partition"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            with patch.dict(
                os.environ,
                {"SLURM_ACCOUNT": "env-account", "SLURM_PARTITION": "env-partition"},
            ):
                # Argument should take priority
                orchestrator = SlurmOrchestrator(
                    account="arg-account",
                    partition="arg-partition",
                    config_file=temp_path,
                )
                assert orchestrator.account == "arg-account"
                assert orchestrator.partition == "arg-partition"
        finally:
            Path(temp_path).unlink()

    def test_initialization_defaults(self):
        """Test default values"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            orchestrator = SlurmOrchestrator()
            assert orchestrator.partition == "gpu"
            assert orchestrator.qos == "default"
            # Default time limit may come from config file, check actual value
            assert orchestrator.time_limit in ["01:00:00", "00:10:00"]

    def test_initialization_log_directory_created(self):
        """Test that log directory is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"

            with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
                orchestrator = SlurmOrchestrator(log_directory=str(log_dir))
                assert log_dir.exists()


class TestSlurmOrchestratorDeployment:
    """Tests for service deployment"""

    @pytest.fixture
    def orchestrator(self):
        """Fixture for orchestrator"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            return SlurmOrchestrator()

    @pytest.fixture
    def basic_recipe(self):
        """Fixture for basic recipe"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        return ServiceRecipe(
            name="test-service", image="docker://test/image:latest", resources=resources
        )

    @pytest.fixture
    def recipe_with_gpu(self):
        """Fixture for recipe with GPU"""
        resources = ResourceSpec(
            cpu_cores=4, memory_gb=8, gpu_count=2, gpu_type="nvidia-a100"
        )
        return ServiceRecipe(
            name="gpu-service", image="docker://test/gpu:latest", resources=resources
        )

    @pytest.fixture
    def recipe_with_volumes(self):
        """Fixture for recipe with volumes"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        volumes = [
            VolumeMount("/host/data", "/container/data", readonly=False),
            VolumeMount("/host/config", "/container/config", readonly=True),
        ]
        return ServiceRecipe(
            name="volume-service",
            image="docker://test/volume:latest",
            resources=resources,
            volumes=volumes,
        )

    def test_deploy_service_success(self, orchestrator, basic_recipe):
        """Test successful service deployment"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="Submitted batch job 12345", stderr=""
            )

            job_id = orchestrator.deploy_service(basic_recipe)

            assert job_id == "12345"
            mock_run.assert_called_once()

    def test_deploy_service_failure(self, orchestrator, basic_recipe):
        """Test deployment failure"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("sbatch failed")

            with pytest.raises(RuntimeError, match="SLURM deployment failed"):
                orchestrator.deploy_service(basic_recipe)

    def test_build_batch_script_basic(self, orchestrator, basic_recipe):
        """Test batch script generation for basic recipe"""
        log_path = "/tmp/test.log"
        script = orchestrator._build_batch_script(basic_recipe, log_path)

        assert "#SBATCH --job-name=test-service" in script
        assert "#SBATCH --cpus-per-task=2" in script
        assert "#SBATCH --mem=4G" in script
        assert "docker://test/image:latest" in script
        assert f"#SBATCH --output={log_path}" in script

    def test_build_batch_script_with_gpu(self, orchestrator, recipe_with_gpu):
        """Test batch script with GPU resources"""
        log_path = "/tmp/test.log"
        script = orchestrator._build_batch_script(recipe_with_gpu, log_path)

        assert "#SBATCH --gres=gpu:2" in script
        assert "--nv" in script  # NVIDIA GPU flag

    def test_build_batch_script_with_volumes(self, orchestrator, recipe_with_volumes):
        """Test batch script with volume mounts"""
        log_path = "/tmp/test.log"
        script = orchestrator._build_batch_script(recipe_with_volumes, log_path)

        assert "mkdir -p /host/data" in script
        assert "mkdir -p /host/config" in script
        assert "--bind" in script
        assert "/host/data:/container/data" in script

    def test_build_batch_script_with_environment(self, orchestrator, basic_recipe):
        """Test batch script with environment variables"""
        basic_recipe.environment = {
            "TEST_VAR": "test_value",
            "ANOTHER_VAR": "another_value",
        }

        log_path = "/tmp/test.log"
        script = orchestrator._build_batch_script(basic_recipe, log_path)

        assert 'export APPTAINERENV_TEST_VAR="test_value"' in script
        assert 'export APPTAINERENV_ANOTHER_VAR="another_value"' in script

    def test_build_batch_script_with_command(self, orchestrator, basic_recipe):
        """Test batch script with custom command"""
        basic_recipe.command = ["/bin/bash", "-c", "echo 'Hello World'"]

        log_path = "/tmp/test.log"
        script = orchestrator._build_batch_script(basic_recipe, log_path)

        assert "echo 'Hello World'" in script

    def test_generate_log_filename(self, orchestrator, basic_recipe):
        """Test log filename generation"""
        filename = orchestrator._generate_log_filename(basic_recipe)

        assert filename.startswith("test-service_")
        assert filename.endswith(".log")
        # Format: name_YYYYMMDD_HHMMSS_uuid.log
        # When split by "_", we get 4 parts: [name, YYYYMMDD, HHMMSS, uuid.log]
        parts = filename.split("_")
        assert len(parts) == 4
        assert parts[0] == "test-service"

    def test_submit_job_success(self, orchestrator):
        """Test successful job submission"""
        script_content = "#!/bin/bash\necho test"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="Submitted batch job 12345", stderr=""
            )

            job_id = orchestrator._submit_job(script_content)

            assert job_id == "12345"

    def test_submit_job_failure(self, orchestrator):
        """Test job submission failure"""
        script_content = "#!/bin/bash\necho test"

        with patch("subprocess.run") as mock_run:
            # Use CalledProcessError which is what subprocess.run raises
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["sbatch"], stderr="sbatch failed"
            )

            with pytest.raises(RuntimeError, match="Job submission failed"):
                orchestrator._submit_job(script_content)


class TestSlurmOrchestratorServiceControl:
    """Tests for service control operations"""

    @pytest.fixture
    def orchestrator(self):
        """Fixture for orchestrator"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            return SlurmOrchestrator()

    def test_stop_service_success(self, orchestrator):
        """Test successful service stop"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = orchestrator.stop_service("12345")

            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "scancel" in args
            assert "12345" in args

    def test_stop_service_failure(self, orchestrator):
        """Test service stop failure"""
        with patch("subprocess.run") as mock_run:
            # Use CalledProcessError which is what subprocess.run raises
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["scancel", "12345"], stderr="scancel failed"
            )

            result = orchestrator.stop_service("12345")

            assert result is False

    def test_get_service_status_running(self, orchestrator):
        """Test getting status for running service"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="RUNNING\n", stderr="")

            status = orchestrator.get_service_status("12345")

            assert status == ServiceStatus.RUNNING

    def test_get_service_status_pending(self, orchestrator):
        """Test getting status for pending service"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="PENDING\n", stderr="")

            status = orchestrator.get_service_status("12345")

            assert status == ServiceStatus.PENDING

    def test_get_service_status_completed(self, orchestrator):
        """Test getting status for completed service"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="COMPLETED\n", stderr="")

            status = orchestrator.get_service_status("12345")

            assert status == ServiceStatus.STOPPED

    def test_get_service_status_failed(self, orchestrator):
        """Test getting status for failed service"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="FAILED\n", stderr="")

            status = orchestrator.get_service_status("12345")

            assert status == ServiceStatus.ERROR

    def test_get_service_status_not_found(self, orchestrator):
        """Test getting status for non-existent service"""
        with patch("subprocess.run") as mock_run:
            # Use CalledProcessError which is what subprocess.run raises
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["squeue", "-j", "99999"], stderr="Job not found"
            )

            status = orchestrator.get_service_status("99999")

            assert status == ServiceStatus.STOPPED

    def test_get_service_status_unknown(self, orchestrator):
        """Test getting unknown status"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="UNKNOWN_STATE\n", stderr=""
            )

            status = orchestrator.get_service_status("12345")

            assert status == ServiceStatus.UNKNOWN


class TestSlurmOrchestratorLogs:
    """Tests for log retrieval"""

    @pytest.fixture
    def orchestrator(self):
        """Fixture for orchestrator with temp log directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
                orch = SlurmOrchestrator(log_directory=tmpdir)
                orch.log_directory = Path(tmpdir)
                yield orch

    def test_get_service_logs_from_custom_log(self, orchestrator):
        """Test getting logs from custom log file"""
        log_content = "Test log content\nLine 2"
        log_file = (
            orchestrator.log_directory / "test-service_20251013_120000_abc123.log"
        )

        with open(log_file, "w") as f:
            f.write(log_content)

        # Mock glob to return our log file
        with patch.object(Path, "glob") as mock_glob:
            mock_glob.return_value = [log_file]

            logs = orchestrator.get_service_logs("12345")

            assert logs == log_content

    def test_get_service_logs_fallback_to_slurm(self, orchestrator):
        """Test fallback to default SLURM log file"""
        log_content = "SLURM log content"

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", mock_open(read_data=log_content)):
                logs = orchestrator.get_service_logs("12345")

                assert logs == log_content

    def test_get_service_logs_file_not_found(self, orchestrator):
        """Test getting logs when file doesn't exist"""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            logs = orchestrator.get_service_logs("12345")

            assert "Log file not found" in logs

    def test_get_service_logs_read_error(self, orchestrator):
        """Test log retrieval with read error"""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", side_effect=IOError("Read error")):
                logs = orchestrator.get_service_logs("12345")

                assert "Error reading logs" in logs


class TestSlurmOrchestratorMiscellaneous:
    """Tests for miscellaneous orchestrator methods"""

    @pytest.fixture
    def orchestrator(self):
        """Fixture for orchestrator"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            return SlurmOrchestrator()

    def test_scale_service_not_supported(self, orchestrator):
        """Test that scaling is not supported"""
        result = orchestrator.scale_service("12345", replicas=3)
        assert result is False

    def test_check_connection_success(self, orchestrator):
        """Test SLURM connection check success"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = orchestrator.check_connection()

            assert result is True

    def test_check_connection_failure(self, orchestrator):
        """Test SLURM connection check failure"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = orchestrator.check_connection()

            assert result is False

    def test_load_config_success(self, orchestrator):
        """Test successful config loading"""
        config_data = {"slurm": {"account": "p12345", "partition": "gpu"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = orchestrator._load_config(temp_path)
            assert config["account"] == "p12345"
            assert config["partition"] == "gpu"
        finally:
            Path(temp_path).unlink()

    def test_load_config_file_not_found(self, orchestrator):
        """Test config loading with missing file"""
        config = orchestrator._load_config("/nonexistent/config.yml")
        assert config == {}

    def test_load_config_invalid_yaml(self, orchestrator):
        """Test config loading with invalid YAML"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: content:")
            temp_path = f.name

        try:
            config = orchestrator._load_config(temp_path)
            assert config == {}
        finally:
            Path(temp_path).unlink()


class TestSlurmOrchestratorIntegration:
    """Integration tests for SLURM orchestrator"""

    @pytest.fixture
    def orchestrator(self):
        """Fixture for orchestrator"""
        with patch.dict(os.environ, {"SLURM_ACCOUNT": "p12345"}):
            return SlurmOrchestrator()

    @pytest.fixture
    def complex_recipe(self):
        """Fixture for complex recipe with all features"""
        resources = ResourceSpec(
            cpu_cores=4,
            memory_gb=16,
            gpu_count=2,
            gpu_type="nvidia-a100",
            nodes=1,
            ntasks=1,
        )

        ports = [Port(container_port=8080, host_port=8080)]

        volumes = [
            VolumeMount("/host/data", "/data"),
            VolumeMount("/host/models", "/models", readonly=True),
        ]

        return ServiceRecipe(
            name="complex-service",
            image="docker://test/complex:latest",
            resources=resources,
            ports=ports,
            volumes=volumes,
            environment={"MODEL_PATH": "/models", "DATA_PATH": "/data"},
            command=["/bin/bash", "-c", "python train.py"],
        )

    def test_full_deployment_lifecycle(self, orchestrator, complex_recipe):
        """Test complete deployment lifecycle"""
        with patch("subprocess.run") as mock_run:
            # Mock sbatch submission
            mock_run.return_value = Mock(
                returncode=0, stdout="Submitted batch job 12345", stderr=""
            )

            # Deploy service
            job_id = orchestrator.deploy_service(complex_recipe)
            assert job_id == "12345"

            # Mock squeue for status check
            mock_run.return_value = Mock(returncode=0, stdout="RUNNING\n", stderr="")

            # Check status
            status = orchestrator.get_service_status(job_id)
            assert status == ServiceStatus.RUNNING

            # Mock scancel for stop
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            # Stop service
            result = orchestrator.stop_service(job_id)
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
