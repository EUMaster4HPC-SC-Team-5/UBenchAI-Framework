"""
Unit tests for Server Services module
Tests: ServiceRecipe, ServiceInstance, ServiceRegistry, Port, VolumeMount, ResourceSpec, etc.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import tempfile
import uuid

from ubenchai.servers.services import (
    ServiceRecipe,
    ServiceInstance,
    ServiceRegistry,
    ServiceStatus,
    Port,
    VolumeMount,
    ResourceSpec,
    HealthCheck,
    Endpoint,
)


class TestPort:
    """Tests for Port dataclass"""

    def test_port_creation(self):
        """Test creating a port mapping"""
        port = Port(container_port=8080, host_port=8080, protocol="tcp")
        assert port.container_port == 8080
        assert port.host_port == 8080
        assert port.protocol == "tcp"

    def test_port_defaults(self):
        """Test port with default values"""
        port = Port(container_port=8080)
        assert port.container_port == 8080
        assert port.host_port is None
        assert port.protocol == "tcp"

    def test_port_custom_protocol(self):
        """Test port with custom protocol"""
        port = Port(container_port=53, protocol="udp")
        assert port.protocol == "udp"


class TestVolumeMount:
    """Tests for VolumeMount dataclass"""

    def test_volume_mount_creation(self):
        """Test creating a volume mount"""
        volume = VolumeMount(
            host_path="/host/path", container_path="/container/path", readonly=True
        )
        assert volume.host_path == "/host/path"
        assert volume.container_path == "/container/path"
        assert volume.readonly is True

    def test_volume_mount_defaults(self):
        """Test volume mount with defaults"""
        volume = VolumeMount(host_path="/host/path", container_path="/container/path")
        assert volume.readonly is False


class TestResourceSpec:
    """Tests for ResourceSpec dataclass"""

    def test_resource_spec_creation(self):
        """Test creating resource specifications"""
        resources = ResourceSpec(
            cpu_cores=4, memory_gb=8, gpu_count=2, gpu_type="nvidia-a100"
        )
        assert resources.cpu_cores == 4
        assert resources.memory_gb == 8
        assert resources.gpu_count == 2
        assert resources.gpu_type == "nvidia-a100"

    def test_resource_spec_defaults(self):
        """Test resource spec with default values"""
        resources = ResourceSpec()
        assert resources.cpu_cores == 1
        assert resources.memory_gb == 1
        assert resources.gpu_count == 0
        assert resources.disk_gb == 10
        assert resources.nodes == 1

    def test_resource_spec_validation_success(self):
        """Test valid resource specification"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        assert resources.validate() is True

    def test_resource_spec_validation_invalid_cpu(self):
        """Test validation with invalid CPU cores"""
        resources = ResourceSpec(cpu_cores=0)
        with pytest.raises(ValueError, match="CPU cores must be positive"):
            resources.validate()

    def test_resource_spec_validation_invalid_memory(self):
        """Test validation with invalid memory"""
        resources = ResourceSpec(memory_gb=-1)
        with pytest.raises(ValueError, match="Memory must be positive"):
            resources.validate()

    def test_resource_spec_validation_invalid_gpu(self):
        """Test validation with invalid GPU count"""
        resources = ResourceSpec(gpu_count=-1)
        with pytest.raises(ValueError, match="GPU count cannot be negative"):
            resources.validate()

    def test_to_slurm_resources_basic(self):
        """Test SLURM resource string generation"""
        resources = ResourceSpec(cpu_cores=4, memory_gb=8)
        slurm_str = resources.to_slurm_resources()
        assert "--cpus-per-task=4" in slurm_str
        assert "--mem=8G" in slurm_str

    def test_to_slurm_resources_with_gpu(self):
        """Test SLURM resource string with GPU"""
        resources = ResourceSpec(
            cpu_cores=4, memory_gb=8, gpu_count=2, gpu_type="nvidia-a100"
        )
        slurm_str = resources.to_slurm_resources()
        assert "--gres=gpu:nvidia-a100:2" in slurm_str


class TestHealthCheck:
    """Tests for HealthCheck dataclass"""

    def test_healthcheck_creation(self):
        """Test creating health check configuration"""
        hc = HealthCheck(
            endpoint="/health", interval_seconds=10, timeout_seconds=5, retries=3
        )
        assert hc.endpoint == "/health"
        assert hc.interval_seconds == 10
        assert hc.timeout_seconds == 5
        assert hc.retries == 3

    def test_healthcheck_defaults(self):
        """Test health check with default values"""
        hc = HealthCheck()
        assert hc.endpoint == "/health"
        assert hc.interval_seconds == 10
        assert hc.timeout_seconds == 5
        assert hc.retries == 3
        assert hc.initial_delay == 5


