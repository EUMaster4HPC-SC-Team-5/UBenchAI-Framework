#!/bin/bash
#SBATCH --job-name=ubenchai_monitoring
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=24:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=logs/monitoring_stack.out
#SBATCH --error=logs/monitoring_stack.err

# ========================================
# UBenchAI Monitoring Stack Deployment
# Prometheus + Grafana on SLURM/HPC
# ========================================

set -e

module load env/release/2024.1
module load Apptainer
module load Python

# Go to submit directory
cd $SLURM_SUBMIT_DIR || exit 1

echo "========================================="
echo "  UBenchAI Monitoring Stack Deployment"
echo "========================================="
echo "Working directory: $(pwd)"
echo "Node: $(hostname)"
echo "IP: $(hostname -i)"
echo ""

# Create directory structure
mkdir -p logs/monitoring
mkdir -p logs/prometheus_data
mkdir -p logs/prometheus_assets
mkdir -p logs/grafana_data
mkdir -p logs/grafana_config/provisioning/datasources
mkdir -p logs/grafana_config/provisioning/dashboards
mkdir -p containers

# ========================================
# PROMETHEUS CONFIGURATION
# ========================================

echo "Creating Prometheus configuration..."

# Get Pushgateway IP if available
PUSHGATEWAY_IP=$(cat logs/pushgateway_data/pushgateway_ip.txt 2>/dev/null || echo "localhost")

cat > logs/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

scrape_configs:
  # Prometheus monitoring itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node Exporter for system hardware metrics
  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/node_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # cAdvisor for container metrics
  - job_name: 'cadvisor'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/cadvisor_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # DCGM GPU Exporter for GPU metrics
  - job_name: 'dcgm_gpu'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/gpu_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # Ollama LLM service metrics
  - job_name: 'ollama'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/ollama_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # Qdrant Vector DB metrics
  - job_name: 'qdrant'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/qdrant_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # Pushgateway for pushed metrics
  - job_name: 'pushgateway'
    static_configs:
      - targets: ['$PUSHGATEWAY_IP:9091']
    scrape_interval: 10s
EOF

echo "✓ Prometheus configuration created"

# Initialize empty JSON target files
echo '[]' > logs/prometheus_assets/node_targets.json
echo '[]' > logs/prometheus_assets/cadvisor_targets.json
echo '[]' > logs/prometheus_assets/gpu_targets.json
echo '[]' > logs/prometheus_assets/ollama_targets.json
echo '[]' > logs/prometheus_assets/qdrant_targets.json

# ========================================
# GRAFANA CONFIGURATION
# ========================================

echo "Creating Grafana configuration..."

# Provision Prometheus datasource (using localhost since same node)
cat > logs/grafana_config/provisioning/datasources/prometheus.yml <<EOF
apiVersion: 1

datasources:
  - name: UBenchAI Prometheus
    type: prometheus
    uid: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 15s
      queryTimeout: 60s
      httpMethod: POST
      keepCookies: []
    version: 1
    readOnly: false
EOF

echo "✓ Grafana datasource configuration created"

# Provision dashboard provider
cat > logs/grafana_config/provisioning/dashboards/default.yml <<EOF
apiVersion: 1

providers:
  - name: 'UBenchAI Dashboards'
    orgId: 1
    folder: 'UBenchAI Monitoring'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

echo "✓ Grafana dashboard provider configuration created"

# ========================================
# DOWNLOAD GRAFANA DASHBOARDS
# ========================================

echo "Downloading preconfigured Grafana dashboards..."

# Download Node Exporter dashboard
if [ ! -f logs/grafana_config/provisioning/dashboards/node-exporter.json ]; then
    echo "  - Creating Node Exporter dashboard..."
    curl -s -o /tmp/node-exporter-raw.json \
      https://grafana.com/api/dashboards/1860/revisions/latest/download
    
    if [ $? -eq 0 ] && [ -f /tmp/node-exporter-raw.json ]; then
        python3 << 'PYEOF' > logs/grafana_config/provisioning/dashboards/node-exporter.json
import json

with open('/tmp/node-exporter-raw.json', 'r') as f:
    dashboard = json.load(f)

# Fix datasource references
def fix_datasource(obj):
    if isinstance(obj, dict):
        if 'datasource' in obj:
            ds = obj['datasource']
            if isinstance(ds, str) and ('${' in ds or ds == ''):
                obj['datasource'] = 'UBenchAI Prometheus'
            elif isinstance(ds, dict):
                if 'type' in ds or 'uid' in ds:
                    if 'uid' in ds and (isinstance(ds['uid'], str) and ('${' in ds['uid'] or ds['uid'] == '')):
                        ds['uid'] = 'prometheus'
                    if 'type' not in ds or ds['type'] == '':
                        ds['type'] = 'prometheus'
        
        for key, value in obj.items():
            if key != 'datasource':
                fix_datasource(value)
    elif isinstance(obj, list):
        for item in obj:
            fix_datasource(item)

