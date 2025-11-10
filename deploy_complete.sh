#!/bin/bash
# UBenchAI Complete Deployment Script
# Deploys vLLM service, Prometheus/Grafana monitoring, and runs tests

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VLLM_RECIPE="vllm"
MONITOR_RECIPE="vllm-monitor"
TIMEOUT=300  # 5 minutes timeout for service startup

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}UBenchAI Complete Deployment${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Function to print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for job to be running
wait_for_job() {
    local job_id=$1
    local timeout=$2
    local start_time=$(date +%s)
    
    info "Waiting for job $job_id to be running (timeout: ${timeout}s)..."
    
    while true; do
        # Check timeout
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -ge $timeout ]; then
            error "Timeout waiting for job $job_id"
            return 1
        fi
        
        # Get job status
        local status=$(squeue -j $job_id --format=%T --noheader 2>/dev/null | tr -d ' ')
        
        if [ -z "$status" ]; then
            error "Job $job_id not found in queue"
            return 1
        fi
        
        if [ "$status" = "RUNNING" ]; then
            info "✓ Job $job_id is RUNNING (took ${elapsed}s)"
            return 0
        elif [ "$status" = "PENDING" ]; then
            echo -n "."
            sleep 5
        else
            error "Job $job_id has unexpected status: $status"
            return 1
        fi
    done
}

# Function to get node for a job
get_job_node() {
    local job_id=$1
    local node=$(squeue -j $job_id --format=%N --noheader 2>/dev/null | tr -d ' ')
    echo "$node"
}

# Function to get job ID from ubenchai output
extract_job_id() {
    grep -oP 'Job ID: \K[0-9]+' || grep -oP 'Orchestrator Handle: \K[0-9]+'
}

#############################################
# Step 1: Start vLLM Service
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Step 1: Starting vLLM Service${NC}"
echo -e "${BLUE}=========================================${NC}"

info "Launching vLLM service from recipe: $VLLM_RECIPE"
VLLM_OUTPUT=$(python -m ubenchai server start --recipe $VLLM_RECIPE 2>&1)
echo "$VLLM_OUTPUT"

# Extract job ID
VLLM_JOB_ID=$(echo "$VLLM_OUTPUT" | extract_job_id)

if [ -z "$VLLM_JOB_ID" ]; then
    error "Failed to extract vLLM job ID from output"
    exit 1
fi

info "vLLM Job ID: $VLLM_JOB_ID"

# Wait for vLLM to be running
if ! wait_for_job $VLLM_JOB_ID $TIMEOUT; then
    error "vLLM service failed to start"
    exit 1
fi
echo ""

# Get vLLM node
VLLM_NODE=$(get_job_node $VLLM_JOB_ID)
info "vLLM running on node: $VLLM_NODE"
VLLM_URL="http://${VLLM_NODE}:8000"
info "vLLM endpoint: $VLLM_URL"

#############################################
# Step 2: Start Monitoring Stack
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Step 2: Starting Monitoring Stack${NC}"
echo -e "${BLUE}=========================================${NC}"

info "Launching Prometheus and Grafana for vLLM job $VLLM_JOB_ID"
MONITOR_OUTPUT=$(python -m ubenchai monitor start --recipe $MONITOR_RECIPE --targets $VLLM_JOB_ID 2>&1)
echo "$MONITOR_OUTPUT"

# Extract monitor ID and URLs
MONITOR_ID=$(echo "$MONITOR_OUTPUT" | grep -oP 'Monitor ID: \K[a-f0-9-]+')
PROMETHEUS_URL=$(echo "$MONITOR_OUTPUT" | grep -oP 'Prometheus: \Khttp://[^ ]+')
GRAFANA_URL=$(echo "$MONITOR_OUTPUT" | grep -oP 'Grafana: \Khttp://[^ ]+')

if [ -z "$MONITOR_ID" ]; then
    error "Failed to extract monitor ID from output"
    warn "Continuing without monitoring..."
