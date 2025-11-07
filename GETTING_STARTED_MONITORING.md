# Getting Started with UBenchAI Monitoring

## 🎯 Quick Start (5 Minutes)

### 1. Deploy the Monitoring Stack

```bash
cd /path/to/UBenchAI-Framework

# Submit monitoring stack to SLURM
sbatch scripts/deploy_monitoring_stack.sh

# Check job status
squeue -u $USER
```

### 2. Wait for Deployment

```bash
# Monitor deployment progress
tail -f logs/monitoring_stack.out

# You should see:
# ✓ Prometheus configuration created
# ✓ Grafana datasource configuration created
# ✓ Prometheus started at http://<ip>:9090
# ✓ Grafana started at http://<ip>:3000
```

### 3. Access Grafana

```bash
# Get the monitoring node IP
cat logs/grafana_data/grafana_ip.txt

# Open in browser: http://<ip>:3000
# Login: admin / ubenchai
```

**That's it!** You now have a working monitoring stack.

---

## 📊 Adding Monitoring to Your Nodes

### Deploy Exporters on Compute Nodes

```bash
# Deploy Node Exporter (system metrics)
sbatch scripts/start_node_exporter.sh

# Deploy cAdvisor (container metrics)
sbatch scripts/start_cadvisor.sh
```

### Register the Targets

```bash
# Find your node IPs
squeue -u $USER -o "%.18i %.9P %.20j %.8u %.2t %.10M %.6D %R"

# Register node exporter
python3 scripts/register_target.py add node --target "node001:9100"

# Register cAdvisor
python3 scripts/register_target.py add cadvisor --target "node001:8080"
```

### Verify in Grafana

1. Go to http://<monitoring-ip>:3000
2. Click **Dashboards** → **Browse**
3. Open **Node Exporter - System Metrics**
4. You should see metrics from your nodes!

---

## 🔧 Common Tasks

### Check Status

```bash
bash scripts/check_monitoring_status.sh
```

### View Logs

```bash
# Prometheus logs
tail -f logs/monitoring/prometheus.err

# Grafana logs
tail -f logs/monitoring/grafana.err
```

### List Registered Targets

```bash
# List all node exporter targets
python3 scripts/register_target.py list node

# List all cAdvisor targets
python3 scripts/register_target.py list cadvisor
```

### Stop Monitoring

```bash
bash scripts/stop_monitoring.sh
```

---

## 📚 What You Get

### Pre-configured Dashboards

1. **Node Exporter - System Metrics**
   - CPU, Memory, Disk, Network usage
   - System load and uptime

2. **LLM Performance** (when using monitor-hpc-stack recipe)
   - Request rate and latency
   - GPU utilization
   - Inference throughput

3. **Vector DB Performance**
   - Query rate and latency
   - Index size and memory

4. **Container Metrics**
   - Container CPU and memory
   - Network and disk I/O

5. **GPU Cluster Overview**
   - Multi-GPU utilization
   - Power and temperature
   - PCIe throughput

### Available Metrics

**System Metrics** (Node Exporter):
- `node_cpu_seconds_total`: CPU usage by core
- `node_memory_MemAvailable_bytes`: Available memory
- `node_disk_io_time_seconds_total`: Disk I/O time
- `node_network_receive_bytes_total`: Network traffic

**Container Metrics** (cAdvisor):
- `container_cpu_usage_seconds_total`: Container CPU
- `container_memory_usage_bytes`: Container memory
- `container_network_receive_bytes_total`: Container network

**GPU Metrics** (DCGM):
- `DCGM_FI_DEV_GPU_UTIL`: GPU utilization
- `DCGM_FI_DEV_FB_USED`: GPU memory used
- `DCGM_FI_DEV_GPU_TEMP`: GPU temperature
- `DCGM_FI_DEV_POWER_USAGE`: GPU power consumption

---

## 🐍 Using Python API

### Basic Usage

```python
from ubenchai.monitors.manager import MonitorManager

# Initialize manager
manager = MonitorManager(
    recipe_directory="recipes",
    output_root="logs"
)

# Start monitoring
instance = manager.start_monitor(
    recipe_name="monitor-hpc-stack",
    targets=["node001:9100", "node002:9100"],
    mode="slurm"
)

print(f"Prometheus: {instance.prometheus_url}")
print(f"Grafana: {instance.grafana_url}")

# Your benchmark code here
# ...

# Stop monitoring
manager.stop_monitor(instance.id)
```

