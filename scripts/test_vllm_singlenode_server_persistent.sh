#!/bin/bash -l
#SBATCH --job-name=vllm-server
#SBATCH --time=02:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=vllm_server_%j.out
#SBATCH --error=vllm_server_%j.err

echo "========================================="
echo "vLLM SERVER (Persistent)"
echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "Date: $(date)"
echo "========================================="

source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0
export PATH="$HOME/.local/bin:$PATH"

cd ~/UBenchAI-Framework

echo "Starting vLLM server..."
echo "Model: facebook/opt-125m"
echo "Note: First run will download model (~500MB)"
echo ""

OUTPUT=$(poetry run ubenchai server start --recipe vllm-singlenode 2>&1)
echo "$OUTPUT"

VLLM_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo ""
echo "vLLM Job ID: $VLLM_JOB_ID"

if [ -z "$VLLM_JOB_ID" ]; then
    echo "ERROR: Could not start server"
    exit 1
fi

echo ""
echo "========================================="
echo "IMPORTANT: Use this job ID for client:"
echo "  export VLLM_SERVER_JOB=$VLLM_JOB_ID"
echo "========================================="

# vLLM needs more time (model loading)
echo "Waiting for server and model initialization (90s)..."
sleep 90

# Get node where it's running
VLLM_NODE=$(squeue -j $VLLM_JOB_ID --format=%R --noheader | tr -d ' ')
echo ""
echo "========================================="
echo "SERVER READY!"
echo "========================================="
echo "Job ID: $VLLM_JOB_ID"
echo "Node: $VLLM_NODE"
echo "URL: http://${VLLM_NODE}:8000"
echo "Model: facebook/opt-125m"
echo "========================================="
echo ""
echo "Test connection with:"
echo "  curl http://${VLLM_NODE}:8000/health"
echo "  curl http://${VLLM_NODE}:8000/v1/models"
echo ""
echo "Test inference:"
echo '  curl -X POST http://'"${VLLM_NODE}"':8000/v1/completions \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"model":"facebook/opt-125m","prompt":"AI is","max_tokens":10}'"'"
echo ""
echo "Stop server with:"
echo "  poetry run ubenchai server stop $VLLM_JOB_ID"
echo ""
echo "Now you can run the client benchmark!"
echo "========================================="

# Monitor server status
echo ""
echo "Keeping monitoring job alive..."
echo "Monitoring vLLM server health..."
echo ""

while true; do
    if squeue -j $VLLM_JOB_ID &>/dev/null; then
        # Check actual health
        HEALTH=$(curl -s --max-time 5 http://${VLLM_NODE}:8000/health 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo "[$(date +%H:%M:%S)] Server running on $VLLM_NODE - Health: OK"
        else
            echo "[$(date +%H:%M:%S)] Server running on $VLLM_NODE - Health: NOT RESPONDING"
        fi
    else
        echo "[$(date +%H:%M:%S)] WARNING: Server job $VLLM_JOB_ID is no longer in queue!"
        break
    fi
    sleep 60
done