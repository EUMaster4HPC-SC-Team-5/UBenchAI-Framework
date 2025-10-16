"""
Reporting module for UBenchAI.

Provides loading of report recipes, aggregation of metrics, and rendering
of reports in multiple formats (HTML, JSON, PDF stub).
"""

from .manager import ReportManager
from .models import ReportFormat, ReportJobStatus
