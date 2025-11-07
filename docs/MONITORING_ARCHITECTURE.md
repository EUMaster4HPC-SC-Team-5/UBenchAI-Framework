# UBenchAI Monitoring Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         SLURM HPC Cluster                              │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                      Compute Nodes Layer                         │ │
│  │                                                                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │ │
│  │  │  Node 001   │  │  Node 002   │  │  GPU Node   │            │ │
│  │  │             │  │             │  │             │            │ │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │            │ │
│  │  │ │Node Exp │ │  │ │Node Exp │ │  │ │Node Exp │ │            │ │
│  │  │ │:9100    │ │  │ │:9100    │ │  │ │:9100    │ │            │ │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │            │ │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │            │ │
│  │  │ │cAdvisor │ │  │ │cAdvisor │ │  │ │DCGM Exp │ │            │ │
│  │  │ │:8080    │ │  │ │:8080    │ │  │ │:9400    │ │            │ │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │            │ │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │             │            │ │
│  │  │ │ Ollama  │ │  │ │ Qdrant  │ │  │             │            │ │
│  │  │ │:11434   │ │  │ │:6333    │ │  │             │            │ │
│  │  │ └─────────┘ │  │ └─────────┘ │  │             │            │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │ │
│  │         │                │                │                    │ │
│  │         └────────────────┼────────────────┘                    │ │
│  │                          │                                     │ │
│  └──────────────────────────┼─────────────────────────────────────┘ │
│                             │                                       │
│                             │ Metrics Scraping                      │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Monitoring Node                             │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │              Prometheus (port 9090)                    │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │         Time-Series Database (TSDB)             │ │ │  │
│  │  │  │         Retention: 30 days                       │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │      File-based Service Discovery                │ │ │  │
│  │  │  │  - node_targets.json                             │ │ │  │
│  │  │  │  - cadvisor_targets.json                         │ │ │  │
│  │  │  │  - gpu_targets.json                              │ │ │  │
│  │  │  │  - ollama_targets.json                           │ │ │  │
│  │  │  │  - qdrant_targets.json                           │ │ │  │
│  │  │  │  Refresh: 10s                                    │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │         PromQL Query Engine                      │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  └────────────────────────┬───────────────────────────────┘ │  │
│  │                           │ HTTP API                        │  │
│  │                           ▼                                 │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │              Grafana (port 3000)                       │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │      Provisioned Datasource                      │ │ │  │
│  │  │  │      - UBenchAI Prometheus                       │ │ │  │
│  │  │  │      - URL: http://localhost:9090                │ │ │  │
│  │  │  │      - Auto-configured on startup                │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │      Pre-configured Dashboards                   │ │ │  │
│  │  │  │  - Node Exporter - System Metrics                │ │ │  │
│  │  │  │  - LLM Performance                               │ │ │  │
│  │  │  │  - Vector DB Performance                         │ │ │  │
│  │  │  │  - Container Metrics                             │ │ │  │
│  │  │  │  - GPU Cluster Overview                          │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  │                                                        │ │  │
│  │  │  ┌──────────────────────────────────────────────────┐ │ │  │
│  │  │  │      Web UI & Visualization                      │ │ │  │
│  │  │  │      Credentials: admin / ubenchai               │ │ │  │
│  │  │  └──────────────────────────────────────────────────┘ │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
┌─────────────┐
│   Exporter  │  (Node Exporter, cAdvisor, DCGM, etc.)
│   :9100     │
└──────┬──────┘
       │
       │ 1. Expose metrics at /metrics endpoint
       │    Format: Prometheus text format
       │    Example: node_cpu_seconds_total{cpu="0",mode="idle"} 12345.67
       │
       ▼
┌─────────────┐
│ Prometheus  │
│   :9090     │
└──────┬──────┘
       │
       │ 2. Scrape metrics every 15s
       │    - Read target files (file_sd_configs)
       │    - HTTP GET /metrics
       │    - Parse and store in TSDB
       │
       │ 3. Store time-series data
       │    - Compressed storage
       │    - 30-day retention
       │    - Indexed by labels
       │
       ▼
┌─────────────┐
│   Grafana   │
│   :3000     │
└──────┬──────┘
       │
       │ 4. Query via PromQL
       │    - HTTP POST /api/v1/query
       │    - Example: rate(node_cpu_seconds_total[5m])
       │
       │ 5. Visualize in dashboards
       │    - Time-series graphs
       │    - Gauges, tables, heatmaps
       │    - Auto-refresh every 5s
       │
       ▼