else
    info "Monitor ID: $MONITOR_ID"
    info "Prometheus: $PROMETHEUS_URL"
    info "Grafana: $GRAFANA_URL"
fi

#############################################
# Step 3: Health Checks
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Step 3: Running Health Checks${NC}"
echo -e "${BLUE}=========================================${NC}"

# Wait a bit for services to fully initialize
info "Waiting 30 seconds for services to fully initialize..."
sleep 30

# Check vLLM health
info "Checking vLLM health endpoint..."
if curl -s -f "$VLLM_URL/health" > /dev/null 2>&1; then
    info "✓ vLLM health check PASSED"
else
    warn "✗ vLLM health check FAILED (service may still be initializing)"
fi

# Check vLLM models endpoint
info "Checking vLLM models endpoint..."
if curl -s -f "$VLLM_URL/v1/models" > /dev/null 2>&1; then
    info "✓ vLLM models endpoint responding"
    curl -s "$VLLM_URL/v1/models" | head -20
else
    warn "✗ vLLM models endpoint not responding yet"
fi

# Check Prometheus
if [ ! -z "$PROMETHEUS_URL" ]; then
    info "Checking Prometheus..."
    if curl -s -f "$PROMETHEUS_URL/-/healthy" > /dev/null 2>&1; then
        info "✓ Prometheus is healthy"
    else
        warn "✗ Prometheus health check failed"
    fi
fi

# Check Grafana
if [ ! -z "$GRAFANA_URL" ]; then
    info "Checking Grafana..."
    if curl -s -f "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
        info "✓ Grafana is healthy"
    else
        warn "✗ Grafana health check failed"
    fi
fi

#############################################
# Step 4: Test vLLM Inference
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Step 4: Testing vLLM Inference${NC}"
echo -e "${BLUE}=========================================${NC}"

info "Sending test inference request to vLLM..."

TEST_PROMPT="Explain what is high-performance computing in one sentence."

# Create test request
TEST_REQUEST=$(cat <<EOF
{
  "model": "mistralai/Mistral-7B-Instruct-v0.2",
  "prompt": "$TEST_PROMPT",
  "max_tokens": 50,
  "temperature": 0.7
}
EOF
)

info "Test prompt: $TEST_PROMPT"
info "Sending request to $VLLM_URL/v1/completions"

RESPONSE=$(curl -s -X POST "$VLLM_URL/v1/completions" \
    -H "Content-Type: application/json" \
    -d "$TEST_REQUEST" 2>&1)

# Check if request succeeded
if echo "$RESPONSE" | grep -q '"text"'; then
    info "✓ Inference test PASSED"
    echo ""
    info "Response:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    warn "✗ Inference test FAILED or still processing"
    echo "$RESPONSE"
fi

#############################################
# Step 5: Summary & Access Instructions
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}=========================================${NC}"

info "All services deployed successfully!"
echo ""

echo -e "${GREEN}Service Information:${NC}"
echo "  vLLM Job ID:     $VLLM_JOB_ID"
echo "  vLLM Node:       $VLLM_NODE"
echo "  vLLM Endpoint:   $VLLM_URL"
echo ""

if [ ! -z "$MONITOR_ID" ]; then
    echo -e "${GREEN}Monitoring Stack:${NC}"
    echo "  Monitor ID:      $MONITOR_ID"
    echo "  Prometheus:      $PROMETHEUS_URL"
    echo "  Grafana:         $GRAFANA_URL"
    echo "  Grafana Login:   admin / admin"
    echo ""
fi

# Extract node names for SSH tunnels
PROMETHEUS_NODE=$(echo "$PROMETHEUS_URL" | grep -oP 'http://\K[^:]+')
PROMETHEUS_PORT=$(echo "$PROMETHEUS_URL" | grep -oP ':(\d+)' | tr -d ':')
GRAFANA_NODE=$(echo "$GRAFANA_URL" | grep -oP 'http://\K[^:]+')
GRAFANA_PORT=$(echo "$GRAFANA_URL" | grep -oP ':(\d+)' | tr -d ':')

