#!/usr/bin/env python3
"""
Aggregate results from multinode benchmark runs
"""

import json
import glob
import statistics
from pathlib import Path
from typing import List, Dict
from loguru import logger


def load_node_results(output_dir: str, run_prefix: str) -> List[Dict]:
    """
    Load results from all nodes

    Args:
        output_dir: Directory containing result files
        run_prefix: Prefix of result files (e.g., "recipe_name_runid")

    Returns:
        List of result dictionaries
    """
    pattern = f"{output_dir}/{run_prefix}_node_*.json"
    result_files = glob.glob(pattern)

    logger.info(f"Found {len(result_files)} result files matching pattern: {pattern}")

    results = []
    for file_path in sorted(result_files):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                results.append(data)
                logger.debug(f"Loaded results from: {file_path}")
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")

    return results


def aggregate_metrics(results: List[Dict]) -> Dict:
    """
    Aggregate metrics from all nodes

    Args:
        results: List of result dictionaries

    Returns:
        Aggregated metrics dictionary
    """
    if not results:
        return {}

    # Extract metrics from all nodes
    all_metrics = [r.get("metrics", {}) for r in results]

    # Calculate aggregate metrics
    total_requests = sum(m.get("total_requests", 0) for m in all_metrics)
    successful_requests = sum(m.get("successful_requests", 0) for m in all_metrics)
    failed_requests = sum(m.get("failed_requests", 0) for m in all_metrics)

    # Collect all latencies
    all_latencies = []
    for result in results:
        # If latencies are stored separately
        latencies = result.get("latencies", [])
        all_latencies.extend(latencies)

    # Calculate aggregate latency statistics
    latency_stats = {}
    if all_latencies:
        sorted_latencies = sorted(all_latencies)
        latency_stats = {
            "latency_min": min(all_latencies),
            "latency_max": max(all_latencies),
            "latency_mean": statistics.mean(all_latencies),
            "latency_median": statistics.median(all_latencies),
            "latency_p50": sorted_latencies[int(len(sorted_latencies) * 0.50)],
            "latency_p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
            "latency_p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
        }
    else:
        # Aggregate from node-level statistics if raw latencies not available
        latency_mins = [m.get("latency_min", 0) for m in all_metrics if "latency_min" in m]
        latency_maxs = [m.get("latency_max", 0) for m in all_metrics if "latency_max" in m]
        latency_means = [m.get("latency_mean", 0) for m in all_metrics if "latency_mean" in m]

        if latency_means:
            latency_stats = {
                "latency_min": min(latency_mins) if latency_mins else 0,
                "latency_max": max(latency_maxs) if latency_maxs else 0,
                "latency_mean": statistics.mean(latency_means),
            }

    # Calculate total duration (max across all nodes)
    durations = [m.get("duration_seconds", 0) for m in all_metrics]
    total_duration = max(durations) if durations else 0

    # Aggregate metrics
    aggregated = {
        "num_nodes": len(results),
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
        "duration_seconds": total_duration,
        "aggregate_throughput_rps": (
            successful_requests / total_duration if total_duration > 0 else 0
        ),
    }

    # Add latency statistics
    aggregated.update(latency_stats)

    # Per-node breakdown
    node_breakdown = []
    for i, metrics in enumerate(all_metrics):
        node_breakdown.append(
            {
                "node_id": metrics.get("node_id", i),
                "hostname": metrics.get("hostname", "unknown"),
                "total_requests": metrics.get("total_requests", 0),
                "successful_requests": metrics.get("successful_requests", 0),
                "throughput_rps": metrics.get("throughput_rps", 0),
            }
        )

    aggregated["node_breakdown"] = node_breakdown

    return aggregated


def save_aggregated_results(
    aggregated: Dict, output_dir: str, run_prefix: str
) -> str:
    """
    Save aggregated results to file

    Args:
        aggregated: Aggregated metrics dictionary
        output_dir: Output directory
        run_prefix: Run prefix

    Returns:
        Path to saved file
    """
    output_file = f"{output_dir}/{run_prefix}_aggregated.json"

    with open(output_file, "w") as f:
        json.dump(aggregated, f, indent=2)

    logger.info(f"Aggregated results saved to: {output_file}")
    return output_file


def print_summary(aggregated: Dict):
    """Print summary of aggregated results"""
    print("\n" + "=" * 70)
    print("AGGREGATED MULTINODE BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Number of Nodes:         {aggregated.get('num_nodes', 0)}")
    print(f"Total Requests:          {aggregated.get('total_requests', 0)}")
    print(f"Successful:              {aggregated.get('successful_requests', 0)}")
    print(f"Failed:                  {aggregated.get('failed_requests', 0)}")
    print(f"Success Rate:            {aggregated.get('success_rate', 0):.2%}")
    print(f"Duration:                {aggregated.get('duration_seconds', 0):.2f}s")
    print(
        f"Aggregate Throughput:    {aggregated.get('aggregate_throughput_rps', 0):.2f} req/s"
    )

    if "latency_mean" in aggregated:
        print(f"\nLatency Statistics (seconds):")
        print(f"  Min:     {aggregated.get('latency_min', 0):.3f}")
        print(f"  Mean:    {aggregated.get('latency_mean', 0):.3f}")
        print(f"  Median:  {aggregated.get('latency_median', 0):.3f}")
        print(f"  P95:     {aggregated.get('latency_p95', 0):.3f}")
        print(f"  P99:     {aggregated.get('latency_p99', 0):.3f}")
        print(f"  Max:     {aggregated.get('latency_max', 0):.3f}")

    if "node_breakdown" in aggregated:
        print(f"\nPer-Node Breakdown:")
        print(f"{'Node ID':<10} {'Hostname':<20} {'Requests':<12} {'Throughput (req/s)':<20}")
        print("-" * 70)
        for node in aggregated["node_breakdown"]:
            print(
                f"{node['node_id']:<10} {node['hostname']:<20} "
                f"{node['total_requests']:<12} {node['throughput_rps']:<20.2f}"
            )

    print("=" * 70)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Aggregate results from multinode benchmark runs"
    )
    parser.add_argument("output_dir", help="Directory containing result files")
    parser.add_argument("run_prefix", help="Prefix of result files")
    parser.add_argument(
        "--output",
        help="Custom output file path (default: <output_dir>/<run_prefix>_aggregated.json)",
    )

    args = parser.parse_args()

    # Load results from all nodes
    logger.info(f"Loading results from: {args.output_dir}")
    results = load_node_results(args.output_dir, args.run_prefix)

    if not results:
        logger.error("No result files found!")
        return 1

    # Aggregate metrics
    logger.info(f"Aggregating metrics from {len(results)} nodes")
    aggregated = aggregate_metrics(results)

    # Save aggregated results
    if args.output:
        output_file = args.output
        with open(output_file, "w") as f:
            json.dump(aggregated, f, indent=2)
        logger.info(f"Aggregated results saved to: {output_file}")
    else:
        output_file = save_aggregated_results(
            aggregated, args.output_dir, args.run_prefix
        )

    # Print summary
    print_summary(aggregated)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())