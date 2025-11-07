#!/bin/bash

# ========================================
# Stop UBenchAI Monitoring Stack
# Gracefully stops Prometheus and Grafana
# ========================================

echo "========================================="
echo "  Stopping UBenchAI Monitoring Stack"
echo "========================================="

# Find and kill Prometheus
echo "Stopping Prometheus..."
PROM_PIDS=$(pgrep -f "prometheus.*ubenchai" || true)
if [ -n "$PROM_PIDS" ]; then
    for pid in $PROM_PIDS; do
        echo "  Killing Prometheus process: $pid"
        kill -TERM $pid 2>/dev/null || true
    done
    sleep 2
    # Force kill if still running
    for pid in $PROM_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "  Force killing Prometheus process: $pid"
            kill -9 $pid 2>/dev/null || true
        fi
    done
    echo "✓ Prometheus stopped"
else
    echo "  No Prometheus processes found"
fi

# Find and kill Grafana
echo "Stopping Grafana..."
GRAFANA_PIDS=$(pgrep -f "grafana-server" || true)
if [ -n "$GRAFANA_PIDS" ]; then
    for pid in $GRAFANA_PIDS; do
        echo "  Killing Grafana process: $pid"
        kill -TERM $pid 2>/dev/null || true
    done
    sleep 2
    # Force kill if still running
    for pid in $GRAFANA_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "  Force killing Grafana process: $pid"
            kill -9 $pid 2>/dev/null || true
        fi
    done
    echo "✓ Grafana stopped"
else
    echo "  No Grafana processes found"
fi

# Find and kill Node Exporter
echo "Stopping Node Exporter..."
NODE_PIDS=$(pgrep -f "node_exporter" || true)
if [ -n "$NODE_PIDS" ]; then
    for pid in $NODE_PIDS; do
        echo "  Killing Node Exporter process: $pid"
        kill -TERM $pid 2>/dev/null || true
    done
    echo "✓ Node Exporter stopped"
else
    echo "  No Node Exporter processes found"
fi

# Find and kill cAdvisor
echo "Stopping cAdvisor..."
CADVISOR_PIDS=$(pgrep -f "cadvisor" || true)
if [ -n "$CADVISOR_PIDS" ]; then
    for pid in $CADVISOR_PIDS; do
        echo "  Killing cAdvisor process: $pid"
        kill -TERM $pid 2>/dev/null || true
    done
    echo "✓ cAdvisor stopped"
else
    echo "  No cAdvisor processes found"
fi

echo ""
echo "========================================="
echo "  Monitoring Stack Stopped"
echo "========================================="
echo ""
echo "To restart, run:"
echo "  sbatch scripts/deploy_monitoring_stack.sh"
echo ""
