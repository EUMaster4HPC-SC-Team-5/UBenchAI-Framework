# Prometheus and Grafana Connection Fixes

## Issues Identified and Fixed

### 1. **Connection Validation and Timing Issues**
**Problem**: Grafana was being deployed immediately after Prometheus without waiting for Prometheus to be ready, causing connection failures.

**Fix**: 
- Added `wait_for_ready()` method in `PrometheusClient` that checks both health and ready endpoints
- Modified `MonitorManager` to wait for Prometheus readiness before deploying Grafana
- Added proper timeout and retry logic with configurable intervals

### 2. **Enhanced Datasource Configuration**
**Problem**: Basic Prometheus datasource configuration lacked proper connection settings and error handling.

**Fix**:
- Enhanced datasource configuration with additional JSON data fields:
  - `httpMethod`: "POST" for better query performance
  - `queryTimeout`: "60s" for handling long queries
  - `keepCookies`: [] for session management
- Added `version` and `readOnly` fields for proper Grafana integration

### 3. **Connection Testing and Validation**
**Problem**: No mechanism to verify that Grafana could actually connect to Prometheus after deployment.

**Fix**:
- Added `_test_datasource_connection()` method in `GrafanaClient`
- Implements proper authentication and health check for datasource
- Waits for Grafana to be ready before testing connection
- Provides detailed logging for connection status

### 4. **Improved Error Handling and Logging**
**Problem**: Limited error reporting made it difficult to diagnose connection issues.

**Fix**:
- Added comprehensive logging throughout the connection process
- Proper exception handling with specific error messages
- Debug-level logging for retry attempts
- Warning messages for non-critical failures

## Key Changes Made

### `grafana_client.py`
- Added `_wait_for_prometheus()` method with retry logic
- Added `_test_datasource_connection()` method for validation
- Enhanced datasource configuration with additional fields
- Improved error handling and logging

### `prometheus_client.py`
- Enhanced `wait_for_ready()` method to check both health and ready endpoints
- Added proper timeout handling with debug logging
- Improved health check with timeout parameter

### `manager.py`
- Modified deployment flow to wait for Prometheus readiness
- Added datasource connection testing after Grafana deployment
- Enhanced error handling for deployment failures

## Usage

The fixes are automatically applied when using the monitoring system:

```python
from ubenchai.monitors.manager import MonitorManager

# Initialize manager
manager = MonitorManager(
    recipe_directory="recipes",
    output_root="logs"
)

# Start monitoring with Prometheus and Grafana
instance = manager.start_monitor(
    recipe_name="monitor-full-stack",
    targets=["localhost"],
    mode="local"
)

# The system will now:
# 1. Deploy Prometheus and wait for it to be ready
# 2. Deploy Grafana with proper datasource configuration
# 3. Test the connection between Grafana and Prometheus
# 4. Create dashboards if connection is successful
```

## Testing

Use the provided test script to validate the connection:

```bash
python test_connection_fix.py
```

This will:
- Create a temporary monitoring setup
- Deploy both Prometheus and Grafana
- Test health endpoints
- Validate datasource connection
- Clean up resources

## Configuration Example

Example recipe with proper Grafana configuration:

```yaml
name: monitor-full-stack
description: Full-stack monitoring with Prometheus and Grafana

exporters:
  - type: prometheus
    port: 9090
    scrape_configs:
      - job_name: node
        static_configs:
          - targets: ["localhost:9100"]

grafana:
  enabled: true
  port: 3000
  admin_user: admin
  admin_password: secure_password
  dashboards:
    - type: system
      title: "System Overview"
```

## Benefits

1. **Reliable Connections**: Proper timing ensures Grafana can connect to Prometheus
2. **Better Error Reporting**: Detailed logging helps diagnose issues quickly
3. **Robust Configuration**: Enhanced datasource settings improve query performance
4. **Automatic Validation**: Connection testing catches issues early
5. **Improved Stability**: Retry logic handles temporary network issues

## Troubleshooting

If connection issues persist:

1. Check Prometheus logs: `logs/prometheus/{instance_id}/prometheus.log`
2. Check Grafana logs: `logs/grafana/{instance_id}/grafana.log`
3. Verify network connectivity between services
4. Ensure proper firewall/security group settings
5. Check for port conflicts

The enhanced logging will provide detailed information about where the connection process fails.
