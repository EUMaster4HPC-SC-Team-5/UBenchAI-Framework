"""
Metrics Analyzer - Data analysis and comparison tools for benchmark results
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from loguru import logger


@dataclass
class MetricSummary:
    """Summary statistics for a metric"""

    name: str
    count: int
    mean: float
    median: float
    min_value: float
    max_value: float
    std_dev: float
    percentiles: Dict[int, float]


@dataclass
class ComparisonResult:
    """Result of comparing two metric sets"""

    metric_name: str
    baseline_value: float
    comparison_value: float
    difference: float
    percent_change: float
    significance: str  # "significant", "minor", "negligible"


class MetricsAnalyzer:
    """Analyze and compare benchmark metrics"""

    def __init__(self, output_dir: str = "logs/analysis"):
        """
        Initialize metrics analyzer

        Args:
            output_dir: Directory to store analysis results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Metrics analyzer initialized with output dir: {output_dir}")

    def analyze_metrics_file(self, file_path: str) -> Dict[str, MetricSummary]:
        """
        Analyze metrics from a JSON file

        Args:
            file_path: Path to metrics JSON file

        Returns:
            Dictionary of metric summaries
        """
        logger.info(f"Analyzing metrics file: {file_path}")

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            return self._analyze_metrics_data(data)

        except Exception as e:
            logger.error(f"Error analyzing metrics file {file_path}: {e}")
            return {}

    def _analyze_metrics_data(self, data: Dict) -> Dict[str, MetricSummary]:
        """Analyze metrics data and return summaries"""
        summaries = {}

        # Extract numeric metrics
        numeric_metrics = self._extract_numeric_metrics(data)

        for metric_name, values in numeric_metrics.items():
            if len(values) > 0:
                summaries[metric_name] = self._calculate_summary(metric_name, values)

        return summaries

    def _extract_numeric_metrics(
        self, data: Dict, prefix: str = ""
    ) -> Dict[str, List[float]]:
        """Recursively extract numeric metrics from nested data"""
        metrics = {}

        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, (int, float)):
                if current_key not in metrics:
                    metrics[current_key] = []
                metrics[current_key].append(float(value))
            elif isinstance(value, dict):
                # Recursively extract from nested dictionaries
                nested_metrics = self._extract_numeric_metrics(value, current_key)
                metrics.update(nested_metrics)
            elif (
                isinstance(value, list) and value and isinstance(value[0], (int, float))
            ):
                # Handle lists of numbers
                if current_key not in metrics:
                    metrics[current_key] = []
                metrics[current_key].extend([float(v) for v in value])

        return metrics

    def _calculate_summary(self, name: str, values: List[float]) -> MetricSummary:
        """Calculate summary statistics for a list of values"""
        if not values:
            return MetricSummary(name, 0, 0, 0, 0, 0, 0, {})

        # Basic statistics
        count = len(values)
        mean = statistics.mean(values)
        median = statistics.median(values)
        min_value = min(values)
        max_value = max(values)

        # Standard deviation
        if count > 1:
            std_dev = statistics.stdev(values)
        else:
            std_dev = 0.0

        # Percentiles
        percentiles = {}
        for p in [25, 50, 75, 90, 95, 99]:
            try:
                percentiles[p] = self._percentile(values, p)
            except:
                percentiles[p] = 0.0

        return MetricSummary(
            name=name,
            count=count,
            mean=mean,
            median=median,
            min_value=min_value,
            max_value=max_value,
            std_dev=std_dev,
            percentiles=percentiles,
        )

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def compare_metrics(
        self, baseline_file: str, comparison_file: str, threshold_percent: float = 5.0
    ) -> List[ComparisonResult]:
        """
        Compare metrics between two files

        Args:
            baseline_file: Path to baseline metrics file
            comparison_file: Path to comparison metrics file
            threshold_percent: Threshold for significant changes

        Returns:
            List of comparison results
        """
        logger.info(f"Comparing metrics: {baseline_file} vs {comparison_file}")

        # Analyze both files
        baseline_summaries = self.analyze_metrics_file(baseline_file)
        comparison_summaries = self.analyze_metrics_file(comparison_file)

        results = []

        # Compare common metrics
        common_metrics = set(baseline_summaries.keys()) & set(
            comparison_summaries.keys()
        )

        for metric_name in common_metrics:
            baseline = baseline_summaries[metric_name]
            comparison = comparison_summaries[metric_name]

            # Compare mean values
            baseline_value = baseline.mean
            comparison_value = comparison.mean

            if baseline_value == 0:
                # Avoid division by zero
                percent_change = 0.0 if comparison_value == 0 else float("inf")
            else:
                percent_change = (
                    (comparison_value - baseline_value) / baseline_value
                ) * 100

            difference = comparison_value - baseline_value

            # Determine significance
            if abs(percent_change) > threshold_percent:
                significance = "significant"
            elif abs(percent_change) > threshold_percent * 0.5:
                significance = "minor"
            else:
                significance = "negligible"

            results.append(
                ComparisonResult(
                    metric_name=metric_name,
                    baseline_value=baseline_value,
                    comparison_value=comparison_value,
                    difference=difference,
                    percent_change=percent_change,
                    significance=significance,
                )
            )

        return results

    def generate_comparison_report(
        self,
        baseline_file: str,
        comparison_file: str,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Generate a detailed comparison report

        Args:
            baseline_file: Path to baseline metrics file
            comparison_file: Path to comparison metrics file
            output_file: Optional output file path

        Returns:
            Path to generated report file
        """
        logger.info(
            f"Generating comparison report: {baseline_file} vs {comparison_file}"
        )

        # Perform comparison
        comparison_results = self.compare_metrics(baseline_file, comparison_file)

        # Generate report
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if not output_file:
            output_file = self.output_dir / f"comparison_report_{timestamp}.json"

        report_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "baseline_file": baseline_file,
            "comparison_file": comparison_file,
            "summary": {
                "total_metrics": len(comparison_results),
                "significant_changes": len(
                    [r for r in comparison_results if r.significance == "significant"]
                ),
                "minor_changes": len(
                    [r for r in comparison_results if r.significance == "minor"]
                ),
                "negligible_changes": len(
                    [r for r in comparison_results if r.significance == "negligible"]
                ),
            },
            "comparisons": [
                {
                    "metric_name": r.metric_name,
                    "baseline_value": r.baseline_value,
                    "comparison_value": r.comparison_value,
                    "difference": r.difference,
                    "percent_change": r.percent_change,
                    "significance": r.significance,
                }
                for r in comparison_results
            ],
        }

        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Comparison report saved to: {output_file}")
        return str(output_file)

    def analyze_trends(self, metrics_files: List[str]) -> Dict[str, Any]:
        """
        Analyze trends across multiple metrics files

        Args:
            metrics_files: List of paths to metrics files

        Returns:
            Trend analysis results
        """
        logger.info(f"Analyzing trends across {len(metrics_files)} files")

        all_summaries = []

        for file_path in metrics_files:
            summaries = self.analyze_metrics_file(file_path)
            all_summaries.append(
                {
                    "file": file_path,
                    "timestamp": self._extract_timestamp(file_path),
                    "summaries": summaries,
                }
            )

        # Sort by timestamp
        all_summaries.sort(key=lambda x: x["timestamp"])

        # Analyze trends for each metric
        trends = {}

        for summary_data in all_summaries:
            for metric_name, summary in summary_data["summaries"].items():
                if metric_name not in trends:
                    trends[metric_name] = {"values": [], "timestamps": [], "files": []}

                trends[metric_name]["values"].append(summary.mean)
                trends[metric_name]["timestamps"].append(summary_data["timestamp"])
                trends[metric_name]["files"].append(summary_data["file"])

        # Calculate trend statistics
        trend_analysis = {}
        for metric_name, trend_data in trends.items():
            if len(trend_data["values"]) > 1:
                values = trend_data["values"]
                trend_analysis[metric_name] = {
                    "trend": self._calculate_trend(values),
                    "volatility": statistics.stdev(values) if len(values) > 1 else 0,
                    "min_value": min(values),
                    "max_value": max(values),
                    "data_points": len(values),
                }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "files_analyzed": len(metrics_files),
            "trends": trend_analysis,
        }

    def _extract_timestamp(self, file_path: str) -> datetime:
        """Extract timestamp from file path or use file modification time"""
        try:
            # Try to extract from filename
            filename = Path(file_path).name
            if "metrics" in filename and "_" in filename:
                # Look for timestamp pattern
                parts = filename.split("_")
                for part in parts:
                    if len(part) >= 8 and part.isdigit():
                        # Assume YYYYMMDD format
                        return datetime.strptime(part[:8], "%Y%m%d")
        except:
            pass

        # Fall back to file modification time
        try:
            return datetime.fromtimestamp(Path(file_path).stat().st_mtime)
        except:
            return datetime.utcnow()

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values"""
        if len(values) < 2:
            return "insufficient_data"

        # Simple linear trend calculation
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)

        if second_avg > first_avg * 1.05:  # 5% increase
            return "increasing"
        elif second_avg < first_avg * 0.95:  # 5% decrease
            return "decreasing"
        else:
            return "stable"
