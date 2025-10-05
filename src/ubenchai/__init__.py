"""
UBenchAI Framework - Unified Benchmarking Framework for AI Factory Workloads
"""

__version__ = "0.1.0"
__author__ = "Team 5 - EUMaster4HPC"

from loguru import logger

# Configure default logger
logger.add(
    "logs/ubenchai_{time}.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
)

__all__ = ["__version__", "__author__", "logger"]
