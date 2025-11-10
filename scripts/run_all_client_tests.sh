#!/bin/bash
# Master script for running all UBenchAI client tests
# Usage: ./run_all_client_tests.sh [all|ollama|qdrant|vllm|vllm-multi]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo ""
}

# Function to submit job and track it
submit_test() {
    local test_name=$1
    local script_file=$2
    
    print_header "Starting: $test_name"
    
    if [ ! -f "$script_file" ]; then
        echo -e "${RED}ERROR: Script not found: $script_file${NC}"
        return 1
    fi
    
    # Make executable
    chmod +x "$script_file"
    
    # Submit job
    echo "Submitting job: sbatch $script_file"
    OUTPUT=$(sbatch "$script_file" 2>&1)
    
    if [ $? -eq 0 ]; then
        JOB_ID=$(echo "$OUTPUT" | grep -oP 'Submitted batch job \K[0-9]+')
        echo -e "${GREEN}✓ Job submitted: $JOB_ID${NC}"
        echo "  Script: $script_file"
        echo "  Name: $test_name"
        echo ""
        echo "Monitor with: squeue -j $JOB_ID"
        echo "View output: tail -f client_*_${JOB_ID}.out"
        return 0
    else
        echo -e "${RED}✗ Job submission failed${NC}"
        echo "$OUTPUT"
        return 1
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [test_name]

Available tests:
  all          - Run all client tests sequentially
  ollama       - Run Ollama LLM benchmark
  qdrant       - Run Qdrant vector DB benchmark
  vllm         - Run vLLM single-node benchmark
  vllm-multi   - Run vLLM multi-node benchmark

Examples:
  $0              # Interactive menu
  $0 all          # Run all tests
  $0 ollama       # Run only Ollama test
  $0 qdrant       # Run only Qdrant test

Monitor running jobs:
  squeue --me
  watch "squeue --me"

View job output:
  tail -f client_*_<job-id>.out

Cancel a job:
  scancel <job-id>
EOF
}

# Function to show menu
show_menu() {
    print_header "UBenchAI Client Test Suite"
    
    echo "Select a test to run:"
    echo ""
    echo "  1) Ollama LLM Benchmark"
    echo "  2) Qdrant Vector DB Benchmark"
    echo "  3) vLLM Single-Node Benchmark"
    echo "  4) vLLM Multi-Node Benchmark"
    echo "  5) Run All Tests (Sequential)"
    echo "  6) Show Current Jobs"
    echo "  0) Exit"
    echo ""
    read -p "Enter choice [0-6]: " choice
    
    case $choice in
        1) submit_test "Ollama Client Test" "test_client_ollama.sh" ;;
        2) submit_test "Qdrant Client Test" "test_client_qdrant.sh" ;;
        3) submit_test "vLLM Single-Node Test" "test_client_vllm_single.sh" ;;
        4) submit_test "vLLM Multi-Node Test" "test_client_vllm_multinode.sh" ;;
        5) run_all_tests ;;
        6) show_jobs ;;
        0) echo "Exiting..."; exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}"; show_menu ;;
    esac
}

# Function to run all tests
run_all_tests() {
    print_header "Running All Client Tests"
    
    echo "This will submit all 4 client tests sequentially."
    echo "Each test will wait for the previous one to complete."
    echo ""
    read -p "Continue? (y/n): " confirm
    
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Cancelled."
        return 1
    fi
    
    # Test 1: Ollama
    print_header "Test 1/4: Ollama"
    if submit_test "Ollama" "test_client_ollama.sh"; then
        OLLAMA_JOB=$(squeue --me --format="%i %j" --noheader | grep "client-ollama" | awk '{print $1}')
        if [ -n "$OLLAMA_JOB" ]; then
            echo "Waiting for Ollama test to complete (Job $OLLAMA_JOB)..."
            while squeue -j $OLLAMA_JOB &>/dev/null; do
                sleep 10
            done
            echo -e "${GREEN}✓ Ollama test completed${NC}"
        fi
    fi
    sleep 5
    
    # Test 2: Qdrant
    print_header "Test 2/4: Qdrant"
    if submit_test "Qdrant" "test_client_qdrant.sh"; then
        QDRANT_JOB=$(squeue --me --format="%i %j" --noheader | grep "client-qdrant" | awk '{print $1}')
        if [ -n "$QDRANT_JOB" ]; then
            echo "Waiting for Qdrant test to complete (Job $QDRANT_JOB)..."
            while squeue -j $QDRANT_JOB &>/dev/null; do
                sleep 10
            done
            echo -e "${GREEN}✓ Qdrant test completed${NC}"
        fi
    fi
    sleep 5
    
    # Test 3: vLLM Single
    print_header "Test 3/4: vLLM Single-Node"
    if submit_test "vLLM Single-Node" "test_client_vllm_single.sh"; then
        VLLM_JOB=$(squeue --me --format="%i %j" --noheader | grep "client-vllm" | grep -v "multi" | awk '{print $1}')
        if [ -n "$VLLM_JOB" ]; then
            echo "Waiting for vLLM single-node test to complete (Job $VLLM_JOB)..."
            while squeue -j $VLLM_JOB &>/dev/null; do
                sleep 10
            done
            echo -e "${GREEN}✓ vLLM single-node test completed${NC}"
        fi
    fi
    sleep 5
    
    # Test 4: vLLM Multi (optional, user must confirm)
    print_header "Test 4/4: vLLM Multi-Node (Optional)"
    echo "vLLM multi-node test requires manual server setup."
    read -p "Run vLLM multi-node test? (y/n): " run_multi
    
    if [ "$run_multi" = "y" ] || [ "$run_multi" = "Y" ]; then
        submit_test "vLLM Multi-Node" "test_client_vllm_multinode.sh"
    else
        echo "Skipping vLLM multi-node test"
    fi
    
    print_header "All Tests Submitted"
    echo "Use 'squeue --me' to monitor jobs"
    echo "View results in: results/"
}

# Function to show current jobs
show_jobs() {
    print_header "Current Jobs"
    squeue --me --format="%.8i %.9P %.20j %.8u %.2t %.10M %.6D %R"
    echo ""
    read -p "Press Enter to continue..."
    show_menu
}

# Main script logic
if [ $# -eq 0 ]; then
    # Interactive mode
    show_menu
else
    # Command line mode
    case $1 in
        all)
            run_all_tests
            ;;
        ollama)
            submit_test "Ollama Client Test" "test_client_ollama.sh"
            ;;
        qdrant)
            submit_test "Qdrant Client Test" "test_client_qdrant.sh"
            ;;
        vllm)
            submit_test "vLLM Single-Node Test" "test_client_vllm_single.sh"
            ;;
        vllm-multi)
            submit_test "vLLM Multi-Node Test" "test_client_vllm_multinode.sh"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            echo -e "${RED}Unknown test: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
fi