"""
ClientOrchestrator - SLURM orchestration for client benchmarks
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from ubenchai.clients.recipes import ClientRecipe
from ubenchai.clients.runs import ClientRun, RunStatus


class ClientOrchestrator:
    """
    Submits and manages benchmarking clients as HPC jobs via SLURM.
    Similar to Server's SlurmOrchestrator but for client workloads.
    """

    def __init__(
        self,
        partition: Optional[str] = None,
        account: Optional[str] = None,
        qos: Optional[str] = None,
        time_limit: Optional[str] = None,
    ):
        """Initialize client orchestrator"""

        # Load from environment or config
        from dotenv import load_dotenv

        load_dotenv()

        self.account = account or os.getenv("SLURM_ACCOUNT")
        self.partition = partition or os.getenv("SLURM_PARTITION", "cpu")
        self.qos = qos or os.getenv("SLURM_QOS", "default")
        self.time_limit = time_limit or os.getenv("SLURM_TIME_LIMIT", "00:30:00")

        if not self.account:
            raise ValueError("SLURM account must be provided")

        logger.info(
            f"ClientOrchestrator: account={self.account}, "
            f"partition={self.partition}, qos={self.qos}"
        )

    def submit(self, run: ClientRun, recipe: ClientRecipe, target_endpoint: str) -> str:
        """
        Submit a client benchmark run to SLURM

        Args:
            run: ClientRun instance
            recipe: ClientRecipe
            target_endpoint: Resolved target endpoint

        Returns:
            Job ID (orchestrator handle)
        """
        logger.info(f"Submitting client run: {run.id} ({recipe.name})")

        # Build SLURM batch script
        script_content = self._build_batch_script(run, recipe, target_endpoint)

        # Submit job
        try:
            job_id = self._submit_job(script_content)
            logger.info(f"Client run submitted with SLURM job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to submit client run: {e}")
            raise RuntimeError(f"SLURM submission failed: {e}")

    def stop(self, handle: str) -> bool:
        """
        Stop a running client (cancel SLURM job)

        Args:
            handle: SLURM job ID

        Returns:
            True if successful
        """
        logger.info(f"Stopping client job: {handle}")

        try:
            subprocess.run(
                ["scancel", handle],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Client job cancelled: {handle}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to cancel job {handle}: {e.stderr}")
            return False

    def status(self, handle: str) -> RunStatus:
        """
        Get client run status from SLURM

        Args:
            handle: SLURM job ID

        Returns:
            RunStatus
        """
        try:
            result = subprocess.run(
                ["squeue", "-j", handle, "--format=%T", "--noheader"],
                capture_output=True,
                text=True,
                check=True,
            )

            slurm_status = result.stdout.strip()

            # Map SLURM status to RunStatus
            status_map = {
                "PENDING": RunStatus.SUBMITTED,
                "RUNNING": RunStatus.RUNNING,
                "COMPLETED": RunStatus.COMPLETED,
                "FAILED": RunStatus.FAILED,
                "CANCELLED": RunStatus.CANCELED,
                "TIMEOUT": RunStatus.FAILED,
            }

            return status_map.get(slurm_status, RunStatus.UNKNOWN)

        except subprocess.CalledProcessError:
            # Job not found - assume completed
            return RunStatus.COMPLETED

    def stdout(self, handle: str) -> str:
        """
        Get client run output

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

    def _build_batch_script(
        self, run: ClientRun, recipe: ClientRecipe, target_endpoint: str
    ) -> str:
        """
        Build SLURM batch script for client run

        Args:
            run: ClientRun
            recipe: ClientRecipe
            target_endpoint: Target endpoint

        Returns:
            Batch script content
        """
        # Get resources from orchestration spec
        resources = recipe.orchestration.resources
        cpu_cores = resources.get("cpu_cores", 1)
        memory_gb = resources.get("memory_gb", 4)

        # Build script
        script = f"""#!/bin/bash -l

#SBATCH --job-name={recipe.name}_{run.id[:8]}
#SBATCH --time={self.time_limit}
#SBATCH --qos={self.qos}
#SBATCH --partition={self.partition}
#SBATCH --account={self.account}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={cpu_cores}
#SBATCH --mem={memory_gb}G

echo "========================================="
echo "UBenchAI Client Run"
echo "========================================="
echo "Date              = $(date)"
echo "Hostname          = $(hostname -s)"
echo "Working Directory = $(pwd)"
echo "Job ID            = $SLURM_JOB_ID"
echo "Run ID            = {run.id}"
echo "Recipe            = {recipe.name}"
echo "Target            = {target_endpoint}"
echo "========================================="

# Load Python module
source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0

# Activate virtual environment (if using Poetry)
cd {os.getcwd()}
export PATH="$HOME/.local/bin:$PATH"

# Run the benchmark client
# TODO: Implement actual benchmark workload generation
echo "Starting benchmark client..."
echo "Pattern: {recipe.workload.pattern}"
echo "Duration: {recipe.workload.duration_seconds}s"
echo "Concurrent users: {recipe.workload.concurrent_users}"

# For now, a simple test with curl
echo "Testing connectivity to target..."
curl -s {target_endpoint}/api/tags || echo "Failed to connect"

# TODO: Generate actual workload based on recipe
# This will be implemented in the next phase

echo "Benchmark completed"
"""

        return script

    def _submit_job(self, script_content: str) -> str:
        """
        Submit job to SLURM

        Args:
            script_content: Batch script content

        Returns:
            Job ID
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

            # Extract job ID
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