class TestEndpoint:
    """Tests for Endpoint dataclass"""

    def test_endpoint_creation(self):
        """Test creating endpoint"""
        endpoint = Endpoint(
            url="http://localhost", port=8080, protocol="http", description="Main API"
        )
        assert endpoint.url == "http://localhost"
        assert endpoint.port == 8080
        assert endpoint.protocol == "http"
        assert endpoint.description == "Main API"

    def test_endpoint_defaults(self):
        """Test endpoint with defaults"""
        endpoint = Endpoint(url="http://localhost", port=8080)
        assert endpoint.protocol == "http"
        assert endpoint.description is None


class TestServiceRecipe:
    """Tests for ServiceRecipe"""

    @pytest.fixture
    def basic_recipe_data(self):
        """Fixture for basic recipe data"""
        return {
            "name": "test-service",
            "image": "docker://test/image:latest",
            "resources": {"cpu_cores": 2, "memory_gb": 4, "gpu_count": 0},
            "ports": [{"container_port": 8080, "host_port": 8080, "protocol": "tcp"}],
            "environment": {"ENV_VAR": "value"},
            "volumes": [
                {
                    "host_path": "/host/data",
                    "container_path": "/data",
                    "readonly": False,
                }
            ],
        }

    @pytest.fixture
    def recipe_with_healthcheck(self, basic_recipe_data):
        """Fixture for recipe with health check"""
        basic_recipe_data["healthcheck"] = {
            "endpoint": "/health",
            "interval_seconds": 10,
            "timeout_seconds": 5,
            "retries": 3,
            "initial_delay": 5,
        }
        return basic_recipe_data

    def test_recipe_from_yaml(self, basic_recipe_data):
        """Test loading recipe from YAML file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(basic_recipe_data, f)
            temp_path = f.name

        try:
            recipe = ServiceRecipe.from_yaml(temp_path)
            assert recipe.name == "test-service"
            assert recipe.image == "docker://test/image:latest"
            assert recipe.resources.cpu_cores == 2
            assert recipe.resources.memory_gb == 4
            assert len(recipe.ports) == 1
            assert recipe.ports[0].container_port == 8080
        finally:
            Path(temp_path).unlink()

    def test_recipe_from_yaml_file_not_found(self):
        """Test loading recipe from non-existent file"""
        with pytest.raises(FileNotFoundError):
            ServiceRecipe.from_yaml("/nonexistent/path.yml")

    def test_recipe_from_yaml_with_healthcheck(self, recipe_with_healthcheck):
        """Test loading recipe with health check"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(recipe_with_healthcheck, f)
            temp_path = f.name

        try:
            recipe = ServiceRecipe.from_yaml(temp_path)
            assert recipe.healthcheck is not None
            assert recipe.healthcheck.endpoint == "/health"
            assert recipe.healthcheck.interval_seconds == 10
        finally:
            Path(temp_path).unlink()

    def test_recipe_validation_success(self, basic_recipe_data):
        """Test successful recipe validation"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(basic_recipe_data, f)
            temp_path = f.name

        try:
            recipe = ServiceRecipe.from_yaml(temp_path)
            assert recipe.validate() is True
        finally:
            Path(temp_path).unlink()

    def test_recipe_validation_no_name(self):
        """Test recipe validation without name"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(name="", image="test", resources=resources)

        with pytest.raises(ValueError, match="Service name is required"):
            recipe.validate()

    def test_recipe_validation_no_image(self):
        """Test recipe validation without image"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(name="test", image="", resources=resources)

        with pytest.raises(ValueError, match="Container image is required"):
            recipe.validate()

    def test_recipe_validation_invalid_port(self):
        """Test recipe validation with invalid port"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(
            name="test",
            image="test",
            resources=resources,
            ports=[Port(container_port=70000)],
        )

        with pytest.raises(ValueError, match="Invalid port"):
            recipe.validate()

    def test_recipe_to_dict(self, basic_recipe_data):
        """Test converting recipe to dictionary"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(basic_recipe_data, f)
            temp_path = f.name

        try:
            recipe = ServiceRecipe.from_yaml(temp_path)
            recipe_dict = recipe.to_dict()

            assert recipe_dict["name"] == "test-service"
            assert recipe_dict["image"] == "docker://test/image:latest"
            assert "resources" in recipe_dict
            assert "ports" in recipe_dict
            assert "environment" in recipe_dict
        finally:
            Path(temp_path).unlink()


class TestServiceInstance:
    """Tests for ServiceInstance"""

    @pytest.fixture
    def sample_recipe(self):
        """Fixture for sample recipe"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        return ServiceRecipe(
            name="test-service", image="docker://test/image:latest", resources=resources
        )

    def test_instance_creation(self, sample_recipe):
        """Test creating service instance"""
        instance = ServiceInstance(recipe=sample_recipe, orchestrator_handle="job-123")

        assert instance.recipe == sample_recipe
        assert instance.orchestrator_handle == "job-123"
        assert instance.status == ServiceStatus.PENDING
        assert isinstance(instance.id, str)
        assert isinstance(instance.created_at, datetime)

    def test_instance_creation_no_handle(self, sample_recipe):
        """Test instance creation without orchestrator handle"""
        with pytest.raises(ValueError, match="Orchestrator handle is required"):
            ServiceInstance(recipe=sample_recipe, orchestrator_handle="")

    def test_instance_creation_no_recipe(self):
        """Test instance creation without recipe"""
        with pytest.raises(ValueError, match="Service recipe is required"):
            ServiceInstance(recipe=None, orchestrator_handle="job-123")

    def test_instance_update_status(self, sample_recipe):
        """Test updating instance status"""
        instance = ServiceInstance(recipe=sample_recipe, orchestrator_handle="job-123")

        instance.update_status(ServiceStatus.RUNNING)
        assert instance.status == ServiceStatus.RUNNING

    def test_instance_add_endpoint(self, sample_recipe):
        """Test adding endpoint to instance"""
        instance = ServiceInstance(recipe=sample_recipe, orchestrator_handle="job-123")

        instance.add_endpoint("http://localhost", 8080, "http", "Main API")

        assert len(instance.endpoints) == 1
        assert instance.endpoints[0].url == "http://localhost"
        assert instance.endpoints[0].port == 8080

    def test_instance_get_metrics(self, sample_recipe):
        """Test getting instance metrics"""
        instance = ServiceInstance(
            recipe=sample_recipe,
            orchestrator_handle="job-123",
            status=ServiceStatus.RUNNING,
        )

        metrics = instance.get_metrics()

        assert "service_id" in metrics
        assert "status" in metrics
        assert "uptime_seconds" in metrics
        assert metrics["status"] == "running"

    def test_instance_is_healthy(self, sample_recipe):
        """Test health check"""
        instance = ServiceInstance(
            recipe=sample_recipe,
            orchestrator_handle="job-123",
            status=ServiceStatus.RUNNING,
        )

        assert instance.is_healthy() is True

        instance.update_status(ServiceStatus.ERROR)
        assert instance.is_healthy() is False

    def test_instance_to_dict(self, sample_recipe):
        """Test converting instance to dictionary"""
        instance = ServiceInstance(recipe=sample_recipe, orchestrator_handle="job-123")
        instance.add_endpoint("http://localhost", 8080)

        instance_dict = instance.to_dict()

        assert instance_dict["id"] == instance.id
        assert instance_dict["recipe_name"] == "test-service"
        assert instance_dict["status"] == "pending"
        assert instance_dict["orchestrator_handle"] == "job-123"
        assert len(instance_dict["endpoints"]) == 1

    def test_instance_repr(self, sample_recipe):
        """Test instance string representation"""
        instance = ServiceInstance(recipe=sample_recipe, orchestrator_handle="job-123")

        repr_str = repr(instance)
        assert "ServiceInstance" in repr_str
        assert instance.id in repr_str
        assert "test-service" in repr_str


