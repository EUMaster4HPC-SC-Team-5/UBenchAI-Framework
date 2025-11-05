#!/bin/bash -l
#SBATCH --job-name=test-ollama
#SBATCH --time=00:20:00
#SBATCH --qos=default
#SBATCH --partition=gpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --output=test_ollama_%j.out
#SBATCH --error=test_ollama_%j.err

echo "========================================="
echo "TEST: Ollama LLM Server"
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

# Start Ollama
echo "[1/5] Starting Ollama server..."
OUTPUT=$(poetry run ubenchai server start --recipe ollama-tiny 2>&1)
echo "$OUTPUT"

# Extract Job ID
OLLAMA_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo "Ollama Job ID: $OLLAMA_JOB_ID"

if [ -z "$OLLAMA_JOB_ID" ]; then
    echo "ERROR: Could not extract job ID"
    exit 1
fi

# Wait for server (longer for model download)
echo "[2/5] Waiting for server and model download (3 min)..."
sleep 180

# Check if job still running
if ! squeue -j $OLLAMA_JOB_ID &>/dev/null; then
    echo "WARNING: Job not running anymore. Checking logs..."
    LATEST_LOG=$(ls -t logs/ollama-llm_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "=== Last 30 lines of log ==="
        tail -30 "$LATEST_LOG"
    fi
    echo "TEST 2 FAILED (Job terminated)"
    exit 1
fi

# Get node
OLLAMA_NODE=$(squeue -j $OLLAMA_JOB_ID --format=%R --noheader | tr -d ' ')
echo "Ollama running on: $OLLAMA_NODE"

# Test API
echo "[3/5] Testing API endpoint..."
curl -s http://${OLLAMA_NODE}:11434/api/tags | jq .
echo ""

# Test generation (if working)
echo "[4/5] Testing text generation..."
curl -s http://${OLLAMA_NODE}:11434/api/generate \
  -d '{"model":"tinyllama","prompt":"What is 2+2?","stream":false}' | jq .
echo ""

# Cleanup
echo "[5/5] Stopping Ollama..."
poetry run ubenchai server stop $OLLAMA_JOB_ID

echo "========================================="
echo "TEST COMPLETED"
echo "========================================="