echo -e "${GREEN}Access Instructions:${NC}"
echo ""
echo -e "${YELLOW}1. Access vLLM from login node or other compute nodes:${NC}"
echo "   curl $VLLM_URL/health"
echo "   curl $VLLM_URL/v1/models"
echo ""

echo -e "${YELLOW}2. Access Prometheus (from your local machine):${NC}"
if [ ! -z "$PROMETHEUS_NODE" ]; then
    echo "   ${GREEN}ssh -L 9090:${PROMETHEUS_NODE}:${PROMETHEUS_PORT} ${USER}@login.lxp.lu${NC}"
    echo "   Then open: ${GREEN}http://localhost:9090${NC}"
else
    echo "   Prometheus URL not available"
fi
echo ""

echo -e "${YELLOW}3. Access Grafana (from your local machine):${NC}"
if [ ! -z "$GRAFANA_NODE" ]; then
    echo "   ${GREEN}ssh -L 3000:${GRAFANA_NODE}:${GRAFANA_PORT} ${USER}@login.lxp.lu${NC}"
    echo "   Then open: ${GREEN}http://localhost:3000${NC}"
    echo "   Login: ${GREEN}admin / admin${NC}"
else
    echo "   Grafana URL not available"
fi
echo ""

echo -e "${YELLOW}4. Access Both with Single SSH Command:${NC}"
if [ ! -z "$PROMETHEUS_NODE" ] && [ ! -z "$GRAFANA_NODE" ]; then
    echo "   ${GREEN}ssh -L 9090:${PROMETHEUS_NODE}:${PROMETHEUS_PORT} -L 3000:${GRAFANA_NODE}:${GRAFANA_PORT} ${USER}@login.lxp.lu${NC}"
    echo "   Then open:"
    echo "     - Prometheus: ${GREEN}http://localhost:9090${NC}"
    echo "     - Grafana:    ${GREEN}http://localhost:3000${NC}"
fi
echo ""

echo -e "${YELLOW}5. Stop All Services:${NC}"
echo "   python -m ubenchai server stop $VLLM_JOB_ID"
if [ ! -z "$MONITOR_ID" ]; then
    echo "   python -m ubenchai monitor stop $MONITOR_ID"
fi
echo ""

# Save deployment info to file
DEPLOYMENT_FILE="deployment_$(date +%Y%m%d_%H%M%S).txt"
cat > "$DEPLOYMENT_FILE" <<EOF
UBenchAI Deployment Information
Generated: $(date)

vLLM Service:
  Job ID:     $VLLM_JOB_ID
  Node:       $VLLM_NODE
  Endpoint:   $VLLM_URL

Monitoring Stack:
  Monitor ID: $MONITOR_ID
  Prometheus: $PROMETHEUS_URL
  Grafana:    $GRAFANA_URL

SSH Tunnel Commands:
  Prometheus: ssh -L 9090:${PROMETHEUS_NODE}:${PROMETHEUS_PORT} ${USER}@login.lxp.lu
  Grafana:    ssh -L 3000:${GRAFANA_NODE}:${GRAFANA_PORT} ${USER}@login.lxp.lu
  Both:       ssh -L 9090:${PROMETHEUS_NODE}:${PROMETHEUS_PORT} -L 3000:${GRAFANA_NODE}:${GRAFANA_PORT} ${USER}@login.lxp.lu

Web Access:
  Prometheus: http://localhost:9090
  Grafana:    http://localhost:3000 (admin/admin)

Stop Commands:
  vLLM:       python -m ubenchai server stop $VLLM_JOB_ID
  Monitor:    python -m ubenchai monitor stop $MONITOR_ID
EOF

info "Deployment information saved to: $DEPLOYMENT_FILE"

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${BLUE}=========================================${NC}"
