# UBenchAI Monitoring Stack Deployment Guide

This guide explains how to deploy and use the Prometheus/Grafana monitoring stack for UBenchAI on HPC/SLURM environments, based on the team9-EUMASTER4HPC2526 implementation.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Quick Start](#quick-start)
5. [Detailed Deployment](#detailed-deployment)
6. [Managing Targets](#managing-targets)
7. [Accessing Dashboards](#accessing-dashboards)
8. [Troubleshooting](#troubleshooting)

## Overview

The UBenchAI monitoring stack provides comprehensive observability for LLM benchmarking workloads on HPC systems. It includes:

- **Prometheus**: Time-series database for metrics collection
- **Grafana**: Visualization and dashboarding
- **Node Exporter**: System hardware and OS metrics
- **cAdvisor**: Container metrics
- **DCGM Exporter**: GPU metrics (NVIDIA)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SLURM Cluster                            │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Compute Node │    │ Compute Node │    │ Compute Node │ │
│  │              │    │              │    │              │ │
│  │ Node Exporter│    │ Node Exporter│    │ Node Exporter│ │
│  │ cAdvisor     │    │ cAdvisor     │    │ DCGM Exporter│ │
│  │ Ollama       │    │ Qdrant       │    │              │ │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘ │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                              │
│                    ┌────────▼────────┐                     │
│                    │  Monitoring Node │                     │
│                    │                 │                     │
│                    │  Prometheus     │                     │
│                    │  Grafana        │                     │
│                    └─────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required Modules
- Apptainer (Singularity)
- Python 3.8+
- SLURM workload manager

### Required Ports
- **9090**: Prometheus
- **3000**: Grafana
- **9100**: Node Exporter
- **8080**: cAdvisor
- **9400**: DCGM Exporter (GPU nodes)

### SLURM Account
Ensure you have access to a SLURM account (e.g., `p200981`). Update the account in the scripts:
```bash
#SBATCH --account=YOUR_ACCOUNT
```

## Quick Start

### 1. Deploy Monitoring Stack

Submit the monitoring stack as a SLURM job:

```bash
cd /path/to/UBenchAI-Framework
sbatch scripts/deploy_monitoring_stack.sh
```

This will:
- Pull Prometheus and Grafana container images
- Configure Prometheus with service discovery
- Configure Grafana with Prometheus datasource
- Start both services
- Download pre-configured dashboards

### 2. Check Status

Monitor the deployment:

```bash
# Check SLURM job status
squeue -u $USER

# Check service status
bash scripts/check_monitoring_status.sh

# View logs
tail -f logs/monitoring_stack.out
```

### 3. Deploy Exporters on Compute Nodes

On each compute node you want to monitor:

```bash
# Deploy Node Exporter (system metrics)
sbatch scripts/start_node_exporter.sh

# Deploy cAdvisor (container metrics)
sbatch scripts/start_cadvisor.sh
```

### 4. Register Targets

Register the exporters with Prometheus:

```bash
# Register node exporter
python3 scripts/register_target.py add node --target "node001:9100"

# Register cAdvisor
python3 scripts/register_target.py add cadvisor --target "node001:8080"

# Register GPU exporter
python3 scripts/register_target.py add gpu --target "gpu001:9400"
```

### 5. Access Grafana

Find the monitoring node IP:

```bash
cat logs/grafana_data/grafana_ip.txt
```

Access Grafana at: `http://<monitoring-node-ip>:3000`

**Default credentials:**
- Username: `admin`
- Password: `ubenchai`

## Detailed Deployment

### Monitoring Stack Configuration

The main deployment script (`deploy_monitoring_stack.sh`) creates:

```
logs/
├── prometheus.yml              # Prometheus configuration
├── prometheus_data/            # Time-series data storage
├── prometheus_assets/          # Service discovery JSON files
│   ├── node_targets.json
│   ├── cadvisor_targets.json
│   ├── gpu_targets.json
│   ├── ollama_targets.json
│   └── qdrant_targets.json
├── grafana_data/               # Grafana database
└── grafana_config/
    └── provisioning/
        ├── datasources/        # Prometheus datasource config
        └── dashboards/         # Dashboard JSON files
```

### Prometheus Configuration

The Prometheus configuration uses **file-based service discovery** for dynamic target management:

```yaml
scrape_configs:
  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/node_targets_*.json'
        refresh_interval: 10s
```

This allows you to add/remove targets without restarting Prometheus.

### Grafana Datasource

Grafana is automatically configured with Prometheus as the default datasource:

```yaml
datasources:
  - name: UBenchAI Prometheus
    type: prometheus
    url: http://localhost:9090
    isDefault: true
    jsonData:
      timeInterval: 15s
      queryTimeout: 60s
      httpMethod: POST
```

## Managing Targets

### Using the Registration Script

The `register_target.py` script manages Prometheus targets:

```bash
# Add a target
python3 scripts/register_target.py add <job_type> --target <host:port>

# Remove a target
python3 scripts/register_target.py remove <job_type> --target <host:port>

# List targets
python3 scripts/register_target.py list <job_type>
```

**Job types:**
- `node`: Node Exporter (system metrics)
- `cadvisor`: cAdvisor (container metrics)
- `gpu`: DCGM Exporter (GPU metrics)
- `ollama`: Ollama LLM service
- `qdrant`: Qdrant vector database

### Adding Labels

Add metadata labels to targets:

```bash
python3 scripts/register_target.py add node \
  --target "node001:9100" \
  --label "datacenter=meluxina" \
  --label "rack=A1"
```

### Manual Target Management

You can also manually edit the JSON files:

```json
[
  {
    "targets": [
      "node001:9100",
      "node002:9100",
      "node003:9100"
    ],
    "labels": {
      "job": "system_metrics",
      "datacenter": "meluxina"
    }
  }
]
```

Prometheus will automatically reload targets every 10 seconds.

## Accessing Dashboards

### Pre-configured Dashboards

The deployment includes several pre-configured dashboards:

1. **Node Exporter - System Metrics**
   - CPU, Memory, Disk, Network
   - System load and uptime
   - Filesystem usage

2. **LLM Performance** (if using monitor-hpc-stack recipe)
   - Request rate and latency
   - GPU utilization and memory
   - Inference throughput

3. **Vector DB Performance**
   - Query rate and latency
   - Index size and memory usage
   - Collection statistics

4. **Container Metrics**
   - Container CPU and memory
   - Network and disk I/O
   - Container lifecycle

5. **GPU Cluster Overview**
   - Multi-GPU utilization
   - Power usage and temperature
   - PCIe throughput

### Creating Custom Dashboards

1. Access Grafana at `http://<monitoring-node-ip>:3000`
2. Click **+** → **Dashboard**
3. Add panels with PromQL queries
4. Save the dashboard

Example PromQL queries:

```promql
# CPU usage
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# GPU utilization
DCGM_FI_DEV_GPU_UTIL

# Request rate
rate(ollama_requests_total[5m])
```

## Using with UBenchAI Python API

The monitoring stack integrates with UBenchAI's Python API:

```python
from ubenchai.monitors.manager import MonitorManager

# Initialize manager
manager = MonitorManager(
    recipe_directory="recipes",
    output_root="logs"
)

# Start monitoring with HPC recipe
instance = manager.start_monitor(
    recipe_name="monitor-hpc-stack",
    targets=["node001:9100", "node002:9100"],
    mode="slurm"
)

# Access URLs
print(f"Prometheus: {instance.prometheus_url}")
print(f"Grafana: {instance.grafana_url}")

# Run your benchmark
# ...

# Stop monitoring
manager.stop_monitor(instance.id)
```

## Stopping the Monitoring Stack

### Stop All Services

```bash
bash scripts/stop_monitoring.sh
```

This will gracefully stop:
- Prometheus
- Grafana
- Node Exporter instances
- cAdvisor instances

### Cancel SLURM Jobs

```bash
# List monitoring jobs
squeue -u $USER -n ubenchai_monitoring,node_exporter,cadvisor

# Cancel specific job
scancel <job_id>

# Cancel all monitoring jobs
scancel -u $USER -n ubenchai_monitoring,node_exporter,cadvisor
```

## Troubleshooting

### Prometheus Not Starting

**Check logs:**
```bash
tail -f logs/monitoring/prometheus.err
```

**Common issues:**
- Port 9090 already in use
- Invalid configuration file
- Insufficient permissions

**Solution:**
```bash
# Check port availability
netstat -tuln | grep 9090

# Validate configuration
prometheus --config.file=logs/prometheus.yml --config.check
```

### Grafana Connection Failed

**Check Prometheus health:**
```bash
curl http://localhost:9090/-/healthy
```

**Check Grafana logs:**
```bash
tail -f logs/monitoring/grafana.err
```

**Test datasource manually:**
```bash
curl -u admin:ubenchai \
  http://localhost:3000/api/datasources/name/UBenchAI%20Prometheus/health
```

### Targets Not Appearing

**Check target files:**
```bash
cat logs/prometheus_assets/node_targets.json
```

**Verify Prometheus can read files:**
```bash
# Check Prometheus targets API
curl http://localhost:9090/api/v1/targets
```

**Check exporter is running:**
```bash
curl http://<target-host>:9100/metrics
```

### No Data in Dashboards

**Verify scrape jobs:**
```bash
# Check Prometheus targets page
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'
```

**Check time range in Grafana:**
- Ensure the dashboard time range includes recent data
- Default retention is 30 days

**Verify metrics exist:**
```bash
# Query Prometheus directly
curl 'http://localhost:9090/api/v1/query?query=up'
```

### SLURM Job Failures

**Check SLURM logs:**
```bash
cat logs/monitoring_stack.err
```

**Common issues:**
- Insufficient resources (memory, CPUs)
- Account/partition issues
- Module loading failures

**Solution:**
```bash
# Adjust resource requirements in script
#SBATCH --mem=4G  # Reduce if needed
#SBATCH --cpus-per-task=1
```

## Best Practices

### Resource Allocation

- **Monitoring Node**: 2 CPUs, 8GB RAM
- **Node Exporter**: 1 CPU, 512MB RAM
- **cAdvisor**: 1 CPU, 1GB RAM

### Data Retention

Default retention is 30 days. Adjust in `deploy_monitoring_stack.sh`:

```bash
--storage.tsdb.retention.time=30d  # Change as needed
```

### Security

1. **Change default password:**
   ```bash
   # Edit deploy_monitoring_stack.sh
   --env GF_SECURITY_ADMIN_PASSWORD=your_secure_password
   ```

2. **Restrict access:**
   - Use firewall rules to limit access to monitoring ports
   - Consider SSH tunneling for remote access

3. **Enable HTTPS:**
   - Configure Grafana with SSL certificates
   - Use reverse proxy (nginx, Apache)

### Performance

1. **Adjust scrape intervals** based on workload:
   ```yaml
   scrape_interval: 15s  # Increase for less frequent updates
   ```

2. **Use recording rules** for expensive queries:
   ```yaml
   groups:
     - name: example
       rules:
         - record: job:node_cpu_usage:avg
           expr: avg(rate(node_cpu_seconds_total[5m]))
   ```

3. **Limit metric cardinality:**
   - Avoid high-cardinality labels
   - Use metric relabeling to drop unnecessary metrics

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Node Exporter Metrics](https://github.com/prometheus/node_exporter)
- [cAdvisor Metrics](https://github.com/google/cadvisor)
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)

## Support

For issues specific to UBenchAI monitoring:
1. Check the troubleshooting section above
2. Review logs in `logs/monitoring/`
3. Consult the UBenchAI documentation
4. Open an issue on the GitHub repository
