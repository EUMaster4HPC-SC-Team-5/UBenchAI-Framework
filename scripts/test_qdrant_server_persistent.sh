#!/bin/bash -l
#SBATCH --job-name=qdrant-server
#SBATCH --time=01:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=qdrant_server_%j.out
#SBATCH --error=qdrant_server_%j.err

echo "========================================="
echo "QDRANT SERVER (Persistent)"
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

echo "Starting Qdrant server..."
OUTPUT=$(poetry run ubenchai server start --recipe qdrant-vectordb 2>&1)
echo "$OUTPUT"

QDRANT_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo ""
echo "Qdrant Job ID: $QDRANT_JOB_ID"

if [ -z "$QDRANT_JOB_ID" ]; then
    echo "ERROR: Could not start server"
    exit 1
fi
# Nel wrapper, dopo aver ottenuto QDRANT_JOB_ID
echo ""
echo "========================================="
echo "IMPORTANT: Use this job ID for client:"
echo "  export QDRANT_SERVER_JOB=$QDRANT_JOB_ID"
echo "========================================="

# Wait for server to be ready
echo "Waiting for server initialization (45s)..."
sleep 45

# Get node where it's running
QDRANT_NODE=$(squeue -j $QDRANT_JOB_ID --format=%R --noheader | tr -d ' ')
echo ""
echo "========================================="
echo "SERVER READY!"
echo "========================================="
echo "Job ID: $QDRANT_JOB_ID"
echo "Node: $QDRANT_NODE"
echo "URL: http://${QDRANT_NODE}:6333"
echo "========================================="
echo ""
echo "Test connection with:"
echo "  curl http://${QDRANT_NODE}:6333/healthz"
echo ""
echo "Stop server with:"
echo "  poetry run ubenchai server stop $QDRANT_JOB_ID"
echo ""
echo "Now you can run the client benchmark!"
echo "========================================="

# Keep job alive (server runs as separate SLURM job)
echo ""
echo "Keeping monitoring job alive..."
echo "Press Ctrl+C or cancel job $SLURM_JOB_ID to stop monitoring"
echo "(Note: This won't stop the Qdrant server itself)"
echo ""

# Monitor server status every 60 seconds
while true; do
    if squeue -j $QDRANT_JOB_ID &>/dev/null; then
        echo "[$(date +%H:%M:%S)] Server still running on $QDRANT_NODE"
    else
        echo "[$(date +%H:%M:%S)] WARNING: Server job $QDRANT_JOB_ID is no longer in queue!"
        break
    fi
    sleep 60
done