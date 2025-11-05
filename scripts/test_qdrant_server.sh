#!/bin/bash -l
#SBATCH --job-name=test-qdrant
#SBATCH --time=00:15:00
#SBATCH --qos=default
#SBATCH --partition=gpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=test_qdrant_%j.out
#SBATCH --error=test_qdrant_%j.err

echo "========================================="
echo "TEST: Qdrant Vector Database"
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

# Start Qdrant
echo "[1/5] Starting Qdrant server..."
OUTPUT=$(poetry run ubenchai server start --recipe qdrant-vectordb 2>&1)
echo "$OUTPUT"

# Extract Job ID
QDRANT_JOB_ID=$(echo "$OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")
echo "Qdrant Job ID: $QDRANT_JOB_ID"

if [ -z "$QDRANT_JOB_ID" ]; then
    echo "ERROR: Could not extract job ID"
    exit 1
fi

# Wait for server
echo "[2/5] Waiting for server to start (30s)..."
sleep 30

# Get node
QDRANT_NODE=$(squeue -j $QDRANT_JOB_ID --format=%R --noheader | tr -d ' ')
echo "Qdrant running on: $QDRANT_NODE"

# Test health
echo "[3/5] Testing health endpoint..."
curl -s http://${QDRANT_NODE}:6333/healthz
echo ""

# Create collection
echo "[4/5] Creating test collection..."
curl -X PUT http://${QDRANT_NODE}:6333/collections/test \
  -H 'Content-Type: application/json' \
  -d '{"vectors": {"size": 384, "distance": "Cosine"}}'
echo ""

# List collections
echo "[5/5] Listing collections..."
curl -s http://${QDRANT_NODE}:6333/collections | jq .
echo ""

# Cleanup
echo "Stopping Qdrant..."
poetry run ubenchai server stop $QDRANT_JOB_ID

echo "========================================="
echo "TEST COMPLETED"
echo "========================================="