┌─────────────┐
│    User     │
│  (Browser)  │
└─────────────┘
```

## Component Details

### Exporters

#### Node Exporter (port 9100)
**Purpose**: System hardware and OS metrics

**Metrics Exposed**:
- CPU usage by core and mode
- Memory usage (total, free, cached, buffers)
- Disk I/O and usage
- Network traffic and errors
- System load and uptime
- Filesystem statistics

**Deployment**: One per compute node

#### cAdvisor (port 8080)
**Purpose**: Container resource usage

**Metrics Exposed**:
- Container CPU usage
- Container memory usage
- Container network I/O
- Container disk I/O
- Container lifecycle events

**Deployment**: One per node running containers

#### DCGM Exporter (port 9400)
**Purpose**: NVIDIA GPU metrics

**Metrics Exposed**:
- GPU utilization (%)
- GPU memory usage
- GPU temperature
- GPU power consumption
- PCIe throughput
- SM clock frequency

**Deployment**: One per GPU node

### Prometheus (port 9090)

**Components**:

1. **Scrape Engine**
   - Pulls metrics from exporters
   - Configurable intervals (default: 15s)
   - Handles target discovery

2. **Time-Series Database (TSDB)**
   - Compressed storage format
   - Efficient indexing by labels
   - Configurable retention (default: 30 days)

3. **Query Engine**
   - PromQL query language
   - Aggregation functions
   - Range queries and instant queries

4. **HTTP API**
   - Query endpoint: `/api/v1/query`
   - Range query: `/api/v1/query_range`
   - Targets: `/api/v1/targets`
   - Health: `/-/healthy`

**File-based Service Discovery**:
```json
[
  {
    "targets": ["node001:9100", "node002:9100"],
    "labels": {
      "job": "system_metrics",
      "datacenter": "meluxina"
    }
  }
]
```

### Grafana (port 3000)

**Components**:

1. **Datasource**
   - Prometheus connection
   - Auto-provisioned on startup
   - Query timeout: 60s

2. **Dashboards**
   - JSON-based configuration
   - Auto-provisioned from files
   - Organized in folders

3. **Panels**
   - Time-series graphs
   - Stat panels
   - Tables and gauges
   - Heatmaps

4. **Variables**
   - Dynamic dashboard filtering
   - Query-based values
   - Multi-select support

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Network Topology                         │
│                                                             │
│  Compute Nodes                    Monitoring Node          │
│  ┌──────────────┐                ┌──────────────┐         │
│  │ node001      │                │ monitor001   │         │
│  │ 10.0.1.1     │                │ 10.0.1.100   │         │
│  │              │                │              │         │
│  │ :9100 ◄──────┼────────────────┼─► Prometheus │         │
│  │ :8080 ◄──────┼────────────────┼─► :9090      │         │
│  └──────────────┘                │      │       │         │
│                                  │      ▼       │         │
│  ┌──────────────┐                │   Grafana   │         │
│  │ node002      │                │   :3000     │         │
│  │ 10.0.1.2     │                │      ▲       │         │
│  │              │                └──────┼───────┘         │
│  │ :9100 ◄──────┼────────────────────────┘                │
│  │ :8080 ◄──────┼────────────────────────┘                │
│  └──────────────┘                                         │
│                                  ▲                         │
│  ┌──────────────┐                │                         │
│  │ gpu001       │                │                         │
│  │ 10.0.1.10    │                │                         │
│  │              │                │                         │
│  │ :9100 ◄──────┼────────────────┘                         │
│  │ :9400 ◄──────┼────────────────┘                         │
│  └──────────────┘                                         │
│                                                            │
│                                  User Access              │
│                                  http://10.0.1.100:3000   │
│                                  (Grafana Web UI)         │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Workflow

```
┌──────────────────────────────────────────────────────────────┐
│                   Deployment Sequence                        │
└──────────────────────────────────────────────────────────────┘

Step 1: Deploy Monitoring Stack
┌─────────────────────────────────────┐
│ sbatch deploy_monitoring_stack.sh   │
└─────────────────┬───────────────────┘
                  │
                  ├─► Pull Prometheus container
                  ├─► Pull Grafana container
                  ├─► Create configuration files
                  ├─► Start Prometheus
                  ├─► Wait for Prometheus ready
                  ├─► Start Grafana
                  ├─► Wait for Grafana ready
                  └─► Download dashboards

Step 2: Deploy Exporters
┌─────────────────────────────────────┐
│ sbatch start_node_exporter.sh       │
│ sbatch start_cadvisor.sh            │
└─────────────────┬───────────────────┘
                  │
                  ├─► Pull exporter containers
                  ├─► Start exporters
                  └─► Verify health

Step 3: Register Targets
┌─────────────────────────────────────┐
│ register_target.py add node ...     │
└─────────────────┬───────────────────┘
                  │
                  ├─► Update JSON target files
                  └─► Prometheus auto-discovers (10s)

