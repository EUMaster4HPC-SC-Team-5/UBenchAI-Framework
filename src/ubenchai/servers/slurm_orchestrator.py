"""
SLURM Orchestrator - MeluXina Compatible
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import yaml
from loguru import logger

from ubenchai.servers.orchestrator import Orchestrator
from ubenchai.servers.services import ServiceRecipe, ServiceStatus


class SlurmOrchestrator(Orchestrator):
    """
    Uses sbatch for autonomous job submission
    """

    def __init__(
        self,
        partition: Optional[str] = None,
        account: Optional[str] = None,
        qos: Optional[str] = None,
        time_limit: Optional[str] = None,
        config_file: str = "config/slurm.yml",
        log_directory: str = "logs",
    ):
        """
        Initialize SLURM orchestrator with MeluXina configuration

        Args:
            partition: SLURM partition (e.g., 'gpu', 'cpu')
            account: SLURM account ID (e.g., 'p00000')
            qos: Quality of Service (e.g., 'default', 'short')
            time_limit: Job time limit (e.g., '01:00:00')
            config_file: Path to YAML configuration file
            log_directory: Directory for SLURM log files
        """

        # Load dotenv for environment variables
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            logger.debug("python-dotenv not available, skipping .env file")

        # Load configuration from YAML file
        config = self._load_config(config_file)

        # Load configuration from multiple sources (priority order: arg > env > config > default)
        self.account = account or os.getenv("SLURM_ACCOUNT") or config.get("account")
        self.partition = (
            partition or os.getenv("SLURM_PARTITION") or config.get("partition", "gpu")
        )
        self.qos = qos or os.getenv("SLURM_QOS") or config.get("qos", "default")
        self.time_limit = (
            time_limit
            or os.getenv("SLURM_TIME_LIMIT")
            or config.get("time_limit", "01:00:00")
        )

        # MeluXina-specific module configuration
        self.module_env = config.get("module_env", "env/release/2024.1")
        self.apptainer_module = config.get(
            "apptainer_module", "Apptainer/1.3.6-GCCcore-13.3.0"
        )

        self.image_cache_dir = config.get("image_cache", "./")

        # Log directory configuration
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # Validate required configuration
        if not self.account:
            raise ValueError(
                "SLURM account must be provided via:\n"
                "  1. Constructor: account='p00000'\n"
                "  2. Environment: export SLURM_ACCOUNT=p00000\n"
                "  3. .env file: SLURM_ACCOUNT=p00000\n"
                "  4. Config file: config/slurm.yml\n\n"
                "To find your account: sacctmgr show user $USER format=account"
            )

        logger.info(
            f"SlurmOrchestrator initialized: "
            f"account={self.account}, "
            f"partition={self.partition}, "
            f"qos={self.qos}, "
            f"time_limit={self.time_limit}, "
            f"log_directory={self.log_directory}"
            f"image_cache={self.image_cache_dir}"
        )

    def _load_config(self, config_file: str) -> dict:
        """
        Load configuration from YAML file

        Args:
            config_file: Path to YAML configuration file

        Returns:
            Dictionary with configuration values
        """
        config_path = Path(config_file)

        if not config_path.exists():
            logger.debug(f"Config file not found: {config_file}")
            return {}

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get("slurm", {})
        except Exception as e:
            logger.warning(f"Failed to load config {config_file}: {e}")
            return {}

    def _generate_log_filename(self, recipe: ServiceRecipe) -> str:
        """
        Generate a unique log filename based on service name and timestamp

        Args:
            recipe: ServiceRecipe containing service name

        Returns:
            Log filename (e.g., "qdrant-vectordb_20251012_113045_a3f8b2.log")
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Generate a short unique ID (first 6 chars of a UUID-like string)
        import uuid

        unique_id = str(uuid.uuid4())[:6]

        return f"{recipe.name}_{timestamp}_{unique_id}.log"

    def deploy_service(self, recipe: ServiceRecipe) -> str:
        """
        Deploy a service via SLURM sbatch submission

        Args:
            recipe: ServiceRecipe containing deployment configuration

        Returns:
            Job ID as the orchestrator handle

        Raises:
            RuntimeError: If deployment fails
        """
        logger.info(f"Deploying service via SLURM: {recipe.name}")

        # Generate log filename
        log_filename = self._generate_log_filename(recipe)
        log_filepath = self.log_directory / log_filename

        # Build SLURM batch script with custom output file
        script_content = self._build_batch_script(recipe, str(log_filepath))

        logger.debug("Generated SLURM batch script:")
        logger.debug("-" * 80)
        logger.debug(script_content)
        logger.debug("-" * 80)

        # Submit job via sbatch
        try:
            job_id = self._submit_job(script_content)
            logger.info(f"Service deployed successfully - Job ID: {job_id}")
            logger.info(f"Log file: {log_filepath}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to deploy service: {e}")
            raise RuntimeError(f"SLURM deployment failed: {e}")

    def stop_service(self, handle: str) -> bool:
        """
        Stop a service by cancelling the SLURM job

        Args:
            handle: SLURM job ID

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Stopping SLURM job: {handle}")

        try:
            subprocess.run(
                ["scancel", handle],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"SLURM job cancelled successfully: {handle}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to cancel job {handle}: {e.stderr}")
            return False

    def get_service_status(self, handle: str) -> ServiceStatus:
        """
        Get service status from SLURM queue

        Args:
            handle: SLURM job ID

        Returns:
            ServiceStatus enum value
        """
        try:
            result = subprocess.run(
                ["squeue", "-j", handle, "--format=%T", "--noheader"],
                capture_output=True,
                text=True,
                check=True,
            )

            slurm_status = result.stdout.strip()

            # Map SLURM status to ServiceStatus
            status_map = {
                "PENDING": ServiceStatus.PENDING,
                "RUNNING": ServiceStatus.RUNNING,
                "COMPLETED": ServiceStatus.STOPPED,
                "FAILED": ServiceStatus.ERROR,
                "CANCELLED": ServiceStatus.STOPPED,
                "TIMEOUT": ServiceStatus.ERROR,
            }

            return status_map.get(slurm_status, ServiceStatus.UNKNOWN)

        except subprocess.CalledProcessError:
            # Job not found in queue - assume stopped/completed
            return ServiceStatus.STOPPED

    def get_service_logs(self, handle: str) -> str:
        """
        Get service logs from SLURM output file

        Args:
            handle: SLURM job ID

        Returns:
            Log contents as string
        """
        # Try to find log file in logs directory
        log_pattern = f"*_{handle}.log"
        matching_logs = list(self.log_directory.glob(log_pattern))

        if matching_logs:
            log_file = matching_logs[0]
            try:
                with open(log_file, "r") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read log file {log_file}: {e}")
                return f"Error reading log file: {e}"

        # Fall back to default slurm output file
        log_file = f"slurm-{handle}.out"
        try:
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    return f.read()
            else:
                return f"Log file not found: {log_file}"
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            return f"Error reading logs: {e}"

    def scale_service(self, handle: str, replicas: int) -> bool:
        """
        Scale service (not supported for SLURM batch jobs)

        Args:
            handle: SLURM job ID
            replicas: Number of replicas (ignored)

        Returns:
            False (not supported)
        """
        logger.warning("Scaling not supported for SLURM orchestrator")
        return False

    def _build_batch_script(self, recipe: ServiceRecipe, log_filepath: str) -> str:
        """
        Build SLURM batch script with custom log file location

        Args:
            recipe: ServiceRecipe containing all configuration
            log_filepath: Full path to the log file

        Returns:
            Complete SLURM batch script as string
        """

        # Build GPU SBATCH directive and apptainer flag
        gpu_sbatch = ""
        gpu_flag = ""
        if recipe.resources.gpu_count > 0:
            gpu_sbatch = f"#SBATCH --gres=gpu:{recipe.resources.gpu_count}"
            gpu_flag = "--nv"  # Enable NVIDIA GPU support

        # Build volume bindings
        volume_binds = []
        mkdir_commands = []

        if recipe.volumes:
            for vol in recipe.volumes:
                host_path = vol.host_path
                volume_binds.append(f"{host_path}:{vol.container_path}")
                mkdir_commands.append(f"mkdir -p {host_path}")

            # Add /mnt/tier1 for scratch access (MeluXina requirement)
            volume_binds.append("/mnt/tier1")

        bind_flag = f"--bind {','.join(volume_binds)}" if volume_binds else ""
        mkdir_section = (
            "\n".join(mkdir_commands)
            if mkdir_commands
            else "# No directories to create"
        )

        # Build environment variables with APPTAINERENV_ prefix
        env_exports = []
        for key, value in recipe.environment.items():
            env_exports.append(f'export APPTAINERENV_{key}="{value}"')
        env_section = (
            "\n".join(env_exports) if env_exports else "# No environment variables"
        )

        # Extract command from recipe
        if recipe.command and len(recipe.command) >= 3 and recipe.command[1] == "-c":
            container_script = recipe.command[2]
        elif recipe.command:
            container_script = " ".join(recipe.command)
        else:
            container_script = 'echo "No command specified in recipe"'

        # Generate the complete SLURM batch script
        script = f"""#!/bin/bash -l

