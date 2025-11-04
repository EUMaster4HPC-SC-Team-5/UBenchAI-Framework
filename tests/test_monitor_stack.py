"""
Test cases for Prometheus/Grafana integration in the monitoring module.
"""

import os
import tempfile
from pathlib import Path
import pytest
import yaml

from ubenchai.monitors.manager import MonitorManager
from ubenchai.monitors.models import MonitorStatus


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create recipes directory
        recipes_dir = workspace / "recipes"
        recipes_dir.mkdir()
        
        # Create a test recipe
        recipe = {
            "name": "test-monitor",
            "description": "Test monitoring recipe",
            "collection_interval_seconds": 5,
            "retention_period_hours": 1,
            "exporters": [
                {
                    "type": "prometheus",
                    "port": 9090,
                    "scrape_configs": [
                        {
                            "job_name": "test",
                            "static_configs": [
                                {"targets": ["localhost:9100"]}
                            ]
                        }
                    ]
                }
            ],
            "grafana": {
                "enabled": True,
                "port": 3000,
                "dashboards": [
                    {
                        "type": "system",
                        "title": "System Overview"
                    }
                ]
            }
        }
        
        with open(recipes_dir / "test-monitor.yml", "w") as f:
            yaml.safe_dump(recipe, f)
            
        yield workspace


def test_monitoring_stack_deployment(temp_workspace):
    """Test full monitoring stack deployment."""
    manager = MonitorManager(
        recipe_directory=str(temp_workspace / "recipes"),
        output_root=str(temp_workspace / "logs")
    )
    
    # Start monitor
    instance = manager.start_monitor(
        recipe_name="test-monitor",
        targets=["localhost"],
        mode="local"
    )
    
    # Verify monitor started successfully
    assert instance.status == MonitorStatus.RUNNING
    assert instance.prometheus_url is not None
    assert instance.grafana_url is not None
    
    # Verify files were created
    monitor_dir = temp_workspace / "logs" / "monitors" / instance.id
    assert (monitor_dir / "instance.json").exists()
    assert (monitor_dir / "prometheus").exists()
    assert (monitor_dir / "grafana").exists()
    
    # Stop monitor
    assert manager.stop_monitor(instance.id)
    
    # Verify monitor stopped
    instance = manager._load_instance_from_disk(instance.id)
    assert instance is not None
    assert instance.status == MonitorStatus.STOPPED