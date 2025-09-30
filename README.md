# UBenchAI-Framework
Unified Benchmarking Framework for AI Workflows
## Setup and Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

If you don't have Poetry installed, you can install it by following the [official installation guide](https://python-poetry.org/docs/#installation).

### Installation Steps for Development
1. **Clone the repository**:
```bash
   git clone https://github.com/EUMaster4HPC-SC-Team-5/UBenchAI-Framework.git
   cd UBenchAI-Framework
```
2. **Install dependencies**
```bash
   poetry install
```
3. **Activate the virtual environment**:
```bash
eval $(poetry env activate)
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

## Technology Stack
- **Python 3.12**: Primary development language.
- **Poetry**: Dependency management and build system
- **PyYAML 6.0.3+**: Service recipe parsing and configuration management
- **Loguru 0.7.3+**: Advanced logging with structured output and rotation
- **Black 25.9.0+**: Code formatting
- **Apptainer/Singularity:** Container runtime optimized for HPC environments
- **Pyslurm**: Python bindings for SLURM API 
- **kubernetes**: Official Kubernetes Python client (optional?)