#SBATCH --job-name={recipe.name}
#SBATCH --output={log_filepath}
#SBATCH --error={log_filepath}
#SBATCH --time={self.time_limit}
#SBATCH --partition={self.partition}
#SBATCH --qos={self.qos}
#SBATCH --account={self.account}
#SBATCH --nodes={recipe.resources.nodes}
#SBATCH --ntasks={recipe.resources.ntasks}
#SBATCH --cpus-per-task={recipe.resources.cpu_cores}
#SBATCH --mem={recipe.resources.memory_gb}G
{gpu_sbatch}

echo "========================================="
echo "SLURM Job Information"
echo "========================================="
echo "Job ID:     $SLURM_JOB_ID"
echo "Job Name:   {recipe.name}"
echo "Node:       $(hostname)"
echo "Date:       $(date)"
echo "Account:    {self.account}"
echo "Partition:  {self.partition}"
echo "CPUs:       {recipe.resources.cpu_cores}"
echo "Memory:     {recipe.resources.memory_gb}G"
echo "GPUs:       {recipe.resources.gpu_count}"
echo "Log File:   {log_filepath}"
echo "========================================="

# Initialize Lmod module system (required on MeluXina)
source /usr/share/lmod/lmod/init/bash

# Load required modules
echo "Loading modules..."
module load {self.module_env}
module load {self.apptainer_module}

