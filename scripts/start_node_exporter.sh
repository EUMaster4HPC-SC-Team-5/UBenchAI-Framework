#!/bin/bash
#SBATCH --job-name=node_exporter
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --time=24:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=logs/node_exporter_%j.out
#SBATCH --error=logs/node_exporter_%j.err

# ========================================
# Node Exporter for System Metrics
# Exports hardware and OS metrics
# ========================================

set -e

module load env/release/2024.1
module load Apptainer

cd $SLURM_SUBMIT_DIR || exit 1

echo "========================================="
echo "  Starting Node Exporter"
echo "========================================="
echo "Node: $(hostname)"
echo "IP: $(hostname -i)"
echo ""

# Create directories
mkdir -p logs/monitoring
mkdir -p containers

# Pull Node Exporter container if not present
if [ ! -f containers/node_exporter.sif ]; then
    echo "Pulling Node Exporter image..."
    apptainer pull containers/node_exporter.sif docker://prom/node-exporter:latest
    echo "✓ Node Exporter image pulled"
fi

# Start Node Exporter
echo "Starting Node Exporter on port 9100..."
apptainer exec \
  containers/node_exporter.sif \
  node_exporter \
  --web.listen-address=0.0.0.0:9100 \
  > logs/monitoring/node_exporter.out 2> logs/monitoring/node_exporter.err &

NODE_EXPORTER_PID=$!
echo "Node Exporter PID: $NODE_EXPORTER_PID"

# Wait for startup
sleep 5

# Check if healthy
if curl -s http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✓ Node Exporter is healthy"
else
    echo "⚠️  Node Exporter health check failed"
fi

echo ""
echo "========================================="
echo "  Node Exporter Ready"
echo "========================================="
echo "Metrics endpoint: http://$(hostname -i):9100/metrics"
echo "Logs: logs/monitoring/node_exporter.{out,err}"
echo "========================================="
echo ""

# Keep service alive
wait $NODE_EXPORTER_PID
