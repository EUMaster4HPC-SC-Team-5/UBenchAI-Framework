# UBenchAI Monitoring Scripts

This directory contains scripts for deploying and managing the Prometheus/Grafana monitoring stack on HPC/SLURM environments.

## Scripts Overview

### Deployment Scripts

#### `deploy_monitoring_stack.sh`
Main deployment script for Prometheus and Grafana.

**Usage:**
```bash
sbatch scripts/deploy_monitoring_stack.sh
```

**What it does:**
- Pulls Prometheus and Grafana container images
- Creates configuration files
- Starts Prometheus on port 9090
- Starts Grafana on port 3000
- Downloads pre-configured dashboards
- Sets up service discovery

**SLURM Resources:**
- Nodes: 1
- CPUs: 2
- Memory: 8GB
- Time: 24 hours

#### `start_node_exporter.sh`
Deploys Node Exporter for system metrics.

**Usage:**
```bash
sbatch scripts/start_node_exporter.sh
```

**What it does:**
- Pulls Node Exporter container
- Starts exporter on port 9100
- Exports CPU, memory, disk, network metrics

**SLURM Resources:**
- Nodes: 1
- CPUs: 1
- Memory: 512MB
- Time: 24 hours

#### `start_cadvisor.sh`
Deploys cAdvisor for container metrics.

**Usage:**
```bash
sbatch scripts/start_cadvisor.sh
```

**What it does:**
- Pulls cAdvisor container
- Starts exporter on port 8080
- Exports container resource usage

**SLURM Resources:**
- Nodes: 1
- CPUs: 1
- Memory: 1GB
- Time: 24 hours

### Management Scripts

#### `register_target.py`
Python script for managing Prometheus targets.

**Usage:**
```bash
# Add a target
python3 scripts/register_target.py add <job_type> --target <host:port>

# Remove a target
python3 scripts/register_target.py remove <job_type> --target <host:port>

# List targets
python3 scripts/register_target.py list <job_type>

# Add target with labels
python3 scripts/register_target.py add node \
  --target "node001:9100" \
  --label "datacenter=meluxina" \
  --label "rack=A1"
```

**Job types:**
- `node`: Node Exporter (system metrics)
- `cadvisor`: cAdvisor (container metrics)
- `gpu`: DCGM Exporter (GPU metrics)
- `ollama`: Ollama LLM service
- `qdrant`: Qdrant vector database

**Examples:**
```bash
# Register node exporter
python3 scripts/register_target.py add node --target "node001:9100"

# Register multiple GPU nodes
python3 scripts/register_target.py add gpu --target "gpu001:9400"
python3 scripts/register_target.py add gpu --target "gpu002:9400"

# List all node targets
python3 scripts/register_target.py list node
```

#### `stop_monitoring.sh`
Stops all monitoring services.

**Usage:**
```bash
bash scripts/stop_monitoring.sh
```

**What it does:**
- Finds and stops Prometheus processes
- Finds and stops Grafana processes
- Finds and stops Node Exporter processes
- Finds and stops cAdvisor processes

#### `check_monitoring_status.sh`
Checks status of all monitoring services.

**Usage:**
```bash
bash scripts/check_monitoring_status.sh
```

**What it shows:**
- Process status (running/not running)
- Process IDs
- Port accessibility
- SLURM job status
- Recent log entries

## Typical Workflow

### 1. Initial Deployment

```bash
# Deploy main monitoring stack
sbatch scripts/deploy_monitoring_stack.sh

# Wait for job to start
squeue -u $USER

# Check logs
tail -f logs/monitoring_stack.out
```

### 2. Deploy Exporters on Compute Nodes

```bash
# SSH to compute node or submit as SLURM job
sbatch scripts/start_node_exporter.sh
sbatch scripts/start_cadvisor.sh
```

### 3. Register Targets

```bash
# Get node IPs from SLURM
squeue -u $USER -o "%.18i %.9P %.20j %.8u %.2t %.10M %.6D %R"

# Register targets
python3 scripts/register_target.py add node --target "node001:9100"
python3 scripts/register_target.py add cadvisor --target "node001:8080"
```

### 4. Verify Setup

```bash
# Check all services
bash scripts/check_monitoring_status.sh

# Get Grafana URL
cat logs/grafana_data/grafana_ip.txt

# Access Grafana
# http://<ip>:3000
# Username: admin
# Password: ubenchai
```

### 5. Monitor Your Workload

Your benchmarks will now be monitored automatically. Access Grafana to view dashboards.

### 6. Cleanup

```bash
# Stop all monitoring
bash scripts/stop_monitoring.sh

# Or cancel SLURM jobs
scancel -u $USER -n ubenchai_monitoring,node_exporter,cadvisor
```