fix_datasource(dashboard)

# Update dashboard metadata
dashboard['title'] = 'Node Exporter - System Metrics'
dashboard['uid'] = 'node-exporter-ubenchai'
if 'id' in dashboard:
    dashboard['id'] = None

print(json.dumps(dashboard, indent=2))
PYEOF
        
        echo "    ✓ Node Exporter dashboard created"
        rm -f /tmp/node-exporter-raw.json
    else
        echo "    ⚠️  Failed to download Node Exporter dashboard"
    fi
fi

# ========================================
# PULL CONTAINER IMAGES
# ========================================

echo "Pulling container images..."

# Pull Prometheus container if not already present
if [ ! -f containers/prometheus.sif ]; then
    echo "  - Pulling Prometheus image..."
    apptainer pull containers/prometheus.sif docker://prom/prometheus:latest
    echo "    ✓ Prometheus image pulled"
fi

# Pull Grafana container if not already present
if [ ! -f containers/grafana.sif ]; then
    echo "  - Pulling Grafana image..."
    apptainer pull containers/grafana.sif docker://grafana/grafana:latest
    echo "    ✓ Grafana image pulled"
fi

# ========================================
# START PROMETHEUS
# ========================================

echo ""
echo "Starting Prometheus..."
apptainer exec \
  --bind logs/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  --bind $(pwd)/logs:/prometheus \
  containers/prometheus.sif \
  prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=0.0.0.0:9090 \
  --storage.tsdb.path=/prometheus/prometheus_data \
  --storage.tsdb.retention.time=30d \
  --web.enable-lifecycle \
  --web.enable-admin-api \
  > logs/monitoring/prometheus.out 2> logs/monitoring/prometheus.err &

PROMETHEUS_PID=$!
echo "Prometheus PID: $PROMETHEUS_PID"

# Wait for Prometheus to start
echo "Waiting for Prometheus to become ready..."
sleep 10

# Check if Prometheus is healthy
for i in {1..12}; do
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "✓ Prometheus is healthy"
        break
    fi
    if [ $i -eq 12 ]; then
        echo "⚠️  Prometheus health check timeout"
    fi
    sleep 5
done

echo "✓ Prometheus started at http://$(hostname -i):9090"
echo "  Logs: logs/monitoring/prometheus.{out,err}"

# ========================================
# START GRAFANA
# ========================================

echo ""
echo "Starting Grafana..."
apptainer exec \
  --env GF_SECURITY_ADMIN_USER=admin \
  --env GF_SECURITY_ADMIN_PASSWORD=ubenchai \
  --env GF_USERS_ALLOW_SIGN_UP=false \
  --env GF_SERVER_HTTP_PORT=3000 \
  --bind $(pwd)/logs/grafana_data:/var/lib/grafana \
  --bind $(pwd)/logs/grafana_config/provisioning:/etc/grafana/provisioning:ro \
  containers/grafana.sif \
  grafana-server \
  --homepath=/usr/share/grafana \
  > logs/monitoring/grafana.out 2> logs/monitoring/grafana.err &

GRAFANA_PID=$!
echo "Grafana PID: $GRAFANA_PID"

# Wait for Grafana to start
echo "Waiting for Grafana to become ready..."
sleep 15

# Check if Grafana is healthy
for i in {1..12}; do
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✓ Grafana is healthy"
        break
    fi
    if [ $i -eq 12 ]; then
        echo "⚠️  Grafana health check timeout"
    fi
    sleep 5
done

echo "✓ Grafana started at http://$(hostname -i):3000"
echo "  Username: admin"
echo "  Password: ubenchai"
echo "  Logs: logs/monitoring/grafana.{out,err}"

# ========================================
# SUMMARY
# ========================================

echo ""
echo "========================================="
echo "   MONITORING STACK READY"
echo "========================================="
echo "Node:       $(hostname)"
echo "IP:         $(hostname -i)"
echo ""
echo "Services:"
echo "  Prometheus: http://$(hostname -i):9090"
echo "  Grafana:    http://$(hostname -i):3000"
echo ""
echo "Credentials:"
echo "  Username: admin"
echo "  Password: ubenchai"
echo ""
echo "Configuration:"
echo "  Prometheus config: logs/prometheus.yml"
echo "  Target files: logs/prometheus_assets/*.json"
echo "  Grafana provisioning: logs/grafana_config/provisioning/"
echo ""
echo "Dashboards provisioned:"
echo "  - Node Exporter - System Metrics"
echo ""
echo "To add monitoring targets, update JSON files in:"
echo "  logs/prometheus_assets/"
echo ""
echo "========================================="
echo ""

# Save node info for reference
echo "$(hostname -i)" > logs/prometheus_data/prometheus_ip.txt
echo "$(hostname -i)" > logs/grafana_data/grafana_ip.txt

# Keep both services alive
wait $PROMETHEUS_PID $GRAFANA_PID
