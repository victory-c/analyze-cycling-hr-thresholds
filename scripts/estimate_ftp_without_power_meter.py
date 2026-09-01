#!/usr/bin/env python3
"""Estimate auditable FTP proxies without an on-bike power meter.

The outputs preserve the directly estimated construct. They never convert HR to watts.
"""

from __future__ import annotations

import argparse
import json
import math
from statistics import median
from typing import Any


GRAVITY = 9.80665


def lab_proxy(
    candidate_powers_w: list[float],
    instrument_error_pct: float,
    high_end_valid: bool,
) -> dict[str, Any]:
    if not candidate_powers_w or any(power <= 0 for power in candidate_powers_w):
        raise ValueError("candidate powers must be positive")
    if not 0 <= instrument_error_pct <= 20:
        raise ValueError("instrument error must be between 0% and 20%")
    central = float(median(candidate_powers_w))
    error = instrument_error_pct / 100.0
    low = min(candidate_powers_w) * (1 - error)
    high = max(candidate_powers_w) * (1 + error)
    return {
        "method": "synchronized laboratory threshold-power candidates",
        "direct_construct": "pLT2/pRCP candidate",
        "candidate_powers_w": [round(value, 2) for value in candidate_powers_w],
        "central_power_w": round(central, 1),
        "measurement_range_w": [round(low, 1), round(high, 1)],
        "ftp_proxy_candidate_w": round(central, 1) if high_end_valid else None,
        "ftp_proxy_eligibility": (
            "eligible as a proxy candidate: high-end validity explicitly confirmed"
            if high_end_valid
            else "withheld: high-end protocol validity was not explicitly confirmed"
        ),
        "instrument_error_pct": instrument_error_pct,
        "caveat": "Ramp pLT2/pRCP is not automatically steady-state FTP; withhold this proxy if high-end validity, cadence, clock alignment, or ergometer power is doubtful.",
    }


def climb_power(
    system_mass_kg: float,
    distance_m: float,
    elevation_gain_m: float,
    duration_s: float,
    cda_m2: float,
    crr: float,
    air_density: float,
    headwind_mps: float,
    drivetrain_efficiency: float,
    maximal_steady: bool,
) -> dict[str, Any]:
    if system_mass_kg <= 0 or distance_m <= 0 or duration_s <= 0:
        raise ValueError("mass, distance, and duration must be positive")
    if not 0 <= elevation_gain_m < distance_m:
        raise ValueError("elevation gain must be nonnegative and less than route distance")
    if cda_m2 < 0 or crr < 0 or air_density <= 0:
        raise ValueError("CdA/CRR must be nonnegative and air density positive")
    if not 0 < drivetrain_efficiency <= 1:
        raise ValueError("drivetrain efficiency must be in (0, 1]")

    velocity = distance_m / duration_s
    theta = math.asin(elevation_gain_m / distance_m)
    relative_air_velocity = velocity + headwind_mps
    gravity_force = system_mass_kg * GRAVITY * math.sin(theta)
    rolling_force = system_mass_kg * GRAVITY * crr * math.cos(theta)
    aero_force = 0.5 * air_density * cda_m2 * relative_air_velocity * abs(relative_air_velocity)
    components = {
        "gravity_w": gravity_force * velocity / drivetrain_efficiency,
        "rolling_w": rolling_force * velocity / drivetrain_efficiency,
        "aerodynamic_w": aero_force * velocity / drivetrain_efficiency,
    }
    crank_power = sum(components.values())
    duration_minutes = duration_s / 60.0
    eligible = maximal_steady and 40 <= duration_minutes <= 70
    result: dict[str, Any] = {
        "method": "steady-climb physics model",
        "direct_construct": f"virtual mean power for {duration_minutes:.1f} minutes",
        "estimated_crank_power_w": round(crank_power, 1),
        "component_power_w": {key: round(value, 1) for key, value in components.items()},
        "ground_speed_kph": round(velocity * 3.6, 2),
        "average_grade_pct": round(100 * math.tan(theta), 2),
        "relative_air_speed_mps": round(relative_air_velocity, 3),
        "ftp_proxy_candidate_w": round(crank_power, 1) if eligible else None,
        "ftp_proxy_eligibility": (
            "eligible as a rough proxy: maximal steady effort lasting 40–70 minutes"
            if eligible
            else "not automatically eligible; require maximal steady status and 40–70 minute duration"
        ),
        "caveat": "Run low/base/high scenarios for wind, CdA, Crr, elevation, mass, and efficiency; the model omits acceleration, drafting, braking, and cornering.",
    }
    return result


def parse_effort(text: str) -> tuple[float, float]:
    try:
        duration, power = (float(value) for value in text.split(":", 1))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("effort must be SECONDS:WATTS") from error
    if duration <= 0 or power <= 0:
        raise argparse.ArgumentTypeError("effort duration and power must be positive")
    return duration, power


