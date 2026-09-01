#!/usr/bin/env python3
"""Create an auditable first-pass QC and threshold-candidate report from CPET XLSX files.

Candidates require physiological adjudication; this script does not diagnose thresholds.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


ALIASES = {
    "time": ("time", "tempo", "t", "elapsedtime", "elapsed"),
    "hr": ("hr", "heartrate", "fc", "heart_rate"),
    "vo2": ("vo2", "o2", "oxygenconsumption"),
    "vco2": ("vco2", "co2", "carbondioxideproduction"),
    "ve": ("ve", "ventilation", "minuteventilation"),
    "rer": ("rer", "rq", "respiratoryexchangeratio"),
    "ve_vo2": ("vevo2", "ve/vo2", "eqo2"),
    "ve_vco2": ("vevco2", "ve/vco2", "eqco2"),
    "peto2": ("peto2", "eto2", "pet_o2"),
    "petco2": ("petco2", "etco2", "pet_co2"),
    "power": ("power", "workrate", "watts", "watt", "load"),
    "cadence": ("cadence", "rpm", "speed"),
}


def normalized(text: Any) -> str:
    return re.sub(r"[^a-z0-9/]", "", str(text).strip().lower())


def excel_column_index(label: str) -> int:
    value = 0
    for character in label.strip().upper():
        if not "A" <= character <= "Z":
            raise ValueError(f"invalid Excel column: {label}")
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def read_sheet(
    path: Path,
    sheet: str,
    header_row: int,
    data_start_row: int,
    data_start_column: str,
) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=sheet, header=header_row - 1, engine="openpyxl")
    rows_to_drop = max(0, data_start_row - header_row - 1)
    if rows_to_drop:
        frame = frame.iloc[rows_to_drop:]
    return frame.iloc[:, excel_column_index(data_start_column) :].reset_index(drop=True)


def choose_columns(frame: pd.DataFrame) -> dict[str, str]:
    normalized_columns = {column: normalized(column) for column in frame.columns}
    selected: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        alias_set = {normalized(alias) for alias in aliases}
        exact = [column for column, norm in normalized_columns.items() if norm in alias_set]
        if exact:
            selected[canonical] = str(exact[0])
            continue
        partial = [
            column
            for column, norm in normalized_columns.items()
            if any(alias and (norm.startswith(alias) or alias in norm) for alias in alias_set)
        ]
        if partial:
            selected[canonical] = str(partial[0])
    return selected


def elapsed_seconds(value: Any) -> float:
    if pd.isna(value):
        return math.nan
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, time):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6
    if isinstance(value, datetime):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6
    if isinstance(value, (int, float, np.number)):
        number = float(value)
        # Excel stores time-of-day as a fraction of one day.
        return number * 86400 if 0 <= number < 1 else number
    text = str(value).strip()
    match = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", text)
    if match:
        hours = int(match.group(1) or 0)
        return hours * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    try:
        return float(text)
    except ValueError:
        return math.nan


def standardize(frame: pd.DataFrame, selected: dict[str, str]) -> pd.DataFrame:
    if "time" not in selected:
        raise ValueError("could not identify an elapsed-time column")
    data = pd.DataFrame({"time": frame[selected["time"]].map(elapsed_seconds)})
    for canonical, source in selected.items():
        if canonical != "time":
            data[canonical] = pd.to_numeric(frame[source], errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["time"])
    data = data.sort_values("time").groupby("time", as_index=False).mean(numeric_only=True)
    if data.empty:
        raise ValueError("no parseable data rows")
    data["time"] -= data["time"].iloc[0]
    if "rer" not in data and {"vo2", "vco2"}.issubset(data):
        data["rer"] = data["vco2"] / data["vo2"]
    if "ve_vo2" not in data and {"ve", "vo2"}.issubset(data):
        data["ve_vo2"] = data["ve"] / data["vo2"]
    if "ve_vco2" not in data and {"ve", "vco2"}.issubset(data):
        data["ve_vco2"] = data["ve"] / data["vco2"]
    return data


def regularize(data: pd.DataFrame, max_interpolation_gap: int = 10) -> pd.DataFrame:
    indexed = data.copy()
    indexed["second"] = indexed["time"].round().astype(int)
    indexed = indexed.groupby("second").mean(numeric_only=True)
    full = indexed.reindex(range(int(indexed.index.min()), int(indexed.index.max()) + 1))
    full = full.interpolate(method="linear", limit=max_interpolation_gap, limit_area="inside")
    full.index.name = "second"
    full["time"] = full.index.astype(float)
    return full


def qc_report(raw: pd.DataFrame, regular: pd.DataFrame, selected: dict[str, str]) -> dict[str, Any]:
    intervals = np.diff(raw["time"].to_numpy(dtype=float))
    report: dict[str, Any] = {
        "raw_rows": int(len(raw)),
        "duration_seconds": round(float(raw["time"].max()), 1),
        "identified_columns": selected,
        "available_canonical_fields": [column for column in regular.columns if column != "time"],
        "median_raw_interval_seconds": round(float(np.nanmedian(intervals)), 3) if len(intervals) else None,
        "nonpositive_intervals_after_grouping": int(np.sum(intervals <= 0)) if len(intervals) else 0,
        "missing_fraction_regular_grid": {
            column: round(float(regular[column].isna().mean()), 4)
            for column in regular.columns
            if column != "time"
        },
    }
    for field in ("hr", "vo2", "vco2", "ve", "rer", "peto2", "petco2", "power", "cadence"):
        if field in regular and regular[field].notna().any():
            report[f"{field}_range"] = [
                round(float(regular[field].min()), 3),
                round(float(regular[field].max()), 3),
            ]
    return report


def exercise_bounds(data: pd.DataFrame) -> tuple[int, int, str]:
    if "power" in data and data["power"].notna().sum() >= 30:
        active = data.index[data["power"].rolling(10, min_periods=3, center=True).median() > 5]
        if len(active) >= 30:
            return int(active.min()), int(active.max()), "power > 5 W"
    if "vo2" in data and data["vo2"].notna().sum() >= 60:
        series = data["vo2"].rolling(20, min_periods=5, center=True).median()
        baseline = float(series.iloc[: max(30, len(series) // 10)].median())
        high = float(series.quantile(0.9))
        active = data.index[series > baseline + 0.15 * (high - baseline)]
        if len(active) >= 30:
            return int(active.min()), int(active.max()), "VO2 rise above baseline"
    start = int(data.index.min() + 0.1 * (data.index.max() - data.index.min()))
    return start, int(data.index.max()), "fallback: exclude first 10%"


def two_line_breakpoint(
    x: pd.Series,
    y: pd.Series,
    start: int,
    end: int,
    min_side: int = 25,
) -> int | None:
    frame = pd.DataFrame({"x": x, "y": y}).loc[start:end].dropna()
    if len(frame) < 2 * min_side + 1:
        return None
    xs = frame["x"].to_numpy(dtype=float)
    ys = frame["y"].to_numpy(dtype=float)
    if np.ptp(xs) == 0:
        return None
    best: tuple[float, int] | None = None
    for split in range(min_side, len(frame) - min_side):
        try:
            left_fit = np.polyfit(xs[:split], ys[:split], 1)
            right_fit = np.polyfit(xs[split:], ys[split:], 1)
        except np.linalg.LinAlgError:
            continue
        left_error = ys[:split] - np.polyval(left_fit, xs[:split])
        right_error = ys[split:] - np.polyval(right_fit, xs[split:])
        sse = float(np.sum(left_error**2) + np.sum(right_error**2))
        if best is None or sse < best[0]:
            best = (sse, int(frame.index[split]))
    return best[1] if best else None


def extremum_time(series: pd.Series, start: int, end: int, mode: str) -> int | None:
    section = series.loc[start:end].dropna()
    if section.empty:
        return None
    return int(section.idxmin() if mode == "min" else section.idxmax())


def value_at(data: pd.DataFrame, field: str, second: int | None) -> float | None:
    if second is None or field not in data or second not in data.index or pd.isna(data.at[second, field]):
        return None
    return round(float(data.at[second, field]), 2)


def median_candidate(candidates: dict[str, int | None]) -> int | None:
    values = [value for value in candidates.values() if value is not None]
    return int(round(float(np.median(values)))) if values else None


def detect_thresholds(data: pd.DataFrame, smooth_seconds: int, start: int, end: int) -> dict[str, Any]:
    smooth = data.rolling(smooth_seconds, min_periods=max(5, smooth_seconds // 2), center=True).mean()
    duration = end - start
    vt_start, vt_end = start + int(0.15 * duration), start + int(0.75 * duration)
    rcp_start, rcp_end = start + int(0.50 * duration), start + int(0.95 * duration)

    vt_candidates: dict[str, int | None] = {}
    if {"vo2", "vco2"}.issubset(smooth):
        vt_candidates["v_slope"] = two_line_breakpoint(
            smooth["vo2"], smooth["vco2"], vt_start, vt_end
        )
    if "ve_vo2" in smooth:
        vt_candidates["ve_vo2_nadir"] = extremum_time(smooth["ve_vo2"], vt_start, vt_end, "min")
    if "peto2" in smooth:
        vt_candidates["peto2_nadir"] = extremum_time(smooth["peto2"], vt_start, vt_end, "min")

    rcp_candidates: dict[str, int | None] = {}
    if "ve_vco2" in smooth:
        rcp_candidates["ve_vco2_nadir"] = extremum_time(smooth["ve_vco2"], rcp_start, rcp_end, "min")
    if "petco2" in smooth:
        rcp_candidates["petco2_peak"] = extremum_time(smooth["petco2"], rcp_start, rcp_end, "max")
    if {"vco2", "ve"}.issubset(smooth):
        rcp_candidates["ve_vs_vco2_break"] = two_line_breakpoint(
            smooth["vco2"], smooth["ve"], rcp_start, rcp_end
        )

    vt_time = median_candidate(vt_candidates)
    rcp_time = median_candidate(rcp_candidates)
    return {
        "smoothing_seconds": smooth_seconds,
        "vt1_indicator_times_seconds": vt_candidates,
        "vt1_consensus_candidate_seconds": vt_time,
        "vt1_candidate_hr_bpm": value_at(smooth, "hr", vt_time),
        "rcp_indicator_times_seconds": rcp_candidates,
        "rcp_consensus_candidate_seconds": rcp_time,
        "rcp_candidate_hr_bpm": value_at(smooth, "hr", rcp_time),
        "warning": "Breakpoints/extrema are candidates; verify sustained directional changes and indicator convergence visually.",
    }


def align_hr(cart: pd.DataFrame, ergometer: pd.DataFrame, max_lag: int = 120) -> dict[str, Any] | None:
    if "hr" not in cart or "hr" not in ergometer:
        return None
    best: tuple[float, int, int, float, float] | None = None
    cart_hr = cart["hr"]
    ergo_hr = ergometer["hr"]
    for lag in range(-max_lag, max_lag + 1):
        # Compare cart HR at t with ergometer HR at t + lag.
        pairs = pd.concat([cart_hr.rename("cart"), ergo_hr.shift(-lag).rename("ergo")], axis=1).dropna()
        if len(pairs) < 30:
            continue
        correlation = float(pairs.corr().iloc[0, 1])
        if not np.isfinite(correlation):
            continue
        difference = pairs["ergo"] - pairs["cart"]
        candidate = (
            correlation,
            lag,
            len(pairs),
            float(difference.mean()),
            float(np.sqrt(np.mean(difference**2))),
        )
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return None
    return {
        "ergometer_time_minus_cart_time_seconds": best[1],
        "correlation": round(best[0], 4),
        "overlap_seconds": best[2],
        "ergometer_minus_cart_hr_bias_bpm": round(best[3], 2),
        "hr_rmse_bpm": round(best[4], 2),
        "interpretation": "Use the lag to map cart threshold time t to ergometer time t + lag; audit power independently.",
    }


def ergometer_values_at(
    ergometer: pd.DataFrame,
    cart_seconds: list[int],
    lag: int,
) -> list[dict[str, Any]]:
    output = []
    for second in cart_seconds:
        ergo_second = second + lag
        row: dict[str, Any] = {"cart_second": second, "ergometer_second": ergo_second}
        for field in ("hr", "power", "cadence"):
            row[field] = value_at(ergometer, field, ergo_second)
        output.append(row)
    return output


def classified_threshold_power_candidates(
    ergometer: pd.DataFrame,
    sensitivity: list[dict[str, Any]],
    lag: int,
) -> dict[str, Any]:
    """Keep VT1 and RCP power candidates separate across smoothing choices."""
    output: dict[str, Any] = {}
    for label, time_key in (
        ("vt1", "vt1_consensus_candidate_seconds"),
        ("rcp", "rcp_consensus_candidate_seconds"),
    ):
        candidates = []
        for analysis in sensitivity:
            cart_second = analysis.get(time_key)
            if cart_second is None:
                continue
            ergo_second = int(cart_second) + lag
            candidates.append(
                {
                    "smoothing_seconds": analysis.get("smoothing_seconds"),
                    "cart_second": int(cart_second),
                    "ergometer_second": ergo_second,
                    "power_w": value_at(ergometer, "power", ergo_second),
                    "hr_bpm": value_at(ergometer, "hr", ergo_second),
                    "cadence_rpm": value_at(ergometer, "cadence", ergo_second),
                }
            )
        powers = [row["power_w"] for row in candidates if row["power_w"] is not None]
        output[label] = {
            "candidates": candidates,
            "candidate_power_values_w": powers,
            "central_power_w": round(float(np.median(powers)), 1) if powers else None,
            "candidate_range_w": [round(min(powers), 1), round(max(powers), 1)] if powers else None,
            "warning": "Automatic candidates require physiological adjudication before use as pVT1/pRCP or an FTP proxy.",
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gas-xlsx", type=Path, required=True)
    parser.add_argument("--gas-sheet", default=0)
    parser.add_argument("--header-row", type=int, default=1, help="one-based header row")
    parser.add_argument("--data-start-row", type=int, default=4, help="one-based first data row")
    parser.add_argument("--data-start-column", default="J")
    parser.add_argument("--ergometer-xlsx", type=Path)
    parser.add_argument("--ergometer-sheet", default="Sheet1")
    parser.add_argument("--ergometer-header-row", type=int, default=13)
    parser.add_argument("--ergometer-data-start-row", type=int, default=15)
    parser.add_argument("--ergometer-data-start-column", default="B")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    gas_raw_frame = read_sheet(
        args.gas_xlsx,
        args.gas_sheet,
        args.header_row,
        args.data_start_row,
        args.data_start_column,
    )
    gas_columns = choose_columns(gas_raw_frame)
    gas_raw = standardize(gas_raw_frame, gas_columns)
    gas = regularize(gas_raw)
    start, end, bound_method = exercise_bounds(gas)
    sensitivity = [detect_thresholds(gas, seconds, start, end) for seconds in (15, 20, 30, 40)]

    result: dict[str, Any] = {
        "purpose": "first-pass CPET QC and candidate detection; not a threshold diagnosis",
        "gas_file": args.gas_xlsx.name,
        "gas_qc": qc_report(gas_raw, gas, gas_columns),
        "exercise_interval": {"start_second": start, "end_second": end, "method": bound_method},
        "smoothing_sensitivity": sensitivity,
        "adjudication_required": [
            "confirm units, calibration/quality flags, protocol stages, cadence, and stop reason",
            "inspect V-slope, VE/VO2, PetO2, VE/VCO2, VE-VCO2, and PetCO2 curves",
            "do not infer LT2/RCP or HRmax if the high end was truncated",
        ],
    }

    if args.ergometer_xlsx:
        ergo_frame = read_sheet(
            args.ergometer_xlsx,
            args.ergometer_sheet,
            args.ergometer_header_row,
            args.ergometer_data_start_row,
            args.ergometer_data_start_column,
        )
        ergo_columns = choose_columns(ergo_frame)
        ergo_raw = standardize(ergo_frame, ergo_columns)
        ergo = regularize(ergo_raw)
        alignment = align_hr(gas, ergo)
        result["ergometer_file"] = args.ergometer_xlsx.name
        result["ergometer_qc"] = qc_report(ergo_raw, ergo, ergo_columns)
        result["clock_alignment"] = alignment
        if alignment:
            candidate_times = sorted(
                {
                    value
                    for analysis in sensitivity
                    for value in (
                        analysis["vt1_consensus_candidate_seconds"],
                        analysis["rcp_consensus_candidate_seconds"],
                    )
                    if value is not None
                }
            )
            result["ergometer_values_at_candidate_times"] = ergometer_values_at(
                ergo,
                candidate_times,
                alignment["ergometer_time_minus_cart_time_seconds"],
            )
            result["classified_threshold_power_candidates"] = classified_threshold_power_candidates(
                ergo,
                sensitivity,
                alignment["ergometer_time_minus_cart_time_seconds"],
            )

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
