"""
SLURM Orchestrator - Manages services via SLURM job scheduler
"""

import subprocess
import tempfile
import os
from typing import Optional
from loguru import logger

from ubenchai.servers.orchestrator import Orchestrator
from ubenchai.servers.services import ServiceRecipe, ServiceStatus


class SlurmOrchestrator(Orchestrator):
    """
    SLURM orchestrator for HPC cluster job submission and management
    """

    def __init__(
        self,
        partition: str = "cpu",
        account: Optional[str] = None,
        qos: str = "default",
    ):
        """
        Initialize SLURM orchestrator

        Args:
            partition: SLURM partition to use
            account: SLURM account (if required)
            qos: Quality of Service
        """
        self.partition = partition
        self.account = account
        self.qos = qos
        logger.info(f"SlurmOrchestrator initialized (partition={partition})")

    def deploy_service(self, recipe: ServiceRecipe) -> str:
        """
        Deploy a service via SLURM

        Args:
            recipe: ServiceRecipe to deploy

        Returns:
            Job ID as the orchestrator handle

        Raises:
            RuntimeError: If deployment fails
        """
        logger.info(f"Deploying service via SLURM: {recipe.name}")

        # Build SLURM batch script
        script_content = self._build_batch_script(recipe)

        # Submit job
        try:
            job_id = self._submit_job(script_content)
            logger.info(f"Service deployed with SLURM job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to deploy service: {e}")
            raise RuntimeError(f"SLURM deployment failed: {e}")

    def stop_service(self, handle: str) -> bool:
        """
        Stop a service (cancel SLURM job)

        Args:
            handle: SLURM job ID

        Returns:
            True if successful
        """
        logger.info(f"Stopping SLURM job: {handle}")

        try:
            result = subprocess.run(
                ["scancel", handle],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"SLURM job cancelled: {handle}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to cancel job {handle}: {e.stderr}")
            return False

    def get_service_status(self, handle: str) -> ServiceStatus:
        """
        Get service status from SLURM

        Args:
            handle: SLURM job ID

        Returns:
            ServiceStatus
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
            # Job not found - assume stopped
            return ServiceStatus.STOPPED

    def get_service_logs(self, handle: str) -> str:
        """
        Get service logs from SLURM output file

        Args:
            handle: SLURM job ID

        Returns:
            Log contents as string
        """
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
        Scale service (not implemented for SLURM)

        Args:
            handle: SLURM job ID
            replicas: Number of replicas

        Returns:
            False (not supported)
        """
        logger.warning("Scaling not supported for SLURM orchestrator")
        return False

    def _build_batch_script(self, recipe: ServiceRecipe) -> str:
        """
        Build SLURM batch script from recipe

        Args:
            recipe: ServiceRecipe

        Returns:
            Batch script content
        """
        # Build resource requirements
        resources = recipe.resources.to_slurm_resources()

        # Build environment variables
        env_exports = "\n".join(
            [f"export {key}={value}" for key, value in recipe.environment.items()]
        )

        # Build volume bindings for Apptainer
        volume_binds = ""
        if recipe.volumes:
            binds = ",".join(
                [f"{vol.host_path}:{vol.container_path}" for vol in recipe.volumes]
            )
            volume_binds = f"--bind {binds}"

        # Build command
        command = " ".join(recipe.command) if recipe.command else ""

        # Construct script
        script = f"""#!/bin/bash -l

#SBATCH --job-name={recipe.name}
#SBATCH --time=01:00:00
#SBATCH --qos={self.qos}
#SBATCH --partition={self.partition}
"""

        if self.account:
            script += f"#SBATCH --account={self.account}\n"

        script += f"""#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
{resources}

echo "========================================="
echo "SLURM Job Information"
echo "========================================="
echo "Date              = $(date)"
echo "Hostname          = $(hostname -s)"
echo "Working Directory = $(pwd)"
echo "Job ID            = $SLURM_JOB_ID"
echo "Job Name          = {recipe.name}"
echo "========================================="

# Initialize Lmod module system
source /usr/share/lmod/lmod/init/bash

# Load required modules
module load env/release/2024.1
module load Apptainer/1.3.6-GCCcore-13.3.0

# Set environment variables
{env_exports}

# Pull container image if not exists
IMAGE_FILE=$(echo {recipe.image} | sed 's|docker://||' | sed 's|/|_|g' | sed 's|:|_|g').sif
if [ ! -f "$IMAGE_FILE" ]; then
    echo "Pulling container image: {recipe.image}"
    apptainer pull $IMAGE_FILE {recipe.image}
fi

# Run the service
echo "Starting service: {recipe.name}"
apptainer exec --nv {volume_binds} $IMAGE_FILE {command}

echo "Service completed"
"""

        return script

    def _submit_job(self, script_content: str) -> str:
        """
        Submit job to SLURM

        Args:
            script_content: Batch script content

        Returns:
            Job ID

        Raises:
            RuntimeError: If submission fails
        """
        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script_content)
            script_path = f.name

        try:
            # Submit the job
            result = subprocess.run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract job ID from output (format: "Submitted batch job 12345")
            output = result.stdout.strip()
            job_id = output.split()[-1]

            logger.debug(f"sbatch output: {output}")
            return job_id

        except subprocess.CalledProcessError as e:
            logger.error(f"sbatch failed: {e.stderr}")
            raise RuntimeError(f"Job submission failed: {e.stderr}")

        finally:
            # Clean up temporary script
            try:
                os.unlink(script_path)
            except Exception:
                pass

    def check_connection(self) -> bool:
        """
        Check if SLURM is available

        Returns:
            True if SLURM commands are available
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
