#!/usr/bin/env python3
"""Summarize sustained HR evidence from Garmin/FIT JSON exports or Strava MCP streams.

This utility finds auditable candidate efforts. It does not declare LTHR or VT1.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Any, Iterable


TIME_KEYS = ("timestamp", "time", "dateTime", "startTime", "elapsed_time", "elapsedTime")
HR_KEYS = ("heart_rate", "heartRate", "hr", "HeartRate", "HR")


def unwrap(value: Any) -> Any:
    """Unwrap common MCP result envelopes and JSON-in-text content."""
    if isinstance(value, dict):
        structured = value.get("structuredContent")
        if isinstance(structured, dict) and "result" in structured:
            return unwrap(structured["result"])
        if set(value) == {"result"}:
            return unwrap(value["result"])
        content = value.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    try:
                        return unwrap(json.loads(block["text"]))
                    except json.JSONDecodeError:
                        continue
    return value


def parse_time(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def numeric(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def find_record_lists(value: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            dicts = [item for item in node if isinstance(item, dict)]
            if len(dicts) >= 2:
                with_time_hr = 0
                for item in dicts[:50]:
                    if any(key in item for key in TIME_KEYS) and any(key in item for key in HR_KEYS):
                        with_time_hr += 1
                if with_time_hr >= min(2, len(dicts)):
                    found.append(dicts)
                    return
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(unwrap(value))
    return found


def first_list(node: dict[str, Any], keys: tuple[str, ...]) -> list[Any] | None:
    return next((node[key] for key in keys if isinstance(node.get(key), list)), None)


def find_parallel_streams(value: Any) -> list[tuple[list[Any], list[Any]]]:
    """Find column-oriented streams such as Strava MCP {"time": [...], "heart_rate": [...]}."""
    found: list[tuple[list[Any], list[Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            times = first_list(node, TIME_KEYS)
            hrs = first_list(node, HR_KEYS)
            # Unequal lengths mean the sample alignment is unknown, so never zip them.
            if times is not None and hrs is not None and len(times) == len(hrs) >= 2:
                found.append((times, hrs))
                return
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(unwrap(value))
    return found


def raw_samples(payload: Any) -> list[tuple[Any, Any]]:
    record_lists = find_record_lists(payload)
    if record_lists:
        return [
            (
                next((record.get(key) for key in TIME_KEYS if key in record), None),
                next((record.get(key) for key in HR_KEYS if key in record), None),
            )
            for record in max(record_lists, key=len)
        ]
    streams = find_parallel_streams(payload)
    if streams:
        times, hrs = max(streams, key=lambda pair: len(pair[0]))
        return list(zip(times, hrs))
    return []


def extract_points(payload: Any) -> list[tuple[float, float]]:
    points = []
    for raw_time, raw_hr in raw_samples(payload):
        timestamp = parse_time(raw_time)
        hr = numeric(raw_hr)
        if timestamp is not None and hr is not None and 25 <= hr <= 260:
            points.append((timestamp, hr))
    points.sort()
    deduplicated: dict[float, float] = {}
    for timestamp, hr in points:
        deduplicated[timestamp] = hr
    if not deduplicated:
        return []
    start = min(deduplicated)
    return [(timestamp - start, hr) for timestamp, hr in sorted(deduplicated.items())]


def interpolate_seconds(points: list[tuple[float, float]], max_gap: int) -> list[list[float]]:
    """Return contiguous one-Hz runs, never bridging gaps longer than max_gap."""
    if not points:
        return []
    runs: list[list[float]] = []
    current: list[float] = []
    for index, (time_a, hr_a) in enumerate(points[:-1]):
        time_b, hr_b = points[index + 1]
        gap = time_b - time_a
        if not current:
            current.append(hr_a)
        if gap <= 0:
            continue
        if gap > max_gap:
            if current:
                runs.append(current)
            current = [hr_b]
            continue
        whole_seconds = max(1, int(round(gap)))
        for step in range(1, whole_seconds + 1):
            fraction = min(1.0, step / gap)
            current.append(hr_a + fraction * (hr_b - hr_a))
    if len(points) == 1:
        current = [points[0][1]]
    if current:
        runs.append(current)
    return runs


def best_window(runs: Iterable[list[float]], seconds: int) -> dict[str, float] | None:
    best: tuple[float, float, float] | None = None
    for run_index, run in enumerate(runs):
        if len(run) < seconds:
            continue
        rolling = sum(run[:seconds])
        candidate = (rolling / seconds, float(run_index), 0.0)
        if best is None or candidate[0] > best[0]:
            best = candidate
        for start in range(1, len(run) - seconds + 1):
            rolling += run[start + seconds - 1] - run[start - 1]
            candidate = (rolling / seconds, float(run_index), float(start))
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        return None
    return {"mean_bpm": round(best[0], 2), "run_index": int(best[1]), "start_second": int(best[2])}


def summarize_file(path: Path, windows: list[int], max_gap: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    points = extract_points(payload)
    if not points:
        return {"file": path.name, "error": "no timestamped HR records or aligned time/HR streams found"}
    gaps = [b[0] - a[0] for a, b in zip(points, points[1:]) if b[0] > a[0]]
    runs = interpolate_seconds(points, max_gap=max_gap)
    values = [hr for _, hr in points]
    return {
        "file": path.name,
        "raw_hr_samples": len(points),
        "elapsed_seconds": round(points[-1][0], 1),
        "hr_min_bpm": round(min(values), 1),
        "hr_mean_observed_bpm": round(fmean(values), 2),
        "hr_max_bpm": round(max(values), 1),
        "median_sample_gap_seconds": round(median(gaps), 2) if gaps else None,
        "gaps_over_limit": sum(gap > max_gap for gap in gaps),
        "continuous_runs_seconds": sorted((len(run) for run in runs), reverse=True)[:10],
        "best_continuous_windows": {
            f"{minutes}min": best_window(runs, minutes * 60) for minutes in windows
        },
        "interpretation": "Candidate evidence only; inspect effort context, power/terrain, sensor quality, drift, and repeatability.",
    }


def inventory_activity_list(path: Path) -> dict[str, Any]:
    payload = unwrap(json.loads(path.read_text(encoding="utf-8")))
    if isinstance(payload, dict):
        for key in ("activities", "activityList", "items", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        return {"file": path.name, "error": "activity list was not found"}
    activities = [item for item in payload if isinstance(item, dict)]
    sports: dict[str, int] = {}
    with_hr = 0
    with_power = 0
    for item in activities:
        sport = str(item.get("activityType") or item.get("sport") or item.get("sport_type") or item.get("type") or "unknown")
        sports[sport] = sports.get(sport, 0) + 1
        if any(numeric(item.get(key)) is not None for key in ("averageHR", "averageHeartRate", "maxHR", "maxHeartRate")):
            with_hr += 1
        if any(numeric(item.get(key)) is not None for key in ("averagePower", "normalizedPower", "maxPower")):
            with_power += 1
    return {
        "file": path.name,
        "activity_count": len(activities),
        "sports": sports,
        "activities_with_summary_hr": with_hr,
        "activities_with_summary_power": with_power,
        "caveat": "Completeness still depends on API pagination and duplicate filtering.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fit-json",
        nargs="+",
        type=Path,
        required=True,
        help="JSON exports containing timestamped HR records or Strava MCP time/heart_rate streams",
    )
    parser.add_argument("--activity-list-json", type=Path, help="optional Garmin or Strava activity-list export")
    parser.add_argument("--windows-min", nargs="+", type=int, default=[20, 30, 40, 60])
    parser.add_argument("--max-interpolation-gap-seconds", type=int, default=12)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if any(window <= 0 for window in args.windows_min):
        parser.error("window lengths must be positive")
    result: dict[str, Any] = {
        "purpose": "field HR evidence inventory; not an automatic threshold diagnosis",
        "activities": [
            summarize_file(path, args.windows_min, args.max_interpolation_gap_seconds)
            for path in args.fit_json
        ],
    }
    if args.activity_list_json:
        result["activity_inventory"] = inventory_activity_list(args.activity_list_json)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()

