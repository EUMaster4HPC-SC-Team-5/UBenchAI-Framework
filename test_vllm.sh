#!/bin/bash
# vLLM Comprehensive Testing Script
# Tests various endpoints and inference scenarios

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <vllm-url>"
    echo "Example: $0 http://mel0123:8000"
    exit 1
fi

VLLM_URL=$1

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}vLLM Comprehensive Testing${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "Target: $VLLM_URL"
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "${BLUE}[TEST]${NC} $test_name"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
    echo ""
}

#############################################
# Test 1: Health Check
#############################################

test_health() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$VLLM_URL/health" 2>&1)
    [ "$response" = "200" ]
}

run_test "Health Endpoint" "test_health"
echo ""

#############################################
# Test 2: Models Endpoint
#############################################

test_models() {
    local response=$(curl -s "$VLLM_URL/v1/models" 2>&1)
    echo "$response" | grep -q '"object".*"list"'
}

run_test "Models Endpoint" "test_models"
if [ $? -eq 0 ]; then
    echo "Available models:"
    curl -s "$VLLM_URL/v1/models" | python3 -m json.tool 2>/dev/null | grep '"id"' | head -5
fi
echo ""

#############################################
# Test 3: Simple Completion
#############################################

test_simple_completion() {
    local request='{"model":"mistralai/Mistral-7B-Instruct-v0.2","prompt":"Hello, world!","max_tokens":10}'
    local response=$(curl -s -X POST "$VLLM_URL/v1/completions" \
        -H "Content-Type: application/json" \
        -d "$request" 2>&1)
    echo "$response" | grep -q '"text"'
}

run_test "Simple Completion" "test_simple_completion"
echo ""

#############################################
# Test 4: Completion with Parameters
#############################################

test_completion_with_params() {
    local request=$(cat <<EOF
{
  "model": "mistralai/Mistral-7B-Instruct-v0.2",
  "prompt": "What is the capital of France?",
  "max_tokens": 50,
  "temperature": 0.7,
  "top_p": 0.9
}
EOF
)
    local response=$(curl -s -X POST "$VLLM_URL/v1/completions" \
        -H "Content-Type: application/json" \
        -d "$request" 2>&1)
    
    echo "$response" | grep -q '"text"'
}

run_test "Completion with Parameters" "test_completion_with_params"
if [ $? -eq 0 ]; then
    echo "Response preview:"
    curl -s -X POST "$VLLM_URL/v1/completions" \
        -H "Content-Type: application/json" \
        -d '{"model":"mistralai/Mistral-7B-Instruct-v0.2","prompt":"What is the capital of France?","max_tokens":50}' \
        | python3 -m json.tool 2>/dev/null | grep -A 3 '"text"' || echo "Could not parse response"
fi
echo ""

#############################################
# Test 5: Chat Completions (OpenAI-compatible)
#############################################

test_chat_completions() {
    local request=$(cat <<EOF
{
  "model": "mistralai/Mistral-7B-Instruct-v0.2",
  "messages": [
    {"role": "user", "content": "What is 2+2?"}
  ],
  "max_tokens": 50
}
EOF
)
    local response=$(curl -s -X POST "$VLLM_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "$request" 2>&1)
    
    echo "$response" | grep -q '"content"'
}

run_test "Chat Completions (OpenAI API)" "test_chat_completions"
if [ $? -eq 0 ]; then
    echo "Chat response preview:"
    curl -s -X POST "$VLLM_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"model":"mistralai/Mistral-7B-Instruct-v0.2","messages":[{"role":"user","content":"What is 2+2?"}],"max_tokens":50}' \
        | python3 -m json.tool 2>/dev/null | grep -A 3 '"content"' || echo "Could not parse response"
fi
echo ""

#############################################
# Test 6: Metrics Endpoint
#############################################

test_metrics() {
    local response=$(curl -s "$VLLM_URL/metrics" 2>&1)
    echo "$response" | grep -q 'vllm:'
}

run_test "Metrics Endpoint (Prometheus)" "test_metrics"
if [ $? -eq 0 ]; then
    echo "Sample metrics:"
    curl -s "$VLLM_URL/metrics" | grep '^vllm:' | head -10
fi
echo ""

#############################################
# Test 7: Performance Test (Multiple Requests)
#############################################

echo -e "${BLUE}[TEST]${NC} Performance Test (10 concurrent requests)"

PERF_START=$(date +%s)

for i in {1..10}; do
    (
        curl -s -X POST "$VLLM_URL/v1/completions" \
            -H "Content-Type: application/json" \
            -d '{"model":"mistralai/Mistral-7B-Instruct-v0.2","prompt":"Count to 5:","max_tokens":20}' \
            > /dev/null 2>&1
    ) &
done

wait

PERF_END=$(date +%s)
PERF_DURATION=$((PERF_END - PERF_START))

echo "Completed 10 concurrent requests in ${PERF_DURATION}s"
if [ $PERF_DURATION -lt 60 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (reasonable response time)"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ SLOW${NC} (took longer than expected)"
fi
echo ""

#############################################
# Test 8: Long Context Test
#############################################

test_long_context() {
    local long_prompt="Explain the concept of high-performance computing, including parallel processing, distributed computing, and GPU acceleration. Discuss the importance of HPC in scientific research and industry applications."
    
    local request=$(cat <<EOF
{
  "model": "mistralai/Mistral-7B-Instruct-v0.2",
  "prompt": "$long_prompt",
  "max_tokens": 200,
  "temperature": 0.7
}
EOF
)
    local response=$(curl -s -X POST "$VLLM_URL/v1/completions" \
        -H "Content-Type: application/json" \
        -d "$request" 2>&1)
    
    echo "$response" | grep -q '"text"'
}

run_test "Long Context Completion" "test_long_context"
echo ""

#############################################
# Test Summary
#############################################

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}=========================================${NC}"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo -e "Total Tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:       $TESTS_PASSED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed:       $TESTS_FAILED${NC}"
else
    echo -e "Failed:       $TESTS_FAILED"
fi

echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some tests failed${NC}"
    exit 1
fi
