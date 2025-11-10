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


"""
ClientOrchestrator - SLURM orchestration for client benchmarks
"""

import subprocess
import tempfile
import os
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
        Submit a client benchmark run to SLURM.

        Args:
            run: ClientRun instance
            recipe: ClientRecipe
            target_endpoint: Resolved target endpoint

        Returns:
            Job ID (orchestrator handle)
        """
        logger.info(f"Submitting client run: {run.id} ({recipe.name})")

        script_content = self._build_batch_script(run, recipe, target_endpoint)

        try:
            job_id = self._submit_job(script_content)
            logger.info(f"Client run submitted with SLURM job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to submit client run: {e}")
            raise RuntimeError(f"SLURM submission failed: {e}")

    def stop(self, handle: str) -> bool:
        """
        Stop a running client (cancel SLURM job).

        Args:
            handle: SLURM job ID
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
        Get client run status from SLURM.

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
        Get client run output from SLURM log file.
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
        Build SLURM batch script for client run.
        """
        resources = recipe.orchestration.resources
        cpu_cores = resources.get("cpu_cores", 1)
        memory_gb = resources.get("memory_gb", 4)

        workload_cmd = self._build_workload_command(recipe, target_endpoint, run)

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
echo "UBenchAI Client Benchmark"
echo "========================================="
echo "Date              = $(date)"
echo "Hostname          = $(hostname -s)"
echo "Working Directory = $(pwd)"
echo "Job ID            = $SLURM_JOB_ID"
echo "Run ID            = {run.id}"
echo "Recipe            = {recipe.name}"
echo "Target            = {target_endpoint}"
echo "========================================="

# Load Python environment
source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0

# Navigate to project directory
cd {os.getcwd()}

# Activate Poetry environment
export PATH="$HOME/.local/bin:$PATH"
eval $(poetry env activate)

# Create output directory
OUTPUT_DIR="{run.artifacts_dir or './results'}"
mkdir -p "$OUTPUT_DIR"

# Run benchmark workload
echo ""
echo "Starting benchmark workload..."
{workload_cmd}

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Benchmark Completed"
echo "========================================="
echo "Exit Code: $EXIT_CODE"
echo "Results:   $OUTPUT_DIR"
echo "========================================="

exit $EXIT_CODE
"""
        return script

    def _build_workload_command(
        self, recipe: ClientRecipe, target_endpoint: str, run: ClientRun
    ) -> str:
        """
        Build the CLI command for the Python workload generator (multi-service).
        """
        output_dir = run.artifacts_dir or "./results"
        output_file = f"{output_dir}/{recipe.name}_{run.id[:8]}_results.json"

        # Workload parameters
        pattern = recipe.workload.pattern
        duration = recipe.workload.duration_seconds
        concurrent_users = recipe.workload.concurrent_users
        think_time = recipe.workload.think_time_ms

        # Deduce service type
        service_type = "ollama"
        if recipe.target.service:
            s = recipe.target.service.lower()
            if "qdrant" in s:
                service_type = "qdrant"
            elif "vllm" in s:
                service_type = "vllm"
            elif "ollama" in s:
                service_type = "ollama"
        else:
            n = recipe.name.lower()
            if "qdrant" in n:
                service_type = "qdrant"
            elif "vllm" in n:
                service_type = "vllm"

        # Dataset / model
        prompt_length = recipe.dataset.params.get("prompt_length", 50)
        model_name = recipe.dataset.params.get("model_name", "tinyllama")

        parts = [
            "python -m ubenchai.clients.workload_generator",
            f'--endpoint "{target_endpoint}"',
            f'--service-type "{service_type}"',
            f'--model "{model_name}"',
            f'--pattern "{pattern}"',
            f"--duration {duration}",
            f"--concurrent-users {concurrent_users}",
            f"--think-time {think_time}",
            f"--prompt-length {prompt_length}",
            f'--output "{output_file}"',
        ]

        # Open-loop specific
        rps = getattr(recipe.workload, "requests_per_second", None)
        if pattern == "open-loop" and rps:
            parts.append(f"--requests-per-second {rps}")

        # Qdrant-specific
        if service_type == "qdrant":
            operation = recipe.dataset.params.get("operation", "search")
            parts.append(f"--operation {operation}")

        cmd = " \\\n    ".join(parts)
        return cmd

    def _submit_job(self, script_content: str) -> str:
        """
        Submit job to SLURM.

        Args:
            script_content: Batch script content

        Returns:
            Job ID
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script_content)
            script_path = f.name

        try:
            result = subprocess.run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=True,
            )

            output = result.stdout.strip()
            job_id = output.split()[-1]

            logger.debug(f"sbatch output: {output}")
            return job_id

        except subprocess.CalledProcessError as e:
            logger.error(f"sbatch failed: {e.stderr}")
            raise RuntimeError(f"Job submission failed: {e.stderr}")
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