### Advanced Usage

```python
# List available recipes
recipes = manager.list_available_recipes()
print(f"Available recipes: {recipes}")

# List running monitors
monitors = manager.list_running_monitors()
for monitor in monitors:
    print(f"Monitor {monitor['id']}: {monitor['status']}")

# Query Prometheus
from ubenchai.monitors.prometheus_client import PrometheusClient

prom = PrometheusClient(workspace_root=Path("logs"))
result = prom.query(
    url=instance.prometheus_url,
    query="rate(node_cpu_seconds_total[5m])"
)
print(result)
```

---

## 🎨 Creating Custom Dashboards

### In Grafana UI

1. Login to Grafana
2. Click **+** → **Dashboard**
3. Click **Add visualization**
4. Select **UBenchAI Prometheus** as datasource
5. Enter PromQL query (e.g., `rate(node_cpu_seconds_total[5m])`)
6. Customize visualization
7. Save dashboard

### Example PromQL Queries

```promql
# CPU usage percentage
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage percentage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Disk usage percentage
100 - ((node_filesystem_avail_bytes{mountpoint="/"} * 100) / node_filesystem_size_bytes{mountpoint="/"})

# Network receive rate (MB/s)
rate(node_network_receive_bytes_total[5m]) / 1024 / 1024

# GPU utilization
DCGM_FI_DEV_GPU_UTIL

# Container CPU usage
rate(container_cpu_usage_seconds_total[5m])
```

---

## 🔍 Troubleshooting

### Monitoring Stack Not Starting

**Check SLURM job:**
```bash
squeue -u $USER
cat logs/monitoring_stack.err
```

**Common issues:**
- Wrong SLURM account → Update `#SBATCH --account=` in script
- Insufficient resources → Reduce memory/CPU requirements
- Module not available → Check `module avail Apptainer`

### Targets Not Appearing

**Check target file:**
```bash
cat logs/prometheus_assets/node_targets.json
```

**Verify exporter is running:**
```bash
curl http://node001:9100/metrics
```

**Check Prometheus targets:**
```bash
curl http://localhost:9090/api/v1/targets | jq
```

### No Data in Dashboards

**Check time range:**
- Click time picker in Grafana (top right)
- Select "Last 5 minutes" or "Last 15 minutes"
- Enable auto-refresh

**Verify metrics exist:**
```bash
# Query Prometheus directly
curl 'http://localhost:9090/api/v1/query?query=up'
```

**Check scrape status:**
- Go to Prometheus: http://<ip>:9090/targets
- Verify targets are "UP"

### Can't Access Grafana

**Check if Grafana is running:**
```bash
curl http://localhost:3000/api/health
```

**Check firewall:**
```bash
# Ensure port 3000 is accessible
netstat -tuln | grep 3000
```

**Use SSH tunnel:**
```bash
# On your local machine
ssh -L 3000:monitoring-node:3000 user@cluster
# Then access: http://localhost:3000
```

---

## 📖 Documentation

### Essential Guides

- **[Deployment Guide](docs/MONITORING_DEPLOYMENT_GUIDE.md)**: Complete deployment instructions
- **[Quick Reference](docs/MONITORING_QUICK_REFERENCE.md)**: Common commands and queries
- **[Architecture](docs/MONITORING_ARCHITECTURE.md)**: System architecture and data flow
- **[Scripts README](scripts/README.md)**: Detailed script documentation

### Key Concepts

**Prometheus**: Time-series database that scrapes metrics from exporters

**Grafana**: Visualization platform for creating dashboards

**Exporters**: Services that expose metrics in Prometheus format

**Service Discovery**: Automatic target discovery using JSON files

**PromQL**: Query language for Prometheus metrics

---

## 🚀 Next Steps

### For Beginners

1. ✅ Deploy monitoring stack (you did this!)
2. ✅ Access Grafana dashboards
3. 📝 Explore pre-configured dashboards
4. 📝 Add more compute nodes
5. 📝 Create custom dashboard