Step 4: Verify
┌─────────────────────────────────────┐
│ check_monitoring_status.sh          │
└─────────────────┬───────────────────┘
                  │
                  ├─► Check processes
                  ├─► Check ports
                  ├─► Check SLURM jobs
                  └─► Show recent logs

Step 5: Access Dashboards
┌─────────────────────────────────────┐
│ http://<monitoring-ip>:3000         │
└─────────────────────────────────────┘
```

## Storage Layout

```
logs/
├── prometheus.yml                    # Prometheus configuration
├── prometheus_data/                  # Time-series database
│   ├── 01HXXX/                      # Data blocks (2h chunks)
│   │   ├── chunks/
│   │   │   └── 000001               # Compressed metric data
│   │   ├── index                    # Block index
│   │   └── meta.json                # Block metadata
│   ├── wal/                         # Write-ahead log
│   │   └── 00000001                 # WAL segments
│   └── prometheus_ip.txt            # Monitoring node IP
├── prometheus_assets/                # Service discovery
│   ├── node_targets.json            # Node exporter targets
│   ├── cadvisor_targets.json        # cAdvisor targets
│   ├── gpu_targets.json             # GPU exporter targets
│   ├── ollama_targets.json          # Ollama targets
│   └── qdrant_targets.json          # Qdrant targets
├── grafana_data/                     # Grafana database
│   ├── grafana.db                   # SQLite database
│   ├── plugins/                     # Installed plugins
│   └── grafana_ip.txt               # Monitoring node IP
├── grafana_config/                   # Grafana configuration
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml       # Datasource config
│       └── dashboards/
│           ├── default.yml          # Dashboard provider
│           ├── node-exporter.json   # System metrics dashboard
│           └── ...                  # Other dashboards
└── monitoring/                       # Service logs
    ├── prometheus.out               # Prometheus stdout
    ├── prometheus.err               # Prometheus stderr
    ├── grafana.out                  # Grafana stdout
    └── grafana.err                  # Grafana stderr
```

## Security Considerations

### Authentication
- Grafana: Username/password (default: admin/ubenchai)
- Prometheus: No authentication by default
- Recommendation: Change default password, enable HTTPS

### Network Security
- Exporters expose metrics on all interfaces (0.0.0.0)
- Use firewall rules to restrict access
- Consider SSH tunneling for remote access

### Data Privacy
- Metrics may contain sensitive information
- Configure metric relabeling to drop sensitive labels
- Limit retention period for compliance

## Performance Characteristics

### Resource Usage

| Component | CPU | Memory | Disk I/O | Network |
|-----------|-----|--------|----------|---------|
| Prometheus | Low | Medium | Medium | Low |
| Grafana | Low | Low | Low | Low |
| Node Exporter | Very Low | Very Low | Very Low | Very Low |
| cAdvisor | Low | Low | Low | Low |
| DCGM Exporter | Very Low | Very Low | Very Low | Very Low |

### Scalability

- **Targets**: Prometheus can handle 1000+ targets
- **Metrics**: Millions of time-series
- **Queries**: Concurrent queries supported
- **Retention**: 30 days default (adjustable)

### Optimization Tips

1. **Reduce scrape frequency** for less critical metrics
2. **Use recording rules** for expensive queries
3. **Limit metric cardinality** (avoid high-cardinality labels)
4. **Configure retention** based on storage capacity
5. **Use federation** for multi-cluster setups

## Integration Points

### UBenchAI Python API
```python
from ubenchai.monitors.manager import MonitorManager

manager = MonitorManager()
instance = manager.start_monitor(
    recipe_name="monitor-hpc-stack",
    mode="slurm"
)
```

### SLURM Integration
- Job submission via `sbatch`
- Resource allocation
- Node assignment
- Job monitoring

### Container Runtime
- Apptainer/Singularity
- Docker images converted to SIF
- Bind mounts for configuration
- Environment variables for settings

## Monitoring the Monitors

### Health Checks

```bash
# Prometheus health
curl http://localhost:9090/-/healthy

# Prometheus ready
curl http://localhost:9090/-/ready

# Grafana health
curl http://localhost:3000/api/health

# Exporter metrics
curl http://localhost:9100/metrics
```

### Logs

```bash
# Prometheus logs
tail -f logs/monitoring/prometheus.err

# Grafana logs
tail -f logs/monitoring/grafana.err

# SLURM job logs
tail -f logs/monitoring_stack.out
```

### Metrics

Monitor the monitoring stack itself:
- `prometheus_tsdb_storage_blocks_bytes`: Storage usage
- `prometheus_target_scrapes_total`: Scrape count
- `grafana_api_response_status_total`: API requests
- `process_cpu_seconds_total`: CPU usage
- `process_resident_memory_bytes`: Memory usage
