from ubenchai.servers.orchestrator import Orchestrator


class SlurmOrchestrator(Orchestrator):
    pass

# Example of a test file distribute accordingly in this 
#!/usr/bin/env python3
# """
# Submit an Ollama job using subprocess to call sbatch
# No external dependencies required - uses native sbatch command
# """
#
# import subprocess
# import tempfile
# import os
#
# def submit_ollama_job():
#     """Submit a Slurm job to run Ollama with Apptainer"""
#
#     # Define the SBATCH script content
#     script_content = """#!/bin/bash -l
#
# #SBATCH --time=00:05:00
# #SBATCH --qos=default
# #SBATCH --partition=gpu
# #SBATCH --account=p200981
# #SBATCH --nodes=1
# #SBATCH --ntasks=1
# #SBATCH --ntasks-per-node=1
#
# echo "Date              = $(date)"
# echo "Hostname          = $(hostname -s)"
# echo "Working Directory = $(pwd)"
#
# # Initialize Lmod module system
# source /usr/share/lmod/lmod/init/bash
#
# # Load the environment module first (required for module hierarchy)
# module load env/release/2024.1
#
# # Now load Apptainer
# module load Apptainer/1.3.6-GCCcore-13.3.0
#
# # Run the processing
# apptainer pull docker://ollama/ollama
# apptainer exec --nv ollama_latest.sif ollama serve
# """
#
#     # Create a temporary file with the script
#     with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
#         f.write(script_content)
#         script_path = f.name
#
#     try:
#         # Submit the job using sbatch
#         result = subprocess.run(
#             ['sbatch', script_path],
#             capture_output=True,
#             text=True,
#             check=True
#         )
#
#         # Extract job ID from output (format: "Submitted batch job 12345")
#         output = result.stdout.strip()
#         job_id = output.split()[-1]
#
#         print(f"Job submitted successfully!")
#         print(f"Job ID: {job_id}")
#         print(f"Output: {output}")
#
#         return job_id
#
#     except subprocess.CalledProcessError as e:
#         print(f"Error submitting job:")
#         print(f"Return code: {e.returncode}")
#         print(f"stdout: {e.stdout}")
#         print(f"stderr: {e.stderr}")
#         return None
#
#     finally:
#         # Clean up the temporary script file
#         os.unlink(script_path)
#
#
# def check_job_status(job_id):
#     """Check the status of a submitted job"""
#     try:
#         result = subprocess.run(
#             ['squeue', '-j', str(job_id), '--format=%T'],
#             capture_output=True,
#             text=True,
#             check=True
#         )
#         status = result.stdout.strip().split('\n')[-1]
#         return status
#     except subprocess.CalledProcessError:
#         return "NOT_FOUND"
#
#
# def cancel_job(job_id):
#     """Cancel a submitted job"""
#     try:
#         subprocess.run(['scancel', str(job_id)], check=True)
#         print(f"Job {job_id} cancelled successfully")
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"Error cancelling job: {e}")
#         return False
#
#
# if __name__ == "__main__":
#     # Submit the job
#     job_id = submit_ollama_job()
#
#     # Optionally check status
#     if job_id:
#         print(f"\nTo check job status: squeue -j {job_id}")
#         print(f"To cancel job: scancel {job_id}")
#         print(f"Or use the functions: check_job_status({job_id}) or cancel_job({job_id})")
#