def critical_power(efforts: list[tuple[float, float]]) -> dict[str, Any]:
    if len(efforts) < 3:
        raise ValueError("critical-power fitting requires at least three efforts")
    durations = [duration for duration, _ in efforts]
    if max(durations) / min(durations) < 2:
        raise ValueError("effort durations need at least a two-fold spread")
    x = [1.0 / duration for duration, _ in efforts]
    y = [power for _, power in efforts]
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    denominator = sum((value - x_mean) ** 2 for value in x)
    if denominator == 0:
        raise ValueError("effort durations must differ")
    w_prime = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / denominator
    cp = y_mean - w_prime * x_mean
    if cp <= 0 or w_prime <= 0:
        raise ValueError("fit produced nonphysiological CP or W'; inspect effort validity")
    fitted = [cp + w_prime / duration for duration in durations]
    residuals = [observed - predicted for observed, predicted in zip(y, fitted)]
    total_squares = sum((value - y_mean) ** 2 for value in y)
    residual_squares = sum(value**2 for value in residuals)
    r_squared = 1 - residual_squares / total_squares if total_squares else 1.0
    return {
        "method": "two-parameter critical-power model P(t) = CP + W'/t",
        "direct_construct": "critical power",
        "efforts": [
            {"duration_s": duration, "power_w": power, "fitted_power_w": round(predicted, 1)}
            for (duration, power), predicted in zip(efforts, fitted)
        ],
        "critical_power_w": round(cp, 1),
        "w_prime_j": round(w_prime, 1),
        "r_squared": round(r_squared, 5),
        "max_absolute_residual_w": round(max(abs(value) for value in residuals), 1),
        "ftp_proxy_candidate_w": round(cp, 1),
        "caveat": "CP is not FTP by definition. Input power validity and effort exhaustion determine whether it is a useful FTP proxy.",
    }


def format_markdown(result: dict[str, Any]) -> str:
    lines = [f'**Method:** {result["method"]}', f'**Direct construct:** {result["direct_construct"]}']
    for key in (
        "central_power_w",
        "measurement_range_w",
        "estimated_crank_power_w",
        "critical_power_w",
        "w_prime_j",
        "r_squared",
        "max_absolute_residual_w",
        "ftp_proxy_candidate_w",
        "ftp_proxy_eligibility",
    ):
        if key in result:
            label = key.replace("_", " ")
            lines.append(f"**{label}:** {result[key]}")
    if "component_power_w" in result:
        lines.append("**component power:** " + ", ".join(f"{key}={value}" for key, value in result["component_power_w"].items()))
    lines.append(f'**Caveat:** {result["caveat"]}')
    return "\n\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    subparsers = parser.add_subparsers(dest="method", required=True)

    lab_parser = subparsers.add_parser("lab", help="summarize synchronized pLT2/pRCP candidates")
    lab_parser.add_argument("--candidate-power-w", nargs="+", type=float, required=True)
    lab_parser.add_argument("--instrument-error-pct", type=float, default=0.0)
    lab_parser.add_argument("--high-end-valid", action="store_true")

    climb_parser = subparsers.add_parser("climb", help="calculate steady-climb virtual power")
    climb_parser.add_argument("--system-mass-kg", type=float, required=True)
    climb_parser.add_argument("--distance-m", type=float, required=True)
    climb_parser.add_argument("--elevation-gain-m", type=float, required=True)
    climb_parser.add_argument("--duration-s", type=float, required=True)
    climb_parser.add_argument("--cda-m2", type=float, required=True)
    climb_parser.add_argument("--crr", type=float, required=True)
    climb_parser.add_argument("--air-density", type=float, required=True)
    climb_parser.add_argument("--headwind-mps", type=float, default=0.0)
    climb_parser.add_argument("--drivetrain-efficiency", type=float, required=True)
    climb_parser.add_argument("--maximal-steady", action="store_true")

    cp_parser = subparsers.add_parser("critical-power", help="fit CP from duration:power pairs")
    cp_parser.add_argument("--effort", nargs="+", type=parse_effort, required=True)

    args = parser.parse_args()
    if args.method == "lab":
        result = lab_proxy(args.candidate_power_w, args.instrument_error_pct, args.high_end_valid)
    elif args.method == "climb":
        result = climb_power(
            args.system_mass_kg,
            args.distance_m,
            args.elevation_gain_m,
            args.duration_s,
            args.cda_m2,
            args.crr,
            args.air_density,
            args.headwind_mps,
            args.drivetrain_efficiency,
            args.maximal_steady,
        )
    else:
        result = critical_power(args.effort)
    if args.format == "markdown":
        print(format_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
