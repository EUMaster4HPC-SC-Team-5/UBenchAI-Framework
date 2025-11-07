#!/bin/bash

# ========================================
# Check UBenchAI Monitoring Stack Status
# Shows status of all monitoring services
# ========================================

echo "========================================="
echo "  UBenchAI Monitoring Stack Status"
echo "========================================="
echo ""

# Function to check if a service is running
check_service() {
    local service_name=$1
    local process_pattern=$2
    local port=$3
    
    echo "[$service_name]"
    
    # Check process
    local pids=$(pgrep -f "$process_pattern" || true)
    if [ -n "$pids" ]; then
        echo "  Status: RUNNING"
        echo "  PIDs: $pids"
        
        # Check port if specified
        if [ -n "$port" ]; then
            if curl -s "http://localhost:$port" > /dev/null 2>&1; then
                echo "  Port $port: ACCESSIBLE"
            else
                echo "  Port $port: NOT ACCESSIBLE"
            fi
        fi
    else
        echo "  Status: NOT RUNNING"
    fi
    echo ""
}

# Check Prometheus
check_service "Prometheus" "prometheus.*config.file" "9090"

# Check Grafana
check_service "Grafana" "grafana-server" "3000"

# Check Node Exporter
check_service "Node Exporter" "node_exporter" "9100"

# Check cAdvisor
check_service "cAdvisor" "cadvisor" "8080"

# Check SLURM jobs
echo "[SLURM Jobs]"
if command -v squeue &> /dev/null; then
    JOBS=$(squeue -u $USER -n ubenchai_monitoring,node_exporter,cadvisor -o "%.18i %.20j %.8T %.10M %.6D %R" 2>/dev/null || true)
    if [ -n "$JOBS" ]; then
        echo "$JOBS"
    else
        echo "  No monitoring jobs found"
    fi
else
    echo "  SLURM not available"
fi
echo ""

# Show recent logs
echo "[Recent Logs]"
if [ -d "logs/monitoring" ]; then
    echo "Prometheus:"
    tail -n 3 logs/monitoring/prometheus.err 2>/dev/null || echo "  No logs found"
    echo ""
    echo "Grafana:"
    tail -n 3 logs/monitoring/grafana.err 2>/dev/null || echo "  No logs found"
else
    echo "  No log directory found"
fi
echo ""

echo "========================================="
echo ""
echo "For detailed logs, check:"
echo "  logs/monitoring/prometheus.{out,err}"
echo "  logs/monitoring/grafana.{out,err}"
echo ""
