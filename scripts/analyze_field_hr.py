#!/usr/bin/env python3
"""Summarize sustained HR evidence from FIT files or JSON activity exports.

Accepts FIT files (raw, gzip as in Strava bulk exports, or zip as in Garmin
exports), JSON record lists, and JSON stream arrays from the Strava MCP,
intervals.icu, or the Strava REST API.

This utility finds auditable candidate efforts. It does not declare LTHR or VT1.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import gzip
from io import BytesIO
import json
import math
from pathlib import Path
import zipfile
from statistics import fmean, median
from typing import Any, Iterable


TIME_KEYS = ("timestamp", "time", "dateTime", "startTime", "elapsed_time", "elapsedTime")
HR_KEYS = ("heart_rate", "heartRate", "heartrate", "hr", "HeartRate", "HR")
HR_SUMMARY_KEYS = ("averageHR", "averageHeartRate", "maxHR", "maxHeartRate", "average_heartrate", "max_heartrate")


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
    if isinstance(value, datetime):
        return value.timestamp()
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
    for key in keys:
        value = node.get(key)
        if isinstance(value, dict):  # Strava REST key_by_type: {"heartrate": {"data": [...]}}
            value = value.get("data")
        if isinstance(value, list):
            return value
    return None


def stream_columns(node: list[Any]) -> dict[str, list[Any]] | None:
    """Turn a [{"type": "heartrate", "data": [...]}, ...] list (intervals.icu, Strava REST) into columns."""
    if node and all(
        isinstance(item, dict) and isinstance(item.get("type"), str) and isinstance(item.get("data"), list)
        for item in node
    ):
        return {item["type"]: item["data"] for item in node}
    return None


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
            columns = stream_columns(node)
            if columns is not None:
                walk(columns)
                return
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


def unpack_container(data: bytes) -> bytes:
    """Return the payload inside gzip (Strava bulk export) or zip (Garmin export) wrappers."""
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".fit")]
            if len(members) != 1:
                raise ValueError(f"expected exactly one .fit file in the zip archive, found {len(members)}")
            return archive.read(members[0])
    return data


def is_fit(data: bytes) -> bool:
    return len(data) >= 12 and data[8:12] == b".FIT"


def fit_samples(data: bytes) -> tuple[list[tuple[Any, Any]], dict[str, Any]]:
    """Decode FIT records, keeping records inside cycling or unlabeled sessions."""
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as error:
        raise RuntimeError(
            "decoding FIT files requires garmin-fit-sdk: python -m pip install -r scripts/requirements.txt"
        ) from error
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    records = messages.get("record_mesgs", [])
    sessions = messages.get("session_mesgs", [])
    metadata: dict[str, Any] = {
        "input_format": "fit",
        "fit_sessions": [{"sport": s.get("sport"), "sub_sport": s.get("sub_sport")} for s in sessions],
    }
    if errors:
        # Partially recorded files are common; keep what decoded, but surface the integrity problem.
        metadata["fit_decode_warnings"] = [f"decoding stopped early; file may be truncated or corrupt: {error}" for error in errors]
    cycling = [s for s in sessions if s.get("sport") == "cycling"]
    # Several non-Garmin head units (e.g. Magene in navigation mode) label rides "generic".
    unknown = [s for s in sessions if s.get("sport") in (None, "generic")]
    kept = cycling or unknown
    if sessions and not kept:
        found = sorted({str(s["sport"]) for s in sessions})
        raise ValueError(f"FIT file has no cycling session (found: {', '.join(found)})")
    if not cycling:
        metadata["sport_warning"] = "FIT sport is generic or missing; confirm the activity was a ride"
    if kept:
        windows = []
        for session in kept:
            start = parse_time(session.get("start_time"))
            elapsed = numeric(session.get("total_elapsed_time"))
            if start is not None and elapsed is not None:
                windows.append((start, start + elapsed))
        if windows:
            # Multisport files also contain swim/run legs; their HR is not cycling evidence.
            def in_kept_session(record: dict[str, Any]) -> bool:
                moment = parse_time(record.get("timestamp"))
                return moment is not None and any(start <= moment <= end for start, end in windows)

            records = [record for record in records if in_kept_session(record)]
    return [(record.get("timestamp"), record.get("heart_rate")) for record in records], metadata


def load_samples(path: Path) -> tuple[list[tuple[Any, Any]], dict[str, Any]]:
    data = unpack_container(path.read_bytes())
    if is_fit(data):
        return fit_samples(data)
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("unsupported file format; expected FIT or JSON") from error
    return raw_samples(payload), {"input_format": "json"}


def extract_points(payload: Any) -> list[tuple[float, float]]:
    return normalize_points(raw_samples(payload))


def normalize_points(samples: Iterable[tuple[Any, Any]]) -> list[tuple[float, float]]:
    points = []
    for raw_time, raw_hr in samples:
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
    try:
        samples, metadata = load_samples(path)
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        return {"file": path.name, "error": str(error)}
    points = normalize_points(samples)
    if not points:
        return {"file": path.name, **metadata, "error": "no timestamped HR records or aligned time/HR streams found"}
    gaps = [b[0] - a[0] for a, b in zip(points, points[1:]) if b[0] > a[0]]
    runs = interpolate_seconds(points, max_gap=max_gap)
    values = [hr for _, hr in points]
    return {
        "file": path.name,
        **metadata,
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
    strava_stubs = 0
    for item in activities:
        sport = str(item.get("activityType") or item.get("sport") or item.get("sport_type") or item.get("type") or "unknown")
        sports[sport] = sports.get(sport, 0) + 1
        if item.get("has_heartrate") is True or any(numeric(item.get(key)) is not None for key in HR_SUMMARY_KEYS):
            with_hr += 1
        # device_watts separates measured power from Strava/intervals.icu estimates.
        if item.get("device_watts") is True or any(numeric(item.get(key)) is not None for key in ("averagePower", "normalizedPower", "maxPower")):
            with_power += 1
        if item.get("source") == "STRAVA":
            strava_stubs += 1
    result: dict[str, Any] = {
        "file": path.name,
        "activity_count": len(activities),
        "sports": sports,
        "activities_with_summary_hr": with_hr,
        "activities_with_summary_power": with_power,
        "caveat": "Completeness still depends on API pagination and duplicate filtering.",
    }
    if strava_stubs:
        result["strava_sourced_stubs"] = strava_stubs
        result["strava_stub_warning"] = (
            "intervals.icu returns empty stubs for activities it received from Strava; "
            "sync those rides to intervals.icu from the device platform or use the original files."
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--activity",
        "--fit-json",
        dest="activity_files",
        nargs="+",
        type=Path,
        required=True,
        help="FIT (.fit, .fit.gz, Garmin .zip) or JSON files with timestamped HR records or time/HR streams",
    )
    parser.add_argument(
        "--activity-list-json", type=Path, help="optional Garmin, Strava, or intervals.icu activity-list export"
    )
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
            for path in args.activity_files
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

