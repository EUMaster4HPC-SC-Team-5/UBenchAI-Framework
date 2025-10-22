"""
Health Checker - Comprehensive system health monitoring
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None


class HealthStatus(Enum):
    """Health status enumeration"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthCheck:
    """Individual health check result"""

    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: str,
        value: Optional[Any] = None,
        threshold: Optional[float] = None,
    ):
        self.name = name
        self.status = status
        self.message = message
        self.value = value
        self.threshold = threshold
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Comprehensive system health checker"""

    def __init__(self, output_dir: str = "logs/health", check_interval: int = 30):
        """
        Initialize health checker

        Args:
            output_dir: Directory to store health check results
            check_interval: Interval between checks in seconds
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.check_interval = check_interval
        self.last_check = None

        # Health thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "load_average": 2.0,
            "process_count": 1000,
            "network_errors": 10,
        }

        logger.info(f"Health checker initialized with output dir: {output_dir}")

    def check_system_health(self) -> Dict[str, HealthCheck]:
        """Perform comprehensive system health check"""
        logger.debug("Performing system health check")

        checks = {}

        # CPU health
        checks["cpu"] = self._check_cpu_health()

        # Memory health
        checks["memory"] = self._check_memory_health()

        # Disk health
        checks["disk"] = self._check_disk_health()

        # Process health
        checks["processes"] = self._check_process_health()

        # Network health
        checks["network"] = self._check_network_health()

        # System load
        checks["load"] = self._check_load_health()

        # Overall system status
        checks["overall"] = self._calculate_overall_health(checks)

        self.last_check = datetime.utcnow()
        self._save_health_results(checks)

        return checks

    def _check_cpu_health(self) -> HealthCheck:
        """Check CPU health"""
        if not psutil:
            return HealthCheck(
                "cpu", HealthStatus.UNKNOWN, "psutil not available for CPU monitoring"
            )

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else None

            if cpu_percent > self.thresholds["cpu_percent"]:
                status = HealthStatus.CRITICAL
                message = f"High CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent > self.thresholds["cpu_percent"] * 0.8:
                status = HealthStatus.WARNING
                message = f"Elevated CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            return HealthCheck(
                "cpu",
                status,
                message,
                value=cpu_percent,
                threshold=self.thresholds["cpu_percent"],
            )

        except Exception as e:
            return HealthCheck("cpu", HealthStatus.UNKNOWN, f"CPU check failed: {e}")

    def _check_memory_health(self) -> HealthCheck:
        """Check memory health"""
        if not psutil:
            return HealthCheck(
                "memory",
                HealthStatus.UNKNOWN,
                "psutil not available for memory monitoring",
            )

        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)

            if memory_percent > self.thresholds["memory_percent"]:
                status = HealthStatus.CRITICAL
                message = f"High memory usage: {memory_percent:.1f}%"
            elif memory_percent > self.thresholds["memory_percent"] * 0.8:
                status = HealthStatus.WARNING
                message = f"Elevated memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}% ({memory_available_gb:.1f}GB available)"

            return HealthCheck(
                "memory",
                status,
                message,
                value=memory_percent,
                threshold=self.thresholds["memory_percent"],
            )

        except Exception as e:
            return HealthCheck(
                "memory", HealthStatus.UNKNOWN, f"Memory check failed: {e}"
            )

    def _check_disk_health(self) -> HealthCheck:
        """Check disk health"""
        if not psutil:
            return HealthCheck(
                "disk", HealthStatus.UNKNOWN, "psutil not available for disk monitoring"
            )

        try:
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)

            if disk_percent > self.thresholds["disk_percent"]:
                status = HealthStatus.CRITICAL
                message = f"High disk usage: {disk_percent:.1f}%"
            elif disk_percent > self.thresholds["disk_percent"] * 0.8:
                status = HealthStatus.WARNING
                message = f"Elevated disk usage: {disk_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {disk_percent:.1f}% ({disk_free_gb:.1f}GB free)"

            return HealthCheck(
                "disk",
                status,
                message,
                value=disk_percent,
                threshold=self.thresholds["disk_percent"],
            )

        except Exception as e:
            return HealthCheck("disk", HealthStatus.UNKNOWN, f"Disk check failed: {e}")

    def _check_process_health(self) -> HealthCheck:
        """Check process health"""
        if not psutil:
            return HealthCheck(
                "processes",
                HealthStatus.UNKNOWN,
                "psutil not available for process monitoring",
            )

        try:
            process_count = len(psutil.pids())

            if process_count > self.thresholds["process_count"]:
                status = HealthStatus.WARNING
                message = f"High process count: {process_count}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Process count normal: {process_count}"

            return HealthCheck(
                "processes",
                status,
                message,
                value=process_count,
                threshold=self.thresholds["process_count"],
            )

        except Exception as e:
            return HealthCheck(
                "processes", HealthStatus.UNKNOWN, f"Process check failed: {e}"
            )

    def _check_network_health(self) -> HealthCheck:
        """Check network health"""
        if not psutil:
            return HealthCheck(
                "network",
                HealthStatus.UNKNOWN,
                "psutil not available for network monitoring",
            )

        try:
            net_io = psutil.net_io_counters()
            error_count = net_io.errin + net_io.errout + net_io.dropin + net_io.dropout

            if error_count > self.thresholds["network_errors"]:
                status = HealthStatus.WARNING
                message = f"Network errors detected: {error_count}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Network health normal: {error_count} errors"

            return HealthCheck(
                "network",
                status,
                message,
                value=error_count,
                threshold=self.thresholds["network_errors"],
            )

        except Exception as e:
            return HealthCheck(
                "network", HealthStatus.UNKNOWN, f"Network check failed: {e}"
            )

    def _check_load_health(self) -> HealthCheck:
        """Check system load"""
        if not psutil:
            return HealthCheck(
                "load", HealthStatus.UNKNOWN, "psutil not available for load monitoring"
            )

        try:
            if hasattr(psutil, "getloadavg"):
                load_avg = psutil.getloadavg()[0]
                cpu_count = psutil.cpu_count()
                load_percent = (load_avg / cpu_count) * 100

                if load_avg > self.thresholds["load_average"]:
                    status = HealthStatus.WARNING
                    message = f"High system load: {load_avg:.2f}"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"System load normal: {load_avg:.2f}"

                return HealthCheck(
                    "load",
                    status,
                    message,
                    value=load_avg,
                    threshold=self.thresholds["load_average"],
                )
            else:
                return HealthCheck(
                    "load",
                    HealthStatus.UNKNOWN,
                    "Load average not available on this system",
                )

        except Exception as e:
            return HealthCheck("load", HealthStatus.UNKNOWN, f"Load check failed: {e}")

    def _calculate_overall_health(self, checks: Dict[str, HealthCheck]) -> HealthCheck:
        """Calculate overall system health"""
        statuses = [
            check.status for check in checks.values() if check.name != "overall"
        ]

        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
            message = "System has critical issues"
        elif HealthStatus.WARNING in statuses:
            overall_status = HealthStatus.WARNING
            warning_count = sum(1 for s in statuses if s == HealthStatus.WARNING)
            message = f"System has {warning_count} warning(s)"
        elif HealthStatus.UNKNOWN in statuses:
            overall_status = HealthStatus.WARNING
            unknown_count = sum(1 for s in statuses if s == HealthStatus.UNKNOWN)
            message = f"System has {unknown_count} unknown status(es)"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All systems healthy"

        return HealthCheck("overall", overall_status, message)

    def _save_health_results(self, checks: Dict[str, HealthCheck]) -> None:
        """Save health check results to file"""
        timestamp = datetime.utcnow()
        filename = f"health_check_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename

        results = {
            "timestamp": timestamp.isoformat(),
            "overall_status": checks["overall"].status.value,
            "checks": {name: check.to_dict() for name, check in checks.items()},
        }

        with open(filepath, "w") as f:
            json.dump(results, f, indent=2)

        logger.debug(f"Health check results saved to: {filepath}")

    def get_health_summary(self) -> Dict:
        """Get current health summary"""
        if not self.last_check:
            return {"status": "no_checks", "message": "No health checks performed yet"}

        # Load latest health check
        health_files = list(self.output_dir.glob("health_check_*.json"))
        if not health_files:
            return {"status": "no_data", "message": "No health check data available"}

        latest_file = max(health_files, key=lambda f: f.stat().st_mtime)

        try:
            with open(latest_file, "r") as f:
                data = json.load(f)

            return {
                "status": data["overall_status"],
                "timestamp": data["timestamp"],
                "checks": data["checks"],
            }
        except Exception as e:
            return {"status": "error", "message": f"Error loading health data: {e}"}

    def set_threshold(self, metric: str, value: float) -> None:
        """Set health check threshold"""
        if metric in self.thresholds:
            self.thresholds[metric] = value
            logger.info(f"Updated threshold for {metric}: {value}")
        else:
            logger.warning(f"Unknown metric: {metric}")

    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds"""
        return self.thresholds.copy()
