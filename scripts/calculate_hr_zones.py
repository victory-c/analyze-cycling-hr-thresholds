#!/usr/bin/env python3
"""Calculate a transparent dual-threshold five-zone cycling HR model."""

from __future__ import annotations

import argparse
import json
import math
from typing import Any


def validate_inputs(vt1: int, lthr: int, max_hr: int | None) -> None:
    if not 30 <= vt1 < lthr <= 260:
        raise ValueError("require 30 <= VT1 < LTHR <= 260 bpm")
    if max_hr is not None and not lthr <= max_hr <= 280:
        raise ValueError("max HR must be >= LTHR and <= 280 bpm")


def pct(value: int, lthr: int) -> float:
    return round(100.0 * value / lthr, 1)


def build_zones(vt1: int, lthr: int, max_hr: int | None = None) -> dict[str, Any]:
    validate_inputs(vt1, lthr, max_hr)
    z1_upper = math.floor(0.90 * vt1)
    z3_upper = math.floor(0.90 * lthr)
    bounds = [
        ("Z1", None, z1_upper, "Domain 1 (lower)"),
        ("Z2", z1_upper + 1, vt1 - 1, "Domain 1 (upper)"),
        ("Z3", vt1, z3_upper, "Domain 2 (lower)"),
        ("Z4", z3_upper + 1, lthr - 1, "Domain 2 (upper)"),
        ("Z5", lthr, max_hr, "Domain 3"),
    ]
    for name, lower, upper, _ in bounds:
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"rounding creates an empty {name}; revise the zone model")

    zones = []
    for name, lower, upper, domain in bounds:
        zones.append(
            {
                "zone": name,
                "lower_bpm": lower,
                "upper_bpm": upper,
                "lower_pct_lthr": pct(lower, lthr) if lower is not None else None,
                "upper_pct_lthr": pct(upper, lthr) if upper is not None else None,
                "domain": domain,
            }
        )

    fixed_lower = 0.73 * lthr
    fixed_upper = 0.88 * lthr
    return {
        "model": "dual-threshold five-zone operational model",
        "anchors": {"vt1_bpm": vt1, "lthr_bpm": lthr, "max_hr_bpm": max_hr},
        "zones": zones,
        "garmin_custom_lower_boundaries_bpm": {
            "Z2": z1_upper + 1,
            "Z3": vt1,
            "Z4": z3_upper + 1,
            "Z5": lthr,
        },
        "garmin_fixed_lthr_example": {
            "Z2_percent": "73-88%",
            "mathematical_lower_bpm": round(fixed_lower, 2),
            "mathematical_upper_bpm": round(fixed_upper, 2),
            "nearest_integer_lower_bpm": round(fixed_lower),
            "nearest_integer_upper_bpm": round(fixed_upper),
            "note": "Device rounding and boundary inclusivity can differ by model/firmware.",
        },
        "caveat": "Only VT1 and LTHR are physiological anchors; the 90% splits are operational.",
    }


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "| Zone | BPM | %LTHR | Domain |",
        "|---|---:|---:|---|",
    ]
    for zone in result["zones"]:
        lo = "open" if zone["lower_bpm"] is None else str(zone["lower_bpm"])
        hi = "open" if zone["upper_bpm"] is None else str(zone["upper_bpm"])
        lo_pct = "open" if zone["lower_pct_lthr"] is None else f'{zone["lower_pct_lthr"]:.1f}%'
        hi_pct = "open" if zone["upper_pct_lthr"] is None else f'{zone["upper_pct_lthr"]:.1f}%'
        lines.append(f'| {zone["zone"]} | {lo}–{hi} | {lo_pct}–{hi_pct} | {zone["domain"]} |')

    boundaries = result["garmin_custom_lower_boundaries_bpm"]
    fixed = result["garmin_fixed_lthr_example"]
    lines.extend(
        [
            "",
            "Garmin custom lower boundaries: "
            + ", ".join(f"{key}={value}" for key, value in boundaries.items()),
            f'Garmin fixed-LTHR example Z2 (73–88%): {fixed["mathematical_lower_bpm"]:.2f}–'
            f'{fixed["mathematical_upper_bpm"]:.2f} bpm; nearest integers '
            f'{fixed["nearest_integer_lower_bpm"]}–{fixed["nearest_integer_upper_bpm"]} bpm.',
            "",
            result["caveat"],
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vt1", type=int, required=True, help="VT1/GET heart rate in bpm")
    parser.add_argument("--lthr", type=int, required=True, help="cycling LTHR/LT2 in bpm")
    parser.add_argument("--max-hr", type=int, help="credible cycling HRmax; omit if unknown")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    result = build_zones(args.vt1, args.lthr, args.max_hr)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(result))


if __name__ == "__main__":
    main()

