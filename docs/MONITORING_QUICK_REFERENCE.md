# UBenchAI Monitoring Quick Reference

## Quick Commands

### Deployment

```bash
# Deploy monitoring stack
sbatch scripts/deploy_monitoring_stack.sh

# Deploy node exporter on compute node
sbatch scripts/start_node_exporter.sh

# Deploy cAdvisor on compute node
sbatch scripts/start_cadvisor.sh
```

### Status & Management

```bash
# Check status
bash scripts/check_monitoring_status.sh

# Stop all monitoring
bash scripts/stop_monitoring.sh

# View logs
tail -f logs/monitoring/prometheus.err
tail -f logs/monitoring/grafana.err
```

### Target Registration

```bash
# Add target
python3 scripts/register_target.py add node --target "node001:9100"

# Remove target
python3 scripts/register_target.py remove node --target "node001:9100"

# List targets
python3 scripts/register_target.py list node
```

### Access URLs

```bash
# Get monitoring node IP
cat logs/grafana_data/grafana_ip.txt

# Access services
# Prometheus: http://<ip>:9090
# Grafana:    http://<ip>:3000
```

## Default Ports

| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics database & query |
| Grafana | 3000 | Dashboards & visualization |
| Node Exporter | 9100 | System metrics |
| cAdvisor | 8080 | Container metrics |
| DCGM Exporter | 9400 | GPU metrics |
| Pushgateway | 9091 | Push metrics |

## Default Credentials

**Grafana:**
- Username: `admin`
- Password: `ubenchai`

## Common PromQL Queries

```promql
# CPU Usage (%)
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory Usage (%)
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Disk Usage (%)
100 - ((node_filesystem_avail_bytes{mountpoint="/"} * 100) / node_filesystem_size_bytes{mountpoint="/"})

# Network Receive Rate (bytes/sec)
rate(node_network_receive_bytes_total[5m])

# GPU Utilization (%)
DCGM_FI_DEV_GPU_UTIL

# GPU Memory Used (bytes)
DCGM_FI_DEV_FB_USED

# Container CPU Usage
rate(container_cpu_usage_seconds_total[5m])

# Container Memory Usage
container_memory_usage_bytes
```

## File Locations

```
UBenchAI-Framework/
├── scripts/
│   ├── deploy_monitoring_stack.sh    # Main deployment
│   ├── start_node_exporter.sh        # Node exporter
│   ├── start_cadvisor.sh             # cAdvisor
│   ├── register_target.py            # Target management
│   ├── stop_monitoring.sh            # Stop services
│   └── check_monitoring_status.sh    # Status check
├── recipes/
│   └── monitor-hpc-stack.yml         # HPC monitoring recipe
├── logs/
│   ├── prometheus.yml                # Prometheus config
│   ├── prometheus_data/              # Time-series data
│   ├── prometheus_assets/            # Target files
│   ├── grafana_data/                 # Grafana database
│   ├── grafana_config/               # Grafana config
│   └── monitoring/                   # Service logs
└── containers/
    ├── prometheus.sif                # Prometheus image
    ├── grafana.sif                   # Grafana image
    ├── node_exporter.sif             # Node exporter image
    └── cadvisor.sif                  # cAdvisor image
```

## Troubleshooting Checklist

- [ ] Check SLURM job status: `squeue -u $USER`
- [ ] Check service processes: `bash scripts/check_monitoring_status.sh`
- [ ] Check Prometheus logs: `tail logs/monitoring/prometheus.err`
- [ ] Check Grafana logs: `tail logs/monitoring/grafana.err`
- [ ] Test Prometheus health: `curl http://localhost:9090/-/healthy`
- [ ] Test Grafana health: `curl http://localhost:3000/api/health`
- [ ] Verify targets: `curl http://localhost:9090/api/v1/targets`
- [ ] Check port availability: `netstat -tuln | grep 9090`

## Example Workflow

### 1. Initial Setup

```bash
# Clone/navigate to UBenchAI
cd /path/to/UBenchAI-Framework

# Deploy monitoring stack
sbatch scripts/deploy_monitoring_stack.sh

# Wait for deployment (check logs)
tail -f logs/monitoring_stack.out
```

### 2. Deploy Exporters

```bash
# On compute nodes, deploy exporters
sbatch scripts/start_node_exporter.sh
sbatch scripts/start_cadvisor.sh

# Get node IPs
squeue -u $USER -o "%.18i %.9P %.20j %.8u %.2t %.10M %.6D %R"
```

### 3. Register Targets

```bash
# Register node exporters
python3 scripts/register_target.py add node --target "node001:9100"
python3 scripts/register_target.py add node --target "node002:9100"

# Register cAdvisor
python3 scripts/register_target.py add cadvisor --target "node001:8080"
```

### 4. Verify Setup

```bash
# Check all services
bash scripts/check_monitoring_status.sh

# Get Grafana URL
cat logs/grafana_data/grafana_ip.txt
# Access: http://<ip>:3000
```

### 5. Run Benchmarks

```bash
# Your benchmark workload runs here
# Metrics are automatically collected
```

### 6. Cleanup

```bash
# Stop monitoring
bash scripts/stop_monitoring.sh

# Or cancel SLURM jobs
scancel -u $USER -n ubenchai_monitoring,node_exporter,cadvisor
```

## SLURM Job Management

```bash
# List monitoring jobs
squeue -u $USER -n ubenchai_monitoring,node_exporter,cadvisor

# Cancel specific job
scancel <job_id>

# Cancel all monitoring jobs
scancel -u $USER -n ubenchai_monitoring

# View job details
scontrol show job <job_id>

# View job output
cat logs/monitoring_stack.out
cat logs/monitoring_stack.err
```

## Grafana Dashboard Tips

### Navigate Dashboards
1. Login to Grafana
2. Click **Dashboards** → **Browse**
3. Select **UBenchAI Monitoring** folder
4. Choose a dashboard

### Adjust Time Range
- Click time picker (top right)
- Select range or use quick options
- Enable auto-refresh for live monitoring

### Create Alerts
1. Edit panel
2. Click **Alert** tab
3. Configure conditions
4. Set notification channels

### Export Dashboard
1. Open dashboard
2. Click **Share** → **Export**
3. Save JSON file
4. Import on other Grafana instances

## API Examples

### Prometheus API

```bash
# Query current values
curl 'http://localhost:9090/api/v1/query?query=up'

# Query time range
curl 'http://localhost:9090/api/v1/query_range?query=up&start=2024-01-01T00:00:00Z&end=2024-01-01T01:00:00Z&step=15s'

# List all metrics
curl http://localhost:9090/api/v1/label/__name__/values

# Get targets
curl http://localhost:9090/api/v1/targets
```

### Grafana API

```bash
# Get datasources
curl -u admin:ubenchai http://localhost:3000/api/datasources

# Get dashboards
curl -u admin:ubenchai http://localhost:3000/api/search

# Create dashboard
curl -u admin:ubenchai \
  -H "Content-Type: application/json" \
  -d @dashboard.json \
  http://localhost:3000/api/dashboards/db
```

## Performance Tuning

### Reduce Scrape Frequency
Edit `logs/prometheus.yml`:
```yaml
global:
  scrape_interval: 30s  # Increase from 15s
```

### Limit Retention
Edit `scripts/deploy_monitoring_stack.sh`:
```bash
--storage.tsdb.retention.time=7d  # Reduce from 30d
```

### Optimize Queries
Use recording rules for expensive queries:
```yaml
groups:
  - name: performance
    interval: 30s
    rules:
      - record: job:cpu_usage:avg
        expr: avg(rate(node_cpu_seconds_total[5m]))
```

## Security Hardening

### Change Default Password
Edit `scripts/deploy_monitoring_stack.sh`:
```bash
--env GF_SECURITY_ADMIN_PASSWORD=your_secure_password
```

### Enable Authentication
Add to Prometheus startup:
```bash
--web.config.file=/path/to/web-config.yml
```

### Use SSH Tunnel
```bash
# On local machine
ssh -L 3000:monitoring-node:3000 user@cluster
# Access: http://localhost:3000
```

## Useful Links

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Prometheus Targets: http://localhost:9090/targets
- Prometheus Config: http://localhost:9090/config
- Grafana Datasources: http://localhost:3000/datasources