## Configuration

### Customizing SLURM Parameters

Edit the `#SBATCH` directives in each script:

```bash
#SBATCH --account=p200981      # Your SLURM account
#SBATCH --partition=cpu        # Partition to use
#SBATCH --qos=default          # QoS policy
#SBATCH --time=24:00:00        # Max runtime
#SBATCH --mem=8G               # Memory allocation
```

### Customizing Ports

Edit the scripts to change default ports:

**Prometheus** (in `deploy_monitoring_stack.sh`):
```bash
--web.listen-address=0.0.0.0:9090  # Change 9090
```

**Grafana** (in `deploy_monitoring_stack.sh`):
```bash
--env GF_SERVER_HTTP_PORT=3000  # Change 3000
```

**Node Exporter** (in `start_node_exporter.sh`):
```bash
--web.listen-address=0.0.0.0:9100  # Change 9100
```

### Customizing Retention

Edit `deploy_monitoring_stack.sh`:

```bash
--storage.tsdb.retention.time=30d  # Change retention period
```

### Customizing Scrape Intervals

Edit `logs/prometheus.yml` after deployment:

```yaml
global:
  scrape_interval: 15s      # Change default interval
  evaluation_interval: 15s  # Change evaluation interval
```

## Troubleshooting

### Script Fails to Submit

**Error:** `sbatch: error: Batch job submission failed`

**Solutions:**
- Check SLURM account: `sacctmgr show user $USER`
- Verify partition exists: `sinfo`
- Check resource limits: `sacctmgr show qos`

### Container Pull Fails

**Error:** `FATAL: Unable to pull docker://...`

**Solutions:**
- Check internet connectivity
- Verify Apptainer is loaded: `module load Apptainer`
- Try pulling manually: `apptainer pull docker://prom/prometheus:latest`

### Port Already in Use

**Error:** `bind: address already in use`

**Solutions:**
- Check what's using the port: `netstat -tuln | grep 9090`
- Kill existing process or change port in script
- Use different node

### Permission Denied

**Error:** `Permission denied` when accessing files

**Solutions:**
- Check file permissions: `ls -la logs/`
- Ensure directories exist: `mkdir -p logs/monitoring`
- Check SLURM job output directory permissions

### Targets Not Appearing

**Problem:** Registered targets don't show up in Prometheus

**Solutions:**
- Verify JSON file format: `cat logs/prometheus_assets/node_targets.json`
- Check Prometheus logs: `tail logs/monitoring/prometheus.err`
- Verify exporter is running: `curl http://node001:9100/metrics`
- Wait for refresh interval (10 seconds)

## Advanced Usage

### Using with Python API

```python
from ubenchai.monitors.manager import MonitorManager

manager = MonitorManager(
    recipe_directory="recipes",
    output_root="logs"
)

instance = manager.start_monitor(
    recipe_name="monitor-hpc-stack",
    targets=["node001:9100"],
    mode="slurm"
)

print(f"Prometheus: {instance.prometheus_url}")
print(f"Grafana: {instance.grafana_url}")
```

### Custom Monitoring Recipe

Create a custom recipe in `recipes/`:

```yaml
name: my-custom-monitor
description: Custom monitoring configuration

exporters:
  - type: prometheus
    port: 9090
    scrape_configs:
      - job_name: my_service
        static_configs:
          - targets: ["localhost:8080"]

grafana:
  enabled: true
  port: 3000
  dashboards:
    - type: system
      title: "My Dashboard"
```

### Batch Target Registration

```bash
# Register multiple targets from file
while read host; do
  python3 scripts/register_target.py add node --target "$host:9100"
done < nodes.txt
```

### Automated Deployment

```bash
#!/bin/bash
# deploy_all.sh

# Deploy monitoring stack
MONITOR_JOB=$(sbatch --parsable scripts/deploy_monitoring_stack.sh)

# Wait for monitoring stack
sleep 30

# Deploy exporters on compute nodes
for node in node001 node002 node003; do
  srun --nodelist=$node scripts/start_node_exporter.sh &
done

wait

# Register targets
for node in node001 node002 node003; do
  python3 scripts/register_target.py add node --target "$node:9100"
done

echo "Deployment complete!"
```

## File Permissions

Make scripts executable:

```bash
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

## Dependencies

- **Apptainer/Singularity**: Container runtime
- **Python 3.8+**: For target registration script
- **curl**: For health checks
- **SLURM**: Workload manager

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `logs/monitoring/`
3. Consult the main documentation: `docs/MONITORING_DEPLOYMENT_GUIDE.md`
4. Check the quick reference: `docs/MONITORING_QUICK_REFERENCE.md`
