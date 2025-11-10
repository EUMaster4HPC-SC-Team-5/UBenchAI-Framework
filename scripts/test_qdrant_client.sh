#!/bin/bash -l
#SBATCH --job-name=client-qdrant
#SBATCH --time=00:20:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=client_qdrant_%j.out
#SBATCH --error=client_qdrant_%j.err

echo "========================================="
echo "CLIENT TEST: Qdrant Vector DB Benchmark"
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

# Check numpy is installed (required for Qdrant)
echo "Verifying numpy installation..."
python3 -c "import numpy; print(f'✓ numpy {numpy.__version__}')" || {
    echo "ERROR: numpy not found. Installing..."
    pip install numpy --break-system-packages
}

# [1/6] Check if Qdrant server is running
echo "[1/6] Checking for running Qdrant server..."

# Use environment variable if set, otherwise search
if [ -n "$QDRANT_SERVER_JOB" ]; then
    QDRANT_JOB=$QDRANT_SERVER_JOB
    echo "Using provided server job ID: $QDRANT_JOB"
else
    # Find by job name (look for the actual service, not wrapper)
    QDRANT_JOB=$(squeue --me --format="%i %j %T" --noheader | \
        grep "qdrant-vectordb" | \
        grep "RUNNING" | \
        awk '{print $1}' | \
        head -n1)
fi

echo "Found Qdrant server: Job ID $QDRANT_JOB"

# [2/6] Get server node
echo "[2/6] Getting server node information..."
QDRANT_NODE=$(squeue -j $QDRANT_JOB --format=%R --noheader | tr -d ' ')

if [ -z "$QDRANT_NODE" ] || [ "$QDRANT_NODE" == "(Resources)" ]; then
    echo "ERROR: Server not yet allocated to a node"
    exit 1
fi

echo "Qdrant server running on: $QDRANT_NODE"

# [3/6] Test server connectivity
echo "[3/6] Testing server connectivity..."
MAX_RETRIES=10
RETRY_COUNT=0
RETRY_DELAY=10

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s --max-time 5 http://${QDRANT_NODE}:6333/collections &>/dev/null; then
        echo "✓ Server is responsive"
        
        # Show available collections
        echo "Available collections:"
        curl -s http://${QDRANT_NODE}:6333/collections | jq '.result.collections[].name' 2>/dev/null || echo "  (jq not available)"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Server not ready, retry $RETRY_COUNT/$MAX_RETRIES... (waiting ${RETRY_DELAY}s)"
        sleep $RETRY_DELAY
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Server not responding after $MAX_RETRIES attempts"
    echo "Server node: $QDRANT_NODE"
    echo "Tried URL: http://${QDRANT_NODE}:6333/collections"
    exit 1
fi

# [4/6] Run client benchmark
echo "[4/6] Starting client benchmark..."
echo "Recipe: qdrant-stress-test"
echo "Operations: search, insert, delete"
echo ""

CLIENT_OUTPUT=$(poetry run ubenchai client run --recipe qdrant-stress-test 2>&1)
echo "$CLIENT_OUTPUT"

# Extract client run ID and SLURM job ID
CLIENT_RUN_ID=$(echo "$CLIENT_OUTPUT" | grep -oP 'Run ID: \K[a-f0-9-]+' || echo "")
CLIENT_JOB_ID=$(echo "$CLIENT_OUTPUT" | grep -oP 'Orchestrator Handle: \K[0-9]+' || echo "")

echo ""
echo "Client Run ID: $CLIENT_RUN_ID"
echo "Client SLURM Job ID: $CLIENT_JOB_ID"

if [ -z "$CLIENT_JOB_ID" ]; then
    echo "WARNING: Could not extract SLURM job ID"
fi

if [ -z "$CLIENT_RUN_ID" ]; then
    echo "WARNING: Could not extract client run ID"
    echo "Checking for any running clients..."
    poetry run ubenchai client list
else
    # [5/6] Monitor client progress
    echo "[5/6] Monitoring client benchmark (max 3 minutes)..."
    
    MAX_WAIT=720  # 3 minutes (Qdrant is fast)
    ELAPSED=0
    CHECK_INTERVAL=5
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        # Check if SLURM job is completed
        JOB_STATE=$(sacct -j $CLIENT_JOB_ID --format=State --noheader 2>/dev/null | head -1 | tr -d ' ')
        
        if [ "$JOB_STATE" = "COMPLETED" ] || [ "$JOB_STATE" = "FAILED" ] || [ "$JOB_STATE" = "CANCELLED" ] || [ "$JOB_STATE" = "TIMEOUT" ]; then
            echo "Client workload job finished with state: $JOB_STATE"
            break
        fi
        
        STATUS=$(poetry run ubenchai client status $CLIENT_RUN_ID 2>&1 || echo "error")
        
        echo ""
        echo "=== Status check (${ELAPSED}s elapsed) ==="
        echo "$STATUS"
        
        # Check if completed
        if echo "$STATUS" | grep -q "completed\|failed\|canceled"; then
            echo "Client benchmark finished"
            break
        fi
        
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "WARNING: Client benchmark timeout after ${MAX_WAIT}s"
    fi
    
    # [6/6] Get final results
    echo "[6/6] Retrieving final results..."
    echo ""
    poetry run ubenchai client status $CLIENT_RUN_ID
    echo ""
    
    # Check for result files
    echo "Looking for result files..."
    RESULT_FILES=$(find results/ -name "*${CLIENT_RUN_ID:0:8}*.json" 2>/dev/null)
    
    if [ -n "$RESULT_FILES" ]; then
        echo "Found result files:"
        echo "$RESULT_FILES"
        echo ""
        echo "=== Results Summary ==="
        for file in $RESULT_FILES; do
            echo "File: $file"
            if command -v jq &>/dev/null; then
                echo "Metrics:"
                jq '.metrics | {total_requests, successful_requests, throughput_rps, latency_mean, latency_p95, latency_p99}' "$file" 2>/dev/null || cat "$file"
            else
                cat "$file"
            fi
            echo ""
        done
    else
        echo "No result files found yet (may still be processing)"
    fi
    
    # Show Qdrant collection status
    echo "=== Qdrant Collection Status ==="
    curl -s http://${QDRANT_NODE}:6333/collections | jq '.' 2>/dev/null || echo "Could not retrieve collections"
fi

echo ""
echo "========================================="
echo "CLIENT TEST COMPLETED"
echo "========================================="
echo "Qdrant Server Job ID: $QDRANT_JOB"
echo "Client Run ID: $CLIENT_RUN_ID"
echo "Node: $(hostname)"
echo "========================================="
echo ""
echo "To view all clients: poetry run ubenchai client list"
echo "To stop server: poetry run ubenchai server stop $QDRANT_JOB"
echo ""
echo "Qdrant Performance Notes:"
echo "  - Expected throughput: 100-500 req/s"
echo "  - Expected latency: < 100ms (P95)"