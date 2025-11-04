#!/usr/bin/env python3
"""
Test script to validate Prometheus and Grafana connection fixes.
"""

import tempfile
import time
from pathlib import Path
import yaml
import requests
from loguru import logger

from src.ubenchai.monitors.manager import MonitorManager
from src.ubenchai.monitors.models import MonitorStatus


def create_test_recipe(workspace: Path) -> None:
    """Create a test monitoring recipe."""
    recipes_dir = workspace / "recipes"
    recipes_dir.mkdir(exist_ok=True)

    recipe = {
        "name": "connection-test",
        "description": "Test Prometheus-Grafana connection",
        "collection_interval_seconds": 5,
        "retention_period_hours": 1,
        "exporters": [
            {
                "type": "prometheus",
                "port": 9090,
                "scrape_configs": [
                    {
                        "job_name": "test",
                        "static_configs": [{"targets": ["localhost:9100"]}],
                    }
                ],
            }
        ],
        "grafana": {
            "enabled": True,
            "port": 3001,  # Use different port to avoid conflicts
            "admin_user": "admin",
            "admin_password": "testpass",
            "dashboards": [{"type": "system", "title": "System Test"}],
        },
    }

    with open(recipes_dir / "connection-test.yml", "w") as f:
        yaml.safe_dump(recipe, f)


def test_prometheus_health(url: str, timeout: int = 30) -> bool:
    """Test if Prometheus is healthy."""
    logger.info(f"Testing Prometheus health at {url}")

    for i in range(timeout):
        try:
            response = requests.get(f"{url}/-/healthy", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Prometheus health check passed")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < timeout - 1:  # Don't sleep on last iteration
            time.sleep(1)

    logger.error("❌ Prometheus health check failed")
    return False


def test_grafana_health(url: str, timeout: int = 60) -> bool:
    """Test if Grafana is healthy."""
    logger.info(f"Testing Grafana health at {url}")

    for i in range(timeout):
        try:
            response = requests.get(f"{url}/api/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Grafana health check passed")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < timeout - 1:  # Don't sleep on last iteration
            time.sleep(1)

    logger.error("❌ Grafana health check failed")
    return False


def test_datasource_connection(
    grafana_url: str, admin_user: str, admin_password: str
) -> bool:
    """Test Prometheus datasource connection in Grafana."""
    logger.info("Testing Prometheus datasource connection in Grafana")

    try:
        # Wait a bit for datasource to be provisioned
        time.sleep(10)

        auth = (admin_user, admin_password)
        response = requests.get(
            f"{grafana_url}/api/datasources/name/UBenchAI%20Prometheus/health",
            auth=auth,
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "OK":
                logger.info("✅ Datasource connection test passed")
                return True
            else:
                logger.error(f"❌ Datasource connection failed: {result}")
                return False
        else:
            logger.error(f"❌ Failed to test datasource: HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing datasource connection: {e}")
        return False


def main():
    """Run the connection test."""
    logger.info("🚀 Starting Prometheus-Grafana connection test")

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        logger.info(f"Using workspace: {workspace}")

        # Create test recipe
        create_test_recipe(workspace)

        # Initialize monitor manager
        manager = MonitorManager(
            recipe_directory=str(workspace / "recipes"),
            output_root=str(workspace / "logs"),
        )

        try:
            # Start monitor
            logger.info("Starting monitoring stack...")
            instance = manager.start_monitor(
                recipe_name="connection-test", targets=["localhost"], mode="local"
            )

            # Verify instance started
            if instance.status != MonitorStatus.RUNNING:
                logger.error(f"❌ Monitor failed to start: {instance.status}")
                return False

            logger.info(f"✅ Monitor started successfully")
            logger.info(f"  Prometheus URL: {instance.prometheus_url}")
            logger.info(f"  Grafana URL: {instance.grafana_url}")

            # Test Prometheus health if available
            if instance.prometheus_url:
                if not test_prometheus_health(instance.prometheus_url):
                    return False
            else:
                logger.info("⚠️ Prometheus not available, skipping health check")

            # Test Grafana health if available
            if instance.grafana_url:
                if not test_grafana_health(instance.grafana_url):
                    return False

                # Test datasource connection
                if not test_datasource_connection(
                    instance.grafana_url,
                    instance.recipe.grafana.get("admin_user", "admin"),
                    instance.recipe.grafana.get("admin_password", "admin"),
                ):
                    return False
            else:
                logger.info("⚠️ Grafana not available, skipping health check")

            logger.info("🎉 All connection tests passed!")

            # Stop monitor
            logger.info("Stopping monitor...")
            if manager.stop_monitor(instance.id):
                logger.info("✅ Monitor stopped successfully")
            else:
                logger.warning("⚠️ Failed to stop monitor cleanly")

            return True

        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
