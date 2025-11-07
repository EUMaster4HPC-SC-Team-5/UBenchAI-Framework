#!/bin/bash
#SBATCH --job-name=cadvisor
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=24:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=logs/cadvisor_%j.out
#SBATCH --error=logs/cadvisor_%j.err

# ========================================
# cAdvisor for Container Metrics
# Monitors Docker/Apptainer containers
# ========================================

set -e

module load env/release/2024.1
module load Apptainer

cd $SLURM_SUBMIT_DIR || exit 1

echo "========================================="
echo "  Starting cAdvisor"
echo "========================================="
echo "Node: $(hostname)"
echo "IP: $(hostname -i)"
echo ""

# Create directories
mkdir -p logs/monitoring
mkdir -p containers

# Pull cAdvisor container if not present
if [ ! -f containers/cadvisor.sif ]; then
    echo "Pulling cAdvisor image..."
    apptainer pull containers/cadvisor.sif docker://gcr.io/cadvisor/cadvisor:latest
    echo "✓ cAdvisor image pulled"
fi

# Start cAdvisor
echo "Starting cAdvisor on port 8080..."
apptainer exec \
  --bind /:/rootfs:ro \
  --bind /var/run:/var/run:ro \
  --bind /sys:/sys:ro \
  --bind /var/lib/docker/:/var/lib/docker:ro \
  containers/cadvisor.sif \
  /usr/bin/cadvisor \
  --port=8080 \
  > logs/monitoring/cadvisor.out 2> logs/monitoring/cadvisor.err &

CADVISOR_PID=$!
echo "cAdvisor PID: $CADVISOR_PID"

# Wait for startup
sleep 5

# Check if healthy
if curl -s http://localhost:8080/metrics > /dev/null 2>&1; then
    echo "✓ cAdvisor is healthy"
else
    echo "⚠️  cAdvisor health check failed"
fi

echo ""
echo "========================================="
echo "  cAdvisor Ready"
echo "========================================="
echo "Metrics endpoint: http://$(hostname -i):8080/metrics"
echo "Web UI: http://$(hostname -i):8080"
echo "Logs: logs/monitoring/cadvisor.{out,err}"
echo "========================================="
echo ""

# Keep service alive
wait $CADVISOR_PID
