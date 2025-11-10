#!/bin/bash -l
#SBATCH --job-name=test-vllm
#SBATCH --time=00:30:00
#SBATCH --qos=default
#SBATCH --partition=gpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --output=test_vllm_%j.out
#SBATCH --error=test_vllm_%j.err

echo "========================================="
echo "TEST 3: vLLM Single-Node Server"
echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "========================================="

# Setup environment
source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0
export PATH="$HOME/.local/bin:$PATH"

cd ~/UBenchAI-Framework

# Create cache directory
mkdir -p ~/vllm_cache

# Start vLLM
echo "[1/5] Starting vLLM server..."
OUTPUT=$(poetry run ubenchai server start --recipe vllm-single 2>&1)
echo "$OUTPUT"

# Extract Job ID
VLLM_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo "vLLM Job ID: $VLLM_JOB_ID"

if [ -z "$VLLM_JOB_ID" ]; then
    echo "ERROR: Could not extract job ID"
    exit 1
fi

# Wait for server (longer for model download)
echo "[2/5] Waiting for server and model (2 min)..."
sleep 120

# Check if job still running
if ! squeue -j $VLLM_JOB_ID &>/dev/null; then
    echo "WARNING: Job not running. Checking logs..."
    LATEST_LOG=$(ls -t logs/vllm-single_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        tail -50 "$LATEST_LOG"
    fi
    echo "TEST 3 FAILED"
    exit 1
fi

# Get node
VLLM_NODE=$(squeue -j $VLLM_JOB_ID --format=%R --noheader | tr -d ' ')
echo "vLLM running on: $VLLM_NODE"

# Test health
echo "[3/5] Testing health..."
curl -s http://${VLLM_NODE}:8000/health
echo ""

# List models
echo "[4/5] Listing models..."
curl -s http://${VLLM_NODE}:8000/v1/models | jq .
echo ""

# Test generation
echo "[5/5] Testing completion..."
curl -s http://${VLLM_NODE}:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "facebook/opt-125m",
    "prompt": "AI is",
    "max_tokens": 20
  }' | jq .
echo ""

# Cleanup
echo "Stopping vLLM..."
poetry run ubenchai server stop $VLLM_JOB_ID

echo "========================================="
echo "TEST 3 COMPLETED"
echo "========================================="