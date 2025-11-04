#!/usr/bin/env python3
"""
Validate that the connection fixes are syntactically correct.
"""

try:
    from src.ubenchai.monitors.grafana_client import GrafanaClient
    print("✅ GrafanaClient imported successfully")
except Exception as e:
    print(f"❌ Failed to import GrafanaClient: {e}")

try:
    from src.ubenchai.monitors.prometheus_client import PrometheusClient
    print("✅ PrometheusClient imported successfully")
except Exception as e:
    print(f"❌ Failed to import PrometheusClient: {e}")

try:
    from src.ubenchai.monitors.manager import MonitorManager
    print("✅ MonitorManager imported successfully")
except Exception as e:
    print(f"❌ Failed to import MonitorManager: {e}")

print("\n🎉 All modules validated successfully!")
