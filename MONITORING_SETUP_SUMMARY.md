# Monitoring Stack Setup Summary

## Overview

This document summarizes the Prometheus/Grafana monitoring implementation for UBenchAI-Framework, based on the team9-EUMASTER4HPC2526 code.

## What Was Implemented

### 1. SLURM Deployment Scripts

Created scripts for deploying monitoring services on HPC/SLURM environments:

- **`scripts/deploy_monitoring_stack.sh`**: Main deployment script for Prometheus + Grafana
- **`scripts/start_node_exporter.sh`**: Deploy Node Exporter for system metrics
- **`scripts/start_cadvisor.sh`**: Deploy cAdvisor for container metrics

### 2. Management Utilities

- **`scripts/register_target.py`**: Python tool for managing Prometheus targets
- **`scripts/stop_monitoring.sh`**: Stop all monitoring services
- **`scripts/check_monitoring_status.sh`**: Check status of monitoring stack

### 3. Configuration

- **`recipes/monitor-hpc-stack.yml`**: HPC-optimized monitoring recipe with:
  - Node Exporter for system metrics
  - cAdvisor for container metrics
  - DCGM for GPU metrics
  - Ollama LLM service monitoring
  - Qdrant vector DB monitoring
  - Pre-configured Grafana dashboards

### 4. Documentation

- **`docs/MONITORING_DEPLOYMENT_GUIDE.md`**: Comprehensive deployment guide
- **`docs/MONITORING_QUICK_REFERENCE.md`**: Quick reference for common tasks
- **`scripts/README.md`**: Script documentation

## Key Features

### Based on team9 Implementation

✅ **Apptainer/Singularity containers** for Prometheus and Grafana
✅ **File-based service discovery** for dynamic target management
✅ **Automatic datasource provisioning** in Grafana
✅ **Pre-configured dashboards** downloaded from Grafana.com
✅ **SLURM job submission** for HPC environments
✅ **Multi-node monitoring** support

### Enhanced for UBenchAI

✅ **Python API integration** with existing MonitorManager
✅ **Recipe-based configuration** using UBenchAI's recipe system
✅ **LLM-specific dashboards** for Ollama monitoring
✅ **Vector DB dashboards** for Qdrant monitoring
✅ **GPU cluster monitoring** with DCGM exporter

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SLURM Cluster                            │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Compute Node │    │ Compute Node │    │ GPU Node     │ │
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
│                    │  Prometheus     │ ← File-based        │
│                    │  (port 9090)    │   service discovery │
│                    │                 │                     │
│                    │  Grafana        │ ← Auto-provisioned  │
│                    │  (port 3000)    │   datasource        │
│                    └─────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Deploy Monitoring Stack

```bash
cd /path/to/UBenchAI-Framework
sbatch scripts/deploy_monitoring_stack.sh
```

### 2. Deploy Exporters on Compute Nodes

```bash
sbatch scripts/start_node_exporter.sh
sbatch scripts/start_cadvisor.sh
```

### 3. Register Targets

```bash
python3 scripts/register_target.py add node --target "node001:9100"
python3 scripts/register_target.py add cadvisor --target "node001:8080"
```

### 4. Access Grafana

```bash
cat logs/grafana_data/grafana_ip.txt
# Access: http://<ip>:3000
# Username: admin
# Password: ubenchai
```

## Comparison with team9 Implementation

| Feature | team9 | UBenchAI | Notes |
|---------|-------|----------|-------|
| Container Runtime | Apptainer | Apptainer | ✅ Same |
| Prometheus Config | Static | File-based SD | ✅ Same approach |
| Grafana Provisioning | Auto | Auto | ✅ Same |
| Dashboard Download | Python script | Python script | ✅ Same |
| SLURM Integration | Yes | Yes | ✅ Same |
| Target Management | Manual JSON | Python tool | ✨ Enhanced |
| Recipe System | No | Yes | ✨ New |
| Python API | No | Yes | ✨ New |
| LLM Monitoring | Basic | Advanced | ✨ Enhanced |
| GPU Monitoring | DCGM | DCGM | ✅ Same |

## Integration with Existing UBenchAI Code

The monitoring stack integrates seamlessly with UBenchAI's existing monitoring system:

### Python API Usage

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

# Access monitoring URLs
print(f"Prometheus: {instance.prometheus_url}")
print(f"Grafana: {instance.grafana_url}")

# Run your benchmark
# ...