class TestServiceRegistry:
    """Tests for ServiceRegistry"""

    @pytest.fixture
    def registry(self):
        """Fixture for service registry"""
        return ServiceRegistry()

    @pytest.fixture
    def sample_instance(self):
        """Fixture for sample service instance"""
        resources = ResourceSpec(cpu_cores=2, memory_gb=4)
        recipe = ServiceRecipe(
            name="test-service", image="docker://test/image:latest", resources=resources
        )
        return ServiceInstance(recipe=recipe, orchestrator_handle="job-123")

    def test_registry_initialization(self, registry):
        """Test registry initialization"""
        assert registry is not None
        assert registry.get_service_count() == 0

    def test_register_service(self, registry, sample_instance):
        """Test registering a service"""
        result = registry.register_service(sample_instance)

        assert result is True
        assert registry.get_service_count() == 1

    def test_register_duplicate_service(self, registry, sample_instance):
        """Test registering duplicate service"""
        registry.register_service(sample_instance)
        result = registry.register_service(sample_instance)

        assert result is False
        assert registry.get_service_count() == 1

    def test_unregister_service(self, registry, sample_instance):
        """Test unregistering a service"""
        registry.register_service(sample_instance)
        result = registry.unregister_service(sample_instance.id)

        assert result is True
        assert registry.get_service_count() == 0

    def test_unregister_nonexistent_service(self, registry):
        """Test unregistering non-existent service"""
        result = registry.unregister_service("nonexistent-id")
        assert result is False

    def test_get_service(self, registry, sample_instance):
        """Test getting service by ID"""
        registry.register_service(sample_instance)
        retrieved = registry.get_service(sample_instance.id)

        assert retrieved is not None
        assert retrieved.id == sample_instance.id

    def test_get_nonexistent_service(self, registry):
        """Test getting non-existent service"""
        retrieved = registry.get_service("nonexistent-id")
        assert retrieved is None

    def test_get_all_services(self, registry):
        """Test getting all services"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(name="test", image="test", resources=resources)

        for i in range(3):
            instance = ServiceInstance(recipe=recipe, orchestrator_handle=f"job-{i}")
            registry.register_service(instance)

        services = registry.get_all_services()
        assert len(services) == 3

    def test_get_services_by_status(self, registry):
        """Test getting services filtered by status"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(name="test", image="test", resources=resources)

        instance1 = ServiceInstance(recipe=recipe, orchestrator_handle="job-1")
        instance1.update_status(ServiceStatus.RUNNING)

        instance2 = ServiceInstance(recipe=recipe, orchestrator_handle="job-2")
        instance2.update_status(ServiceStatus.STOPPED)

        registry.register_service(instance1)
        registry.register_service(instance2)

        running_services = registry.get_services_by_status(ServiceStatus.RUNNING)
        assert len(running_services) == 1
        assert running_services[0].status == ServiceStatus.RUNNING

    def test_service_exists(self, registry, sample_instance):
        """Test checking if service exists"""
        assert registry.service_exists(sample_instance.id) is False

        registry.register_service(sample_instance)
        assert registry.service_exists(sample_instance.id) is True

    def test_cleanup_stale_services(self, registry):
        """Test cleaning up stale services"""
        resources = ResourceSpec()
        recipe = ServiceRecipe(name="test", image="test", resources=resources)

        # Create an old instance
        old_instance = ServiceInstance(recipe=recipe, orchestrator_handle="job-1")
        old_instance.created_at = datetime.now() - timedelta(hours=48)
        old_instance.update_status(ServiceStatus.STOPPED)

        # Create a recent instance
        new_instance = ServiceInstance(recipe=recipe, orchestrator_handle="job-2")
        new_instance.update_status(ServiceStatus.STOPPED)

        registry.register_service(old_instance)
        registry.register_service(new_instance)

        count = registry.cleanup_stale_services(max_age_hours=24)

        assert count == 1
        assert registry.get_service_count() == 1

    def test_clear_all(self, registry, sample_instance):
        """Test clearing all services"""
        registry.register_service(sample_instance)
        count = registry.clear_all()

        assert count == 1
        assert registry.get_service_count() == 0

    def test_thread_safety(self, registry):
        """Test thread-safe operations"""
        import threading

        resources = ResourceSpec()
        recipe = ServiceRecipe(name="test", image="test", resources=resources)

        def register_services():
            for i in range(10):
                instance = ServiceInstance(
                    recipe=recipe,
                    orchestrator_handle=f"job-{threading.current_thread().name}-{i}",
                )
                registry.register_service(instance)

        threads = [threading.Thread(target=register_services) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 50 services (5 threads × 10 services)
        assert registry.get_service_count() == 50


class TestServiceStatus:
    """Tests for ServiceStatus enum"""

    def test_status_values(self):
        """Test service status enum values"""
        assert ServiceStatus.PENDING.value == "pending"
        assert ServiceStatus.STARTING.value == "starting"
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.STOPPING.value == "stopping"
        assert ServiceStatus.STOPPED.value == "stopped"
        assert ServiceStatus.ERROR.value == "error"
        assert ServiceStatus.UNKNOWN.value == "unknown"

    def test_status_comparison(self):
        """Test status comparison"""
        status1 = ServiceStatus.RUNNING
        status2 = ServiceStatus.RUNNING
        status3 = ServiceStatus.STOPPED

        assert status1 == status2
        assert status1 != status3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
