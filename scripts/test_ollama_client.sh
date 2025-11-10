#!/bin/bash -l
#SBATCH --job-name=client-ollama
#SBATCH --time=00:30:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=client_ollama_%j.out
#SBATCH --error=client_ollama_%j.err

echo "========================================="
echo "CLIENT TEST: Ollama LLM Benchmark"
echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================="

# Setup ambiente
source /usr/share/lmod/lmod/init/bash
module load env/release/2024.1
module load Python/3.12.3-GCCcore-13.3.0
export PATH="$HOME/.local/bin:$PATH"

cd ~/UBenchAI-Framework

# [1/6] Check if Ollama server is running
echo "[1/6] Checking for running Ollama server..."

# Trova il job del servizio Ollama (NON wrapper, NON client)
OLLAMA_JOB=$(squeue --me --format="%i %j %T" --noheader | \
    grep "ollama-" | \
    grep -v "ollama-server" | \
    grep -v "client-ollama" | \
    grep "RUNNING" | \
    awk '{print $1}' | \
    head -n1)

if [ -z "$OLLAMA_JOB" ]; then
    echo "ERROR: No running Ollama server found!"
    echo ""
    echo "Current queue:"
    squeue --me --format="%i %j %T %R"
    echo ""
    echo "Please start the server first, e.g.:"
    echo "  sbatch ollama_server_persistent.sh"
    exit 1
fi

echo "Found Ollama server: Job ID $OLLAMA_JOB"

# [2/6] Verify server job status
echo "[2/6] Verifying server status..."
if ! squeue -j "$OLLAMA_JOB" &>/dev/null; then
    echo "ERROR: Ollama server job not running"
    exit 1
fi

OLLAMA_NODE=$(squeue -j "$OLLAMA_JOB" --format=%R --noheader | tr -d ' ')
echo "Ollama server running on: $OLLAMA_NODE"

# [3/6] Test connectivity & models
echo "[3/6] Testing server connectivity..."
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    RESPONSE=$(curl -s --max-time 5 "http://${OLLAMA_NODE}:11434/api/tags" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
        echo "✓ Server health check passed"

        if echo "$RESPONSE" | grep -q '"models"' ; then
            echo "✓ Models endpoint accessible"
            echo "Raw /api/tags response:"
            echo "$RESPONSE"
            break
        else
            echo "⚠ Server responding, but /api/tags has unexpected format"
            echo "Raw response:"
            echo "$RESPONSE"
        fi
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Server not ready, retry $RETRY_COUNT/$MAX_RETRIES (waiting 15s)..."
    sleep 15
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Server not responding after $MAX_RETRIES attempts"
    exit 1
fi

# Test inferenza base
echo "Testing inference capability..."
TEST_RESPONSE=$(curl -s --max-time 30 "http://${OLLAMA_NODE}:11434/api/generate" \
    -H 'Content-Type: application/json' \
    -d '{"model":"tinyllama","prompt":"AI is","stream":false,"options":{"num_predict":10}}' 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$TEST_RESPONSE" ]; then
    echo "✓ Inference test request sent"
    if command -v jq &>/dev/null; then
        echo "Sample response snippet:"
        echo "$TEST_RESPONSE" | jq '.response' 2>/dev/null || echo "$TEST_RESPONSE"
    else
        echo "Raw response:"
        echo "$TEST_RESPONSE"
    fi
else
    echo "WARNING: Inference test failed, but proceeding with benchmark"
fi

# [4/6] Run benchmark via UBenchAI client
echo "[4/6] Starting client benchmark..."
echo "Recipe: ollama-stress-test"
echo ""

CLIENT_OUTPUT=$(poetry run ubenchai client run --recipe ollama-stress-test 2>&1)
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

    MAX_WAIT=600
    ELAPSED=0
    CHECK_INTERVAL=15

    while [ $ELAPSED -lt $MAX_WAIT ]; do
        # Check if SLURM job is completed
        JOB_STATE=$(sacct -j $CLIENT_JOB_ID --format=State --noheader 2>/dev/null | head -1 | tr -d ' ')
        
        if [ "$JOB_STATE" = "COMPLETED" ] || [ "$JOB_STATE" = "FAILED" ] || [ "$JOB_STATE" = "CANCELLED" ] || [ "$JOB_STATE" = "TIMEOUT" ]; then
            echo "Client workload job finished with state: $JOB_STATE"
            break
        fi
        STATUS=$(poetry run ubenchai client status "$CLIENT_RUN_ID" 2>&1 || echo "error")

        echo ""
        echo "=== Status check (${ELAPSED}s elapsed) ==="
        echo "$STATUS"

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

    # [6/6] Results + JSON completi
    echo "[6/6] Retrieving final results..."
    echo ""
    poetry run ubenchai client status "$CLIENT_RUN_ID"
    echo ""

    echo "Looking for result files..."
    RESULT_FILES=$(find results/ -name "*${CLIENT_RUN_ID:0:8}*.json" 2>/dev/null)

    if [ -n "$RESULT_FILES" ]; then
        echo "Found result files:"
        echo "$RESULT_FILES"
        echo ""
        echo "=== Results Summary (full JSON) ==="
        for file in $RESULT_FILES; do
            echo "File: $file"
            if command -v jq &>/dev/null; then
                # Stampa SOLO le metriche principali più leggibili…
                echo "Key metrics:"
                jq '.metrics | {total_requests, successful_requests, failed_requests, success_rate, throughput_rps, latency_min, latency_mean, latency_p95, latency_p99, latency_max}' "$file" 2>/dev/null || cat "$file"
                echo ""
                echo "Full JSON:"
                jq '.' "$file" 2>/dev/null || cat "$file"
            else
                # …oppure tutto il JSON grezzo
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
echo "Ollama Server Job ID: $OLLAMA_JOB"
echo "Client Run ID: $CLIENT_RUN_ID"
echo "Node: $(hostname)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================="
echo ""
echo "To view all clients: poetry run ubenchai client list"
echo "To stop server: poetry run ubenchai server stop $OLLAMA_JOB"
echo ""
echo "Ollama Performance Notes:"
echo "  - Expected throughput: decine req/s (TinyLlama)"
echo "  - Expected latency: < 1–2s (P95, a seconda del carico)"