# Stop monitoring
manager.stop_monitor(instance.id)
```

### Existing Code Components Used

- **`src/ubenchai/monitors/manager.py`**: MonitorManager orchestrates deployment
- **`src/ubenchai/monitors/prometheus_client.py`**: Handles Prometheus deployment
- **`src/ubenchai/monitors/grafana_client.py`**: Handles Grafana deployment
- **`src/ubenchai/monitors/models.py`**: Data models for monitoring instances

### New Components Added

- **SLURM deployment scripts**: Shell scripts for HPC deployment
- **Target registration tool**: Python utility for managing targets
- **HPC monitoring recipe**: Recipe optimized for HPC environments
- **Comprehensive documentation**: Deployment and usage guides

## File Structure

```
UBenchAI-Framework/
├── scripts/                              # NEW: Deployment scripts
│   ├── deploy_monitoring_stack.sh        # Main deployment
│   ├── start_node_exporter.sh            # Node exporter
│   ├── start_cadvisor.sh                 # cAdvisor
│   ├── register_target.py                # Target management
│   ├── stop_monitoring.sh                # Stop services
│   ├── check_monitoring_status.sh        # Status check
│   └── README.md                         # Script documentation
├── recipes/
│   ├── monitor-full-stack.yml            # EXISTING: Full stack recipe
│   └── monitor-hpc-stack.yml             # NEW: HPC-optimized recipe
├── docs/                                 # NEW: Documentation
│   ├── MONITORING_DEPLOYMENT_GUIDE.md    # Comprehensive guide
│   └── MONITORING_QUICK_REFERENCE.md     # Quick reference
├── src/ubenchai/monitors/                # EXISTING: Python API
│   ├── manager.py                        # Monitor manager
│   ├── prometheus_client.py              # Prometheus client
│   ├── grafana_client.py                 # Grafana client
│   └── models.py                         # Data models
└── logs/                                 # Runtime data
    ├── prometheus.yml                    # Generated config
    ├── prometheus_data/                  # Time-series data
    ├── prometheus_assets/                # Target files
    ├── grafana_data/                     # Grafana database
    ├── grafana_config/                   # Grafana config
    └── monitoring/                       # Service logs
```

## Configuration Files

### Prometheus Configuration

Generated in `logs/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: node_exporter
    file_sd_configs:
      - files:
          - /prometheus/prometheus_assets/node_targets_*.json
        refresh_interval: 10s
  # ... more jobs
```

### Grafana Datasource

Generated in `logs/grafana_config/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1
datasources:
  - name: UBenchAI Prometheus
    type: prometheus
    url: http://localhost:9090
    isDefault: true
```

### Target Files

Example `logs/prometheus_assets/node_targets.json`:

```json
[
  {
    "targets": [
      "node001:9100",
      "node002:9100"
    ],
    "labels": {
      "job": "system_metrics"
    }
  }
]
```

## Next Steps

### For Users

1. **Review documentation**: Read `docs/MONITORING_DEPLOYMENT_GUIDE.md`
2. **Customize SLURM parameters**: Update account/partition in scripts
3. **Deploy monitoring stack**: Run `sbatch scripts/deploy_monitoring_stack.sh`
4. **Deploy exporters**: Run on compute nodes
5. **Register targets**: Use `register_target.py`
6. **Access Grafana**: View dashboards

### For Developers

1. **Extend dashboards**: Add custom panels in Grafana
2. **Add new exporters**: Create deployment scripts for other exporters
3. **Enhance recipes**: Add more monitoring configurations
4. **Integrate with benchmarks**: Use Python API in benchmark code
5. **Add alerting**: Configure Grafana alerts for critical metrics

## Troubleshooting

Common issues and solutions:

1. **SLURM job fails**: Check account/partition settings
2. **Port conflicts**: Change ports in deployment scripts
3. **Targets not appearing**: Verify JSON format and exporter status
4. **Grafana connection fails**: Check Prometheus health endpoint
5. **No data in dashboards**: Verify scrape jobs and time range

See `docs/MONITORING_DEPLOYMENT_GUIDE.md` for detailed troubleshooting.

## Resources

- **Deployment Guide**: `docs/MONITORING_DEPLOYMENT_GUIDE.md`
- **Quick Reference**: `docs/MONITORING_QUICK_REFERENCE.md`
- **Script Documentation**: `scripts/README.md`
- **Existing Fixes**: `PROMETHEUS_GRAFANA_CONNECTION_FIXES.md`

## Credits

Implementation based on:
- **team9-EUMASTER4HPC2526**: Original monitoring stack implementation
- **UBenchAI-Framework**: Existing monitoring infrastructure
- **Prometheus/Grafana**: Open-source monitoring tools
