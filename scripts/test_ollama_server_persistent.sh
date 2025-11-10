#!/bin/bash -l
#SBATCH --job-name=ollama-server
#SBATCH --time=02:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --output=ollama_server_%j.out
#SBATCH --error=ollama_server_%j.err

echo "========================================="
echo "OLLAMA SERVER (Persistent)"
echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "========================================="

source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0
export PATH="$HOME/.local/bin:$PATH"

cd ~/UBenchAI-Framework

echo "Starting Ollama server..."
OUTPUT=$(poetry run ubenchai server start --recipe ollama-tiny 2>&1)
echo "$OUTPUT"

OLLAMA_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo ""
echo "Ollama Job ID: $OLLAMA_JOB_ID"

if [ -z "$OLLAMA_JOB_ID" ]; then
    echo "ERROR: Could not start server"
    exit 1
fi

echo ""
echo "========================================="
echo "IMPORTANT: Use this job ID for client:"
echo "  export OLLAMA_SERVER_JOB=$OLLAMA_JOB_ID"
echo "========================================="

# Wait for Ollama (longer - needs to pull model)
echo "Waiting for server initialization (120s)..."
sleep 120

# Get node
OLLAMA_NODE=$(squeue -j $OLLAMA_JOB_ID --format=%R --noheader | tr -d ' ')

if [ -z "$OLLAMA_NODE" ]; then
    echo "ERROR: Could not determine node!"
    echo "Job may have crashed. Check logs:"
    ls -lt logs/ollama-llm_*.log | head -1
    exit 1
fi

echo ""
echo "========================================="
echo "SERVER READY!"
echo "========================================="
echo "Job ID: $OLLAMA_JOB_ID"
echo "Node: $OLLAMA_NODE"
echo "URL: http://${OLLAMA_NODE}:11434"
echo "========================================="
echo ""
echo "Test connection with:"
echo "  curl http://${OLLAMA_NODE}:11434/api/tags"
echo ""
echo "Stop server with:"
echo "  poetry run ubenchai server stop $OLLAMA_JOB_ID"
echo ""
echo "Now you can run the client benchmark!"
echo "========================================="

# Monitor server
echo ""
echo "Keeping monitoring job alive..."
echo "Monitoring Ollama server health..."
echo ""

while true; do
    if squeue -j $OLLAMA_JOB_ID &>/dev/null; then
        # Check health
        HEALTH=$(curl -s --max-time 5 http://${OLLAMA_NODE}:11434/api/tags 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo "[$(date +%H:%M:%S)] Server running on $OLLAMA_NODE - Health: OK"
        else
            echo "[$(date +%H:%M:%S)] Server running on $OLLAMA_NODE - Health: NOT RESPONDING"
        fi
    else
        echo "[$(date +%H:%M:%S)] WARNING: Server job $OLLAMA_JOB_ID is no longer in queue!"
        break
    fi
    sleep 60
done