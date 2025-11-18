#!/bin/bash -l
#SBATCH --job-name=client-vllm
#SBATCH --time=00:40:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --output=client_vllm_%j.out
#SBATCH --error=client_vllm_%j.err

echo "========================================="
echo "CLIENT TEST: vLLM Inference Benchmark"
echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================="

# Setup environment
source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0
export PATH="$HOME/.local/bin:$PATH"

cd ~/UBenchAI-Framework

# [1/6] Check if vLLM server is running
echo "[1/6] Checking for running vLLM server..."

# Find the actual vLLM service job (vllm-sin* or vllm-single*)
# Exclude both wrapper and client
VLLM_JOB=$(squeue --me --format="%i %j %T" --noheader | \
    grep -E "vllm-sin" | \
    grep -v "vllm-server" | \
    grep -v "client-vllm" | \
    grep "RUNNING" | \
    awk '{print $1}' | \
    head -n1)

if [ -z "$VLLM_JOB" ]; then
    echo "ERROR: No running vLLM server found!"
    echo ""
    echo "Current queue:"
    squeue --me --format="%i %j %T %R"
    echo ""
    echo "Looking for: vllm-sin* (vLLM service job)"
    exit 1
fi

echo "Found vLLM server: Job ID $VLLM_JOB"

# [2/6] Verify server is still running
echo "[2/6] Verifying server status..."
if ! squeue -j $VLLM_JOB &>/dev/null; then
    echo "ERROR: vLLM server job not running"
    echo "Checking logs..."
    LATEST_LOG=$(ls -t logs/vllm-single_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "=== Last 50 lines of log ==="
        tail -50 "$LATEST_LOG"
    fi
    exit 1
fi

VLLM_NODE=$(squeue -j $VLLM_JOB --format=%R --noheader | tr -d ' ')
echo "vLLM server running on: $VLLM_NODE"

# [3/6] Test server connectivity
echo "[3/6] Testing server connectivity..."
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Test health endpoint
    HEALTH_CHECK=$(curl -s --max-time 5 http://${VLLM_NODE}:8000/health 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "✓ Server health check passed"
        echo "Health status: $HEALTH_CHECK"
        
        # Test models endpoint
        MODELS=$(curl -s --max-time 5 http://${VLLM_NODE}:8000/v1/models 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo "✓ Models endpoint accessible"
            echo "Available models:"
            echo "$MODELS" | jq '.data[].id' 2>/dev/null || echo "  (Could not parse models)"
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Server not ready, retry $RETRY_COUNT/$MAX_RETRIES (waiting 20s)..."
    sleep 20
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Server not responding after $MAX_RETRIES attempts"
    echo "Checking vLLM logs..."
    LATEST_LOG=$(ls -t logs/vllm-single_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "=== Last 30 lines of log ==="
        tail -30 "$LATEST_LOG"
    fi
    exit 1
fi

# Test inference capability
echo "Testing inference capability..."
TEST_RESPONSE=$(curl -s --max-time 30 http://${VLLM_NODE}:8000/v1/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"facebook/opt-125m","prompt":"AI is","max_tokens":10}' 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✓ Inference test successful"
    echo "Response: $TEST_RESPONSE" | jq '.choices[0].text' 2>/dev/null || echo "  (Could not parse response)"
else
    echo "WARNING: Inference test failed, but proceeding with benchmark"
fi

# [4/6] Run client benchmark
echo "[4/6] Starting client benchmark..."
echo "Recipe: vllm-stress-test"
echo "Model: facebook/opt-125m"
echo "Duration: 120 seconds"
echo ""

CLIENT_OUTPUT=$(poetry run ubenchai client run --recipe vllm-stress-test2 2>&1)
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
    echo "[5/6] Monitoring client benchmark (max 10 minutes)..."
    
    MAX_WAIT=600  # 10 minutes (vLLM can be slow)
    ELAPSED=0
    CHECK_INTERVAL=15
    
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
                echo "Key Metrics:"
                jq '.metrics | {total_requests, successful_requests, success_rate, throughput_rps, latency_mean, latency_p95, latency_p99}' "$file" 2>/dev/null || cat "$file"
            else
                cat "$file"
            fi
            echo ""
        done
    else
        echo "No result files found yet (may still be processing)"
    fi
fi

echo ""
echo "========================================="
echo "CLIENT TEST COMPLETED"
echo "========================================="
echo "vLLM Server Job ID: $VLLM_JOB"
echo "Client Run ID: $CLIENT_RUN_ID"
echo "Node: $(hostname)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================="
echo ""
echo "To view all clients: poetry run ubenchai client list"
echo "To stop server: poetry run ubenchai server stop $VLLM_JOB"
echo ""
echo "vLLM Performance Notes:"
echo "  - Expected throughput: 10-20 req/s"
echo "  - Expected latency: 2-5s (P95)"
echo "  - GPU utilization is key for performance"