### For Advanced Users

1. 📝 Integrate with benchmark code using Python API
2. 📝 Create custom monitoring recipes
3. 📝 Set up alerting rules
4. 📝 Configure recording rules for performance
5. 📝 Deploy GPU monitoring with DCGM

### For Developers

1. 📝 Extend dashboard templates
2. 📝 Add new exporter types
3. 📝 Implement custom metrics
4. 📝 Create automated deployment workflows
5. 📝 Contribute improvements back to UBenchAI

---

## 💡 Tips & Best Practices

### Performance

- **Adjust scrape intervals** based on your needs (default: 15s)
- **Use recording rules** for expensive queries
- **Limit retention** if storage is limited (default: 30 days)

### Security

- **Change default password** in `deploy_monitoring_stack.sh`
- **Use SSH tunneling** for remote access
- **Restrict network access** with firewall rules

### Monitoring

- **Monitor the monitors**: Check Prometheus and Grafana health
- **Set up alerts**: Get notified of issues
- **Regular backups**: Export important dashboards

### Organization

- **Label your targets**: Add meaningful labels when registering
- **Organize dashboards**: Use folders in Grafana
- **Document custom queries**: Add descriptions to panels

---

## 🆘 Getting Help

### Check Documentation

1. Read the error message carefully
2. Check the troubleshooting section above
3. Review the deployment guide
4. Search the quick reference

### Debug Steps

1. Check SLURM job status: `squeue -u $USER`
2. Review logs: `tail -f logs/monitoring_stack.err`
3. Verify services: `bash scripts/check_monitoring_status.sh`
4. Test connectivity: `curl http://localhost:9090/-/healthy`

### Common Solutions

- **Port conflicts**: Change ports in deployment scripts
- **Permission issues**: Check file/directory permissions
- **Module errors**: Verify required modules are loaded
- **Network issues**: Check firewall and network configuration

---

## 📊 Example Workflow

### Complete Monitoring Setup

```bash
# 1. Deploy monitoring stack
cd /path/to/UBenchAI-Framework
sbatch scripts/deploy_monitoring_stack.sh

# 2. Wait for deployment
sleep 60

# 3. Deploy exporters on 3 nodes
for i in {1..3}; do
  sbatch scripts/start_node_exporter.sh
done

# 4. Get node IPs
squeue -u $USER -o "%.18i %.20j %R" | grep node_exporter

# 5. Register targets (replace with actual IPs)
python3 scripts/register_target.py add node --target "10.0.1.1:9100"
python3 scripts/register_target.py add node --target "10.0.1.2:9100"
python3 scripts/register_target.py add node --target "10.0.1.3:9100"

# 6. Check status
bash scripts/check_monitoring_status.sh

# 7. Get Grafana URL
cat logs/grafana_data/grafana_ip.txt

# 8. Access Grafana and view dashboards!
```

---

## 🎓 Learning Resources

### Prometheus

- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Best Practices](https://prometheus.io/docs/practices/)

### Grafana

- [Grafana Documentation](https://grafana.com/docs/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Alerting Guide](https://grafana.com/docs/grafana/latest/alerting/)

### Exporters

- [Node Exporter](https://github.com/prometheus/node_exporter)
- [cAdvisor](https://github.com/google/cadvisor)
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter)

---

## ✅ Checklist

### Initial Setup
- [ ] Deploy monitoring stack
- [ ] Verify Prometheus is running
- [ ] Verify Grafana is accessible
- [ ] Login to Grafana

### Add Monitoring
- [ ] Deploy node exporters
- [ ] Register targets
- [ ] Verify targets in Prometheus
- [ ] Check dashboards in Grafana

### Customization
- [ ] Change default password
- [ ] Create custom dashboard
- [ ] Add labels to targets
- [ ] Configure retention period

### Production Ready
- [ ] Set up alerting
- [ ] Document custom queries
- [ ] Configure backups
- [ ] Test disaster recovery

---

**🎉 Congratulations!** You now have a production-ready monitoring stack for your HPC benchmarking workloads.

For detailed information, see the comprehensive guides in the `docs/` directory.
