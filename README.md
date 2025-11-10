# UBenchAI-Framework: Unified Benchmarking Framework for AI Factory Workloads
![CI Tests](https://github.com/EUMaster4HPC-SC-Team-5/UBenchAI-Framework/workflows/CI%20-%20Tests%20and%20Linting/badge.svg)

## Project Overview
UBenchAI-Framework is a modular benchmarking framework designed to evaluate the performance of AI Factory components on the MeluXina supercomputer. This project is part of the EUMaster4HPC Student Challenge 2025-2026.

**Team 5 Members:**
- Alberto Taddei (@albtad01)
- Arianna Amadini (@AriannaAmadini)
- Dennys Huber (@dnyse)
- Elizabeth Koleva (@Elizabethvk)

## Setup and Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

If you don't have Poetry installed, you can install it by following the [official installation guide](https://python-poetry.org/docs/#installation).

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/EUMaster4HPC-SC-Team-5/UBenchAI-Framework.git
   cd UBenchAI-Framework
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Activate the virtual environment**:
   ```bash
   eval $(poetry env activate)
   ```

4. **Verify installation**:
   ```bash
   poetry run ubenchai --version
   poetry run ubenchai --help
   ```

## Running the Framework

The UBenchAI Framework can be run in multiple ways:

### Method 1: Via Poetry (Recommended for Development)
```bash
# Using the installed command
poetry run ubenchai server list

# With verbose logging
poetry run ubenchai -v server start --recipe llm-inference

# Run client commands
poetry run ubenchai client run --recipe stress-test
```

### Method 2: Via Python Module
```bash
# Run as a module
poetry run python -m ubenchai server list
```

### Method 3: Via main.py
```bash
# Direct execution of main.py
poetry run python main.py server list
```

### Method 4: After Shell Activation
```bash
# Activate the environment first
poetry shell

# Then run directly
ubenchai server list
ubenchai client run --recipe test
ubenchai monitor start --recipe metrics
```

## Command Reference

### Server Module
Manage containerized AI services:

```bash
# Start a service from a recipe
ubenchai server start --recipe <recipe-name> [--config <config-file>]

# Stop a running service
ubenchai server stop <service-id>

# List available/running services
ubenchai server list

# Get service status
ubenchai server status <service-id>
```

**Example:**
```bash
poetry run ubenchai server start --recipe llm-inference
```

### Client Module
Run benchmarking workloads:

```bash
# Run a client workload
ubenchai client run --recipe <recipe-name> [--overrides <overrides-file>]

# Stop a running client
ubenchai client stop <run-id>

# List available/running clients
ubenchai client list

# Get client run status
ubenchai client status <run-id>
```

**Example:**
```bash
poetry run ubenchai client run --recipe stress-test
```

### Monitor Module
Start monitoring and metrics collection:

```bash
# Start monitoring
ubenchai monitor start --recipe <recipe-name> [--targets <service1,service2>]

# Stop monitoring
ubenchai monitor stop <monitor-id>

# List monitors
ubenchai monitor list

# Show metrics
ubenchai monitor metrics <monitor-id> [--output <file>]

# Generate report
ubenchai monitor report <monitor-id> [--format html|json|pdf]
```

**Example:**
```bash
poetry run ubenchai monitor start --recipe system-metrics --targets api-server,db-server
```

### Code Formatting

The project uses Black for code formatting:

```bash
# Format all code
poetry run black src/

# Check formatting without making changes
poetry run black --check src/
```

### Working on Specific Modules


#### Server Module
```bash
# Test server commands
poetry run ubenchai server start --recipe test-recipe
```

#### Client Module
```bash
# Test client commands
poetry run ubenchai client run --recipe test-workload
```

#### Monitor Module
```bash
# Test monitor commands
poetry run ubenchai monitor start --recipe test-monitor
```

#### Reporting Module
```bash
# Test report generation
poetry run ubenchai monitor report <monitor-id> --format html
```

## Logging

The framework uses `loguru` for structured logging:

- **Default log level**: INFO
- **Verbose mode**: DEBUG (use `-v` or `--verbose` flag)
- **Log files**: Automatically created in `logs/` directory with rotation
- **Log format**: `YYYY-MM-DD HH:mm:ss | LEVEL | module:function - message`

**Example with verbose logging:**
```bash
poetry run ubenchai -v server start --recipe test
```

## Environment Variables

You can configure the framework using environment variables:

```bash
# Set log level
export UBENCHAI_LOG_LEVEL=DEBUG

# Set configuration directory
export UBENCHAI_CONFIG_DIR=/path/to/configs

# Run with environment
poetry run ubenchai server list
```

## Testing 

```bash
# Run all tests
poetry run pytest tests/

# Run specific test file
poetry run pytest tests/test_services.py

# Run specific test class
poetry run pytest tests/test_services.py::TestServiceRecipe

# Run specific test function
poetry run pytest tests/test_services.py::TestServiceRecipe::test_recipe_creation

# Run with verbose output
poetry run pytest tests/ -v

# Run with extra verbose output (show test names)
poetry run pytest tests/ -vv
```

### Running Tests by Category

```bash
# Run only unit tests
poetry run pytest tests/ -m unit

# Run only integration tests
poetry run pytest tests/ -m integration

# Skip slow tests
poetry run pytest tests/ -m "not slow"
```

### Running with Coverage

```bash
# Run tests with coverage report
poetry run pytest tests/ --cov=src/ubenchai

# With detailed missing lines
poetry run pytest tests/ --cov=src/ubenchai --cov-report=term-missing

# Generate HTML coverage report
poetry run pytest tests/ --cov=src/ubenchai --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

```
## Common Options

```bash
# Stop on first failure
poetry run pytest tests/ -x

# Show local variables on failure
poetry run pytest tests/ -l

# Run last failed tests
poetry run pytest tests/ --lf

# Run failed tests first, then others
poetry run pytest tests/ --ff

# Quiet output (less verbose)
poetry run pytest tests/ -q

# Show print statements
poetry run pytest tests/ -s
```

## Debugging Tests

```bash
# Drop into debugger on failure
poetry run pytest tests/ --pdb

# Drop into debugger at start of test
poetry run pytest tests/ --trace

# Show which fixtures are being used
poetry run pytest tests/ --fixtures

# Show available tests without running
poetry run pytest tests/ --collect-only
```

## GitHub Actions

Tests run automatically on GitHub when you:
- Push to a branch.
- Create a pull request.

## Writing New Tests

### Test Template

```python
import pytest
from ubenchai.servers.services import ServiceRecipe

class TestMyFeature:
    """Tests for my new feature"""

    @pytest.fixture
    def sample_data(self):
        """Fixture providing test data"""
        return {"key": "value"}

    def test_something(self, sample_data):
        """Test description"""
        # Arrange
        expected = "value"
        
        # Act
        result = sample_data["key"]
        
        # Assert
        assert result == expected
```

### Test Naming

- Files: `test_*.py`
- Classes: `Test*`
- Functions: `test_*`

### Using Markers

```python
@pytest.mark.unit
def test_fast_unit_test():
    """This is a fast unit test"""
    assert True

@pytest.mark.integration
def test_component_integration():
    """This tests multiple components"""
    assert True

@pytest.mark.slow
def test_slow_operation():
    """This test takes time"""
    assert True
```

## Troubleshooting

### "Module not found" errors
```bash
# Reinstall dependencies
poetry install

# Verify installation
poetry run python -c "import ubenchai; print(ubenchai.__version__)"
```

### "Command not found: ubenchai"
```bash
# Make sure you're using poetry run
poetry run ubenchai --help

# Or activate the environment first
poetry shell
ubenchai --help
```

## Architecture

### Server Module
The Server Module provides containerized service management for benchmark workloads using Apptainer containers. It handles service lifecycle management, request routing, and resource orchestration across both local development and HPC cluster environments.

```mermaid
classDiagram
    class ServerManager {
        -orchestrator: Orchestrator
        -recipe_loader: RecipeLoader
        -service_registry: ServiceRegistry
        -logger: Logger
        -request_handler: ServiceRequestHandler
        +start_service(recipe_name: str, config: dict) ServiceInstance
        +stop_service(service_id: str) bool
        +list_available_services() List~ServiceRecipe~
        +list_running_services() List~ServiceInstance~
        +check_service_health(service_id: str) HealthStatus
        +get_service_status(service_id: str) ServiceStatus
        +handle_request(service_name: str, endpoint: str, payload: dict) Response
        +forward_request(container: ServiceInstance, endpoint: str, payload: dict) Response
    }

    class ServiceRecipe {
        -name: str
        -image: str
        -resources: ResourceSpec
        -ports: List~Port~
        -environment: dict
        -volumes: List~VolumeMount~
        -healthcheck: HealthCheck
        +validate() bool
        +to_dict() dict
        +from_yaml(yaml_path: str) ServiceRecipe
    }

    class ServiceInstance {
        -id: str
        -recipe: ServiceRecipe
        -status: ServiceStatus
        -created_at: datetime
        -orchestrator_handle: str
        -endpoints: List~Endpoint~
        +get_logs() str
        +get_metrics() dict
        +restart() bool
        +scale(replicas: int) bool
    }

    class Orchestrator {
        <<interface>>
        +deploy_service(recipe: ServiceRecipe) str
        +stop_service(handle: str) bool
        +get_service_status(handle: str) ServiceStatus
        +get_service_logs(handle: str) str
        +scale_service(handle: str, replicas: int) bool
    }

    class KubernetesOrchestrator {
        -k8s_client: ApiClient
        -namespace: str
        +deploy_service(recipe: ServiceRecipe) str
        +stop_service(handle: str) bool
        +get_service_status(handle: str) ServiceStatus
        +get_service_logs(handle: str) str
        +scale_service(handle: str, replicas: int) bool
        -create_deployment(recipe: ServiceRecipe) V1Deployment
        -create_service(recipe: ServiceRecipe) V1Service
        -wait_for_ready(handle: str) bool
    }

    class SlurmOrchestrator {
        -slurm_client: SlurmClient
        -job_templates: dict
        +deploy_service(recipe: ServiceRecipe) str
        +stop_service(handle: str) bool
        +get_service_status(handle: str) ServiceStatus
        +get_service_logs(handle: str) str
        +scale_service(handle: str, replicas: int) bool
        -create_batch_script(recipe: ServiceRecipe) str
        -submit_job(script: str) str
        -monitor_job(job_id: str) JobStatus
    }

    class ApptainerRuntime {
        -image_path: str
        -bind_mounts: List~str~
        +build_command(recipe: ServiceRecipe) List~str~
        +validate_image(image_path: str) bool
        +get_gpu_args() List~str~
    }

    class RecipeLoader {
        -recipe_directory: str
        -cache: dict
        +load_recipe(name: str) ServiceRecipe
        +validate_recipe(recipe: ServiceRecipe) List~ValidationError~
        +list_available_recipes() List~str~
        +reload_recipes() bool
        -parse_yaml(file_path: str) dict
    }

    class ServiceRegistry {
        -running_services: dict
        -service_lock: Lock
        +register_service(instance: ServiceInstance) bool
        +unregister_service(service_id: str) bool
        +get_service(service_id: str) ServiceInstance
        +get_all_services() List~ServiceInstance~
        +cleanup_stale_services() int
    }

    class ResourceSpec {
        -cpu_cores: int
        -memory_gb: int
        -gpu_count: int
        -gpu_type: str
        -disk_gb: int
        -network_bandwidth: int
        +validate() bool
        +to_k8s_resources() V1ResourceRequirements
        +to_slurm_resources() str
    }

    class HealthCheck {
        -endpoint: str
        -interval_seconds: int
        -timeout_seconds: int
        -retries: int
        -initial_delay: int
        +execute(service_endpoint: str) HealthStatus
        +is_healthy(response: HttpResponse) bool
    }

    class ServiceStatus {
        <<enumeration>>
        PENDING
        STARTING
        RUNNING
        STOPPING
        STOPPED
        ERROR
        UNKNOWN
    }


    %% Relationships
    ServerManager --> ServiceRegistry
    ServerManager --> RecipeLoader
    ServerManager --> Orchestrator
    ServerManager --> ServiceInstance
    
    ServiceInstance --> ServiceRecipe
    ServiceInstance --> ServiceStatus
    
    ServiceRecipe --> ResourceSpec
    ServiceRecipe --> HealthCheck
    
    Orchestrator <|-- KubernetesOrchestrator
    Orchestrator <|-- SlurmOrchestrator
    
    KubernetesOrchestrator --> ApptainerRuntime
    SlurmOrchestrator --> ApptainerRuntime
    
    RecipeLoader --> ServiceRecipe
```
#### Core Components
- **ServerManager**: Central orchestration component that manages the complete lifecycle of containerized AI services. Coordinates between recipe loading, service registry, orchestration, and request handling. Integrates directly with both Kubernetes and SLURM environments.
- **ServiceRegistry**: Registry that tracks all running service instances. Provides service discovery, cleanup of stale services, and access coordination.
- **ServiceInstance**: Represents a running containerized service with monitoring capabilities.
- **ServiceRecipe**: YAML-based service configuration defining container images, resource requirements, health checks, and deployment parameters.
- **RecipeLoader**: Manages discovery, loading, and validation of service recipes from the file system.
- **Orchestrator Implementations**
    - **KubernetesOrchestrator**: Native Kubernetes integration with Deployment and Service management. (Initial focus will lay on slurm)
    - **SlurmOrchestrator**: HPC cluster job submission with batch script generation and monitoring

### Client Module
The Client Module provides workload generation and benchmarking capabilities against containerized AI services. It handles client lifecycle management, recipe loading, run tracking, orchestration (local or SLURM), health resolution, and metrics collection.
```mermaid
classDiagram
    class ClientManager {
        -orchestrator: Orchestrator
        -recipe_loader: ClientRecipeLoader
        -run_registry: RunRegistry
        -logger: Logger
        -health_resolver: HealthResolver
        +start_client(recipe_name: str, overrides: dict) ClientRun
        +stop_client(run_id: str) bool
        +list_available_clients() List~ClientRecipe~
        +list_running_clients() List~ClientRun~
        +get_client_status(run_id: str) RunStatus
        +validate_recipe(recipe_name: str) ValidationReport
    }

    class ClientRecipe {
        -name: str
        -target: TargetSpec
        -workload: WorkloadSpec
        -dataset: DatasetSpec
        -orchestration: OrchestrationSpec
        -output: OutputSpec
        -repro: ReproSpec
        +validate() bool
        +to_dict() dict
        +from_yaml(yaml_path: str) ClientRecipe
    }

    class ClientRun {
        -id: str
        -recipe: ClientRecipe
        -status: RunStatus
        -created_at: datetime
        -orchestrator_handle: str
        -artifacts_dir: str
        +get_logs() str
        +get_metrics() dict
    }

    class ClientRecipeLoader {
        -recipe_directory: str
        -cache: dict
        +load_recipe(name: str) ClientRecipe
        +validate_recipe(recipe: ClientRecipe) List~ValidationError~
        +list_available_recipes() List~str~
        +reload_recipes() bool
        -parse_yaml(file_path: str) dict
    }

    class RunRegistry {
        -runs: dict
        -run_lock: Lock
        +register(run: ClientRun) bool
        +unregister(run_id: str) bool
        +get(run_id: str) ClientRun
        +get_all() List~ClientRun~
        +cleanup_stale_runs() int
    }

    class Orchestrator {
        <<interface>>
        +submit(run: ClientRun) str
        +stop(handle: str) bool
        +status(handle: str) RunStatus
        +stdout(handle: str) str
    }

    class SlurmOrchestrator {
        -slurm_client: SlurmClient
        -job_templates: dict
        +submit(run: ClientRun) str
        +stop(handle: str) bool
        +status(handle: str) RunStatus
        +stdout(handle: str) str
    }

    class KubernetesOrchestrator {
        -k8s_client: ApiClient
        -namespace: str
        +submit(run: ClientRun) str
        +stop(handle: str) bool
        +status(handle: str) RunStatus
        +stdout(handle: str) str
    }

    class HealthResolver {
        +resolve_endpoint(recipe: ClientRecipe) TargetSpec
        +read_server_endpoint_file(path: str) TargetSpec
        +check_connectivity(target: TargetSpec) bool
    }

    class RunStatus {
        <<enumeration>>
        SUBMITTED
        RUNNING
        COMPLETED
        FAILED
        CANCELED
        UNKNOWN
    }

    %% Relationships
    ClientManager --> ClientRecipeLoader
    ClientManager --> RunRegistry
    ClientManager --> Orchestrator
    ClientManager --> HealthResolver
    ClientManager --> ClientRun
    ClientRun --> ClientRecipe
    ClientRun --> RunStatus
    Orchestrator <|-- SlurmOrchestrator
    Orchestrator <|-- KubernetesOrchestrator
    ClientRecipeLoader --> ClientRecipe
    RunRegistry --> ClientRun
```
#### Core Components

- **ClientManager**: Central orchestration component for managing benchmarking clients. Coordinates recipe loading, run tracking, orchestration, and health validation. Provides CLI commands for start/stop/list/status.  
- **ClientRecipe**: YAML-based configuration defining workload pattern (open/closed loop), dataset source, target endpoint (HTTP/gRPC/SQL/S3), and orchestration parameters (local/Slurm).  
- **ClientRun**: Represents a single benchmarking run. Stores recipe, run status, timestamps, orchestrator handle, and output artifacts.  
- **ClientRecipeLoader**: Manages discovery, parsing, and validation of client recipes from the filesystem. Provides schema validation and error reporting.  
- **RunRegistry**: Tracks active and historical client runs, supports cleanup, and ensures consistent metadata storage.  
- **Orchestrator Implementations**  
  - **SlurmOrchestrator**: Submits and manages benchmarking clients as HPC jobs via SLURM, handling job scripts and status polling.  
  - **KubernetesOrchestrator**: Provides analogous orchestration for K8s (optional, future extension).  
- **HealthResolver**: Resolves and validates server endpoints before client execution. Performs connectivity checks to ensure the target is reachable.


### Monitor Module

Start monitoring and metrics collection:

```bash
# Start monitoring
ubenchai monitor start --recipe <recipe-name> [--targets <service1,service2>]

# Stop monitoring
ubenchai monitor stop <monitor-id>

# List monitors
ubenchai monitor list

```

**Example:**
```bash
poetry run ubenchai monitor start --recipe vllm-monitor --targets 12345678
```

**See the [Complete Monitoring Workflow](#complete-monitoring-workflow) section below for a detailed step-by-step guide.**

## Complete Monitoring Workflow

This section provides a complete step-by-step guide for deploying a service (vLLM) and monitoring it with Prometheus and Grafana.

### Step 1: Start the vLLM Service

First, deploy the vLLM inference service on MeluXina:

```bash
poetry run ubenchai server start --recipe vllm
```

**Expected Output:**
```
✓ Service started successfully!
   Service ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
   Recipe: vllm-singlenode
   Status: running
   Orchestrator Handle: 12345678
```

**Important:** Note the **Orchestrator Handle** (SLURM job ID) - you'll need this for monitoring. In this example, it's `12345678`.

You can also find running jobs with:
```bash
squeue --me
```

### Step 2: Start the Monitoring Stack

Start Prometheus and Grafana to monitor your vLLM service using the job ID from Step 1:

```bash
poetry run ubenchai monitor start --recipe vllm-monitor --targets 12345678
```

**Expected Output:**
```
✓ Monitoring stack started!
   Monitor ID: m9n8o7p6-q5r4-3210-stuv-wx9876543210
   Recipe: vllm-monitor

   Prometheus: http://mel2091:9090
   Grafana: http://mel2091:3000 (admin/admin)
```

**Note:** The node names (e.g., `mel2091`) will vary depending on which compute nodes your jobs are assigned to.

### Step 3: Access Monitoring via SSH Port Forwarding

Since the monitoring services run on MeluXina compute nodes (not accessible directly from the internet), you need to set up SSH port forwarding.

#### Option A: Forward Both Services (Recommended)

**On your local machine**, open a terminal and run:

```bash
ssh -L 9090:mel2091:9090 -L 3000:mel2091:3000 <your-username>@login.lxp.lu
```

Replace:
- `mel2091` with the actual compute node from your monitor output
- `<your-username>` with your MeluXina username

#### Option B: Forward Services Separately

If you prefer separate tunnels:

**Prometheus tunnel:**
```bash
ssh -L 9090:mel2091:9090 <your-username>@login.lxp.lu
```

**Grafana tunnel (in a second terminal):**
```bash
ssh -L 3000:mel2091:3000 <your-username>@login.lxp.lu
```

### Step 4: Access the Web Interfaces

With the SSH tunnels active, open your web browser:

**Prometheus:**
- URL: http://localhost:9090
- Check targets: http://localhost:9090/targets
- Query interface: http://localhost:9090/graph

**Grafana:**
- URL: http://localhost:3000
- Username: `admin`
- Password: `admin` (change on first login)

### Step 5: Explore Metrics in Prometheus

Once Prometheus is accessible:

1. Go to http://localhost:9090/targets
2. Verify your vLLM service appears as a target with status "UP"
3. Navigate to the Graph tab: http://localhost:9090/graph
4. Try some example queries:
   ```
   # Request rate
   rate(vllm:request_success_total[5m])
   
   # GPU cache usage
   vllm:gpu_cache_usage_perc
   
   # Request latency (p95)
   histogram_quantile(0.95, rate(vllm:e2e_request_latency_seconds_bucket[5m]))
   ```

### Step 6: View Grafana Dashboard

The monitoring stack automatically provisions a vLLM dashboard:

1. Go to http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards** → **Browse**
4. Open the **vLLM Metrics** dashboard

The dashboard includes panels for:
- Request Rate
- GPU Cache Usage  
- Request Latency (p50, p95)
- Running Requests

### Step 7: Customize Grafana Dashboards

#### Add a New Panel

1. Open the vLLM dashboard
2. Click the **Add** button → **Visualization**
3. In the query editor, enter a PromQL query:
   ```
   vllm:num_requests_waiting
   ```
4. Configure visualization settings:
   - **Panel title:** "Waiting Requests"
   - **Visualization type:** Time series or Stat
   - **Unit:** Short (for counts)
5. Click **Apply** to save

#### Edit Existing Panels

1. Hover over any panel
2. Click the dropdown menu (⋮) → **Edit**
3. Modify the query, visualization type, or display options
4. Click **Apply** to save changes

#### Save Dashboard Changes

After making modifications:
1. Click the **Save dashboard** icon (💾) at the top
2. Add a description of changes
3. Click **Save**

#### Create a New Dashboard

1. Click **+** → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as the data source
4. Build your custom panels with PromQL queries
5. Save the dashboard

**Example Custom Queries:**
```promql
# Tokens per second
rate(vllm:prompt_tokens_total[5m]) + rate(vllm:generation_tokens_total[5m])

# Cache hit rate
vllm:cache_hit_total / (vllm:cache_hit_total + vllm:cache_miss_total)

# Average batch size
avg_over_time(vllm:avg_prompt_throughput_toks_per_s[5m])
```

### Step 8: Stop Monitoring When Done

To stop the monitoring stack:

```bash
# List running monitors to get the monitor ID
poetry run ubenchai monitor list

# Stop the monitor (use ID from list output)
poetry run ubenchai monitor stop m9n8o7p6
```

To stop the vLLM service:

```bash
# Stop by service ID
poetry run ubenchai server stop a1b2c3d4

# Or stop by SLURM job ID
poetry run ubenchai server stop 12345678
```

#### Core Components  
- **MonitorManager**: Central orchestration component that manages the complete lifecycle of monitoring runs. Coordinates recipe loading, monitor instances, Prometheus/Grafana integration, and metric export.  
- **MonitorInstance**: Represents a running monitoring session linked to a recipe. Provides status, logs, health checks, and collected metrics.  
- **MonitorRecipe**: YAML-based configuration defining monitoring targets, collection intervals, retention settings, and exporter options.  
- **RecipeLoader**: Manages discovery, validation, and loading of monitor recipes from the filesystem.  
- **PrometheusClient**: Deploys and manages Prometheus instances. Handles scraping configuration, queries, health checks, and metric export to files.  
- **GrafanaClient**: Deploys Grafana, connects it to Prometheus, and provisions dashboards for visualization.  


## Technology Stack
- **Python 3.12**: Primary development language.
- **Poetry**: Dependency management and build system
- **PyYAML 6.0.3+**: Service recipe parsing and configuration management
- **Loguru 0.7.3+**: Advanced logging with structured output and rotation
- **Black 25.9.0+**: Code formatting
- **Apptainer/Singularity:** Container runtime optimized for HPC environments
- **Pyslurm**: Python bindings for SLURM API 
- **kubernetes**: Official Kubernetes Python client (optional?)

### **Dennys Huber** - Server Module Lead
**Primary Responsibilities:**
- Lead the Core Server Framework
- Design ServerManager architecture
- Define ServiceRecipe YAML format
- Create ServiceRegistry tracking system

---

### **Alberto Taddei** - Client Module Lead
**Primary Responsibilities:**
- Lead the Core Client Framework
- Design ClientManager architecture
- Define client benchmark recipes
- Create workload execution patterns

---

### **Arianna Amadini** - Monitor Module Lead
**Primary Responsibilities:**
- Lead the Core Monitor Framework
- Design monitoring data collection
- Define metrics storage format
- Plan Grafana integration approach

---

### **Elizabeth Koleva** - Reporting Module Lead
**Primary Responsibilities:**
- Lead the Core Reporting Framework
- Design report generation system
- Define report templates
- Plan visualization approaches

---

## Shared Responsibilities (All Team Members)

- **Everyone:** Participate in design brainstorming sessions
- **Everyone:** Review and provide feedback on all designs

## Communication Plan

### Weekly Sync Meetings
- **Day:** To be decided by team
- **Duration:** 1 hour
- **Agenda:** Progress updates, blockers, design discussions

### Bi-weekly Mentor Sessions
- Present design progress
- Get feedback on technical approach
- Clarify requirements

### Async Communication
- Use GitHub Issues for task-specific discussions
- Update issue status regularly
- Tag team members for reviews

## Acknowledgments
- EUMaster4HPC Program
- LuxProvide and MeluXina Supercomputer
- Dr. Farouk Mansouri for supervision