# Verify Apptainer is available
if ! command -v apptainer &> /dev/null; then
    echo "ERROR: Apptainer not found after module load"
    exit 1
fi

echo "[OK] Apptainer: $(apptainer --version)"

# Prepare volume mount directories on host
echo "Preparing host directories..."
{mkdir_section}

# Set environment variables for container
echo "Setting environment variables..."
{env_section}

# Set up container image cache directory
IMAGE_CACHE_DIR="{self.image_cache_dir}"
mkdir -p "$IMAGE_CACHE_DIR"
echo "Container cache directory: $IMAGE_CACHE_DIR"

# Pull container image if not exists (caching for efficiency)
IMAGE_NAME=$(echo "{recipe.image}" | sed 's|docker://||' | sed 's|/|_|g' | sed 's|:|_|g')
IMAGE_FILE="${{IMAGE_CACHE_DIR}}/${{IMAGE_NAME}}.sif"

if [ ! -f "$IMAGE_FILE" ]; then
    echo "Pulling container image: {recipe.image}"
    apptainer pull "$IMAGE_FILE" "{recipe.image}"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to pull container image"
        exit 1
    fi
    echo "[OK] Container image pulled: $IMAGE_FILE"
else
    echo "[OK] Using cached container: $IMAGE_FILE"
fi

# Create startup script that will run inside the container
CONTAINER_SCRIPT="/tmp/container_startup_${{SLURM_JOB_ID}}.sh"
cat > "$CONTAINER_SCRIPT" << 'CONTAINER_SCRIPT_EOF'
{container_script}
CONTAINER_SCRIPT_EOF

chmod +x "$CONTAINER_SCRIPT"

echo ""
echo "========================================="
echo "Starting Service in Container"
echo "========================================="

# Run the service inside Apptainer container
apptainer exec \\
    {gpu_flag} \\
    {bind_flag} \\
    "$IMAGE_FILE" \\
    /bin/bash "$CONTAINER_SCRIPT"

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Job Completed"
echo "========================================="
echo "Exit Code: $EXIT_CODE"
echo "Job ID:    $SLURM_JOB_ID"
echo "End Time:  $(date)"
echo "Log File:  {log_filepath}"
echo "========================================="

# Cleanup temporary files
rm -f "$CONTAINER_SCRIPT"

exit $EXIT_CODE
"""

        return script

    def _submit_job(self, script_content: str) -> str:
        """
        Submit job to SLURM using sbatch

        Args:
            script_content: Complete batch script content

        Returns:
            Job ID as string

        Raises:
            RuntimeError: If submission fails
        """
        # Create temporary script file with UTF-8 encoding
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8"
        ) as f:
            f.write(script_content)
            script_path = f.name

        try:
            # Submit the job with sbatch
            result = subprocess.run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract job ID from output
            output = result.stdout.strip()
            job_id = output.split()[-1]

            logger.debug(f"sbatch output: {output}")
            logger.info(f"Job submitted successfully: {job_id}")

            return job_id

        except subprocess.CalledProcessError as e:
            logger.error(f"sbatch failed: {e.stderr}")
            raise RuntimeError(f"Job submission failed: {e.stderr}")

        finally:
            # Clean up temporary script file
            try:
                os.unlink(script_path)
            except Exception:
                pass

    def check_connection(self) -> bool:
        """
        Check if SLURM is available and accessible

        Returns:
            True if SLURM commands are available, False otherwise
        """
        try:
            subprocess.run(
                ["squeue", "--version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
