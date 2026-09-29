#!/usr/bin/env python3
"""Append Jenkins build timings and result to workspace CSV/log files."""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent
METRICS_FILE = WORKSPACE / "metrics.csv"
RESULTS_LOG = WORKSPACE / "pipeline-results.log"
METRIC_FIELDS = ("build_time", "test_time", "deploy_time", "success")


def non_negative_seconds(value: str) -> int:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("time must be a number of seconds") from error
    if seconds < 0:
        raise argparse.ArgumentTypeError("time cannot be negative")
    return round(seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-time", required=True, type=non_negative_seconds)
    parser.add_argument("--test-time", required=True, type=non_negative_seconds)
    parser.add_argument("--deploy-time", required=True, type=non_negative_seconds)
    parser.add_argument("--success", required=True, choices=("0", "1"))
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--result", required=True, choices=("SUCCESS", "FAILURE", "UNSTABLE", "ABORTED"))
    parser.add_argument("--metrics-file", type=Path, default=METRICS_FILE)
    parser.add_argument("--log-file", type=Path, default=RESULTS_LOG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics_path = args.metrics_file
    log_path = args.log_file
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "build_time": args.build_time,
        "test_time": args.test_time,
        "deploy_time": args.deploy_time,
        "success": args.success,
    }
    needs_header = not metrics_path.exists() or metrics_path.stat().st_size == 0
    with metrics_path.open("a", newline="", encoding="utf-8") as metrics_file:
        writer = csv.DictWriter(metrics_file, fieldnames=METRIC_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result_line = (
        f"{timestamp} build={args.build_number} result={args.result} "
        f"build_time={args.build_time}s test_time={args.test_time}s "
        f"deploy_time={args.deploy_time}s success={args.success}"
    )
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(result_line + "\n")
    print(result_line)
    print(f"Metrics appended to {metrics_path}")


if __name__ == "__main__":
    main()