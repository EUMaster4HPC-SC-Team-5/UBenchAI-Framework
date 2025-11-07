#!/usr/bin/env python3
"""
Register monitoring targets with Prometheus.
Updates the JSON target files that Prometheus uses for service discovery.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List


def load_targets(file_path: Path) -> List[dict]:
    """Load existing targets from JSON file."""
    if not file_path.exists():
        return []

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            # Handle both array format and Prometheus file_sd format
            if isinstance(data, list):
                if len(data) > 0 and "targets" in data[0]:
                    return data
                else:
                    # Convert simple list to Prometheus format
                    return [{"targets": data, "labels": {}}] if data else []
            return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load {file_path}: {e}", file=sys.stderr)
        return []


def save_targets(file_path: Path, targets: List[dict]) -> None:
    """Save targets to JSON file in Prometheus file_sd format."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(targets, f, indent=2)

    print(f"✓ Saved {len(targets)} target group(s) to {file_path}")


def add_target(file_path: Path, target: str, labels: dict = None) -> None:
    """Add a new target to the targets file."""
    targets = load_targets(file_path)

    # Check if target already exists
    for group in targets:
        if target in group.get("targets", []):
            print(f"Target {target} already exists in {file_path}")
            return

    # Add to first group or create new group
    if targets:
        targets[0]["targets"].append(target)
        if labels:
            targets[0]["labels"].update(labels)
    else:
        targets = [{"targets": [target], "labels": labels or {}}]

    save_targets(file_path, targets)
    print(f"✓ Added target: {target}")


def remove_target(file_path: Path, target: str) -> None:
    """Remove a target from the targets file."""
    targets = load_targets(file_path)

    found = False
    for group in targets:
        if target in group.get("targets", []):
            group["targets"].remove(target)
            found = True

    # Remove empty groups
    targets = [g for g in targets if g.get("targets")]

    if found:
        save_targets(file_path, targets)
        print(f"✓ Removed target: {target}")
    else:
        print(f"Target {target} not found in {file_path}")


def list_targets(file_path: Path) -> None:
    """List all targets in the file."""
    targets = load_targets(file_path)

    if not targets:
        print(f"No targets in {file_path}")
        return

    print(f"Targets in {file_path}:")
    for i, group in enumerate(targets):
        print(f"\n  Group {i + 1}:")
        for target in group.get("targets", []):
            print(f"    - {target}")
        if group.get("labels"):
            print(f"    Labels: {group['labels']}")


def main():
    parser = argparse.ArgumentParser(
        description="Register monitoring targets with Prometheus"
    )
    parser.add_argument(
        "action", choices=["add", "remove", "list"], help="Action to perform"
    )
    parser.add_argument(
        "job_type",
        choices=["node", "cadvisor", "gpu", "ollama", "qdrant"],
        help="Type of monitoring job",
    )
    parser.add_argument(
        "--target", help="Target in format 'host:port' (required for add/remove)"
    )
    parser.add_argument(
        "--label",
        action="append",
        help="Label in format 'key=value' (can be specified multiple times)",
    )
    parser.add_argument(
        "--targets-dir",
        default="logs/prometheus_assets",
        help="Directory containing target files (default: logs/prometheus_assets)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.action in ["add", "remove"] and not args.target:
        parser.error(f"--target is required for action '{args.action}'")

    # Parse labels
    labels = {}
    if args.label:
        for label in args.label:
            if "=" not in label:
                parser.error(f"Invalid label format: {label}. Use 'key=value'")
            key, value = label.split("=", 1)
            labels[key] = value

    # Determine target file
    targets_dir = Path(args.targets_dir)
    file_path = targets_dir / f"{args.job_type}_targets.json"

    # Perform action
    if args.action == "add":
        add_target(file_path, args.target, labels)
    elif args.action == "remove":
        remove_target(file_path, args.target)
    elif args.action == "list":
        list_targets(file_path)


if __name__ == "__main__":
    main()
