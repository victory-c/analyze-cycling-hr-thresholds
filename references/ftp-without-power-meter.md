# Estimating FTP without an on-bike power meter

## Core limitation

Heart rate is an internal response, not mechanical work. Do not convert bpm to watts from HR alone. Speed is also insufficient without gradient, mass, wind, air density, rolling resistance, aerodynamics, acceleration, drafting, and braking. If none of the methods below has defensible power input, report FTP as not identifiable.

Use “FTP proxy” for an indirect estimate. Preserve the directly supported construct—such as ergometer power at RCP (`pRCP`), virtual climb power, or critical power (`CP`)—alongside any FTP interpretation.

## Evidence hierarchy

### 1. Synchronized laboratory ergometer power

Use this first when the athlete has no field power meter but the CPET used a calibrated cycle ergometer.

1. Verify the ergometer rather than trusting the metabolic cart's duplicated work-rate channel.
2. Align the gas-cart and ergometer clocks from their common HR streams.
3. Identify LT2/RCP independently from gas exchange or lactate.
4. Extract ergometer power at every defensible threshold candidate and across smoothing choices.
5. Use the median candidate power as the central `pLT2`/`pRCP`; use the candidate spread plus stated instrument accuracy as the measurement range.
6. Audit cadence, stage duration, ramp rate, high-end validity, and stop reason.

Ramp power at RCP is not automatically a steady 60-minute power because VO2 and metabolite kinetics lag a rising workload. Keep the label `pRCP` unless a steady-state or time-trial validation supports calling it FTP. If the high end was truncated or cadence-limited, withhold the FTP proxy.

`scripts/analyze_cpet.py` reports `classified_threshold_power_candidates`, keeping VT1 and RCP power values separate across smoothing choices. Pass only the physiologically adjudicated RCP/LT2 candidates to:

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown lab \
  --candidate-power-w 250 258 263 --instrument-error-pct 2 --high-end-valid
```

### 2. Controlled climb virtual power

Use a continuous, steady climb with no drafting, braking, coasting, or meaningful descent. Prefer low and known wind, a reliable route distance/elevation profile, exact rider-plus-bike mass, suitable tires/surface, and repeat trials.

For constant speed on a climb, estimate crank power from:

`P = v × (m g sin(theta) + m g Crr cos(theta) + 0.5 rho CdA v_air |v_air|) / efficiency`

where `theta = asin(elevation_gain / route_distance)` and `v_air = ground_speed + headwind` under the script's sign convention. The model omits acceleration and cornering losses.

Run low/base/high scenarios for uncertain wind, CdA, Crr, elevation, and drivetrain efficiency; do not present only one decimal-perfect result. A steep climb reduces the aerodynamic share but does not eliminate uncertainty. The road-cycling power model was experimentally validated under controlled parameterization by [Martin et al. (1998)](https://pubmed.ncbi.nlm.nih.gov/28121252/).

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown climb \
  --system-mass-kg 82 --distance-m 10000 --elevation-gain-m 700 \
  --duration-s 3000 --cda-m2 0.32 --crr 0.005 --air-density 1.18 \
  --headwind-mps 0 --drivetrain-efficiency 0.975 --maximal-steady
```

Only call a 40–70 minute maximal, approximately steady result an FTP proxy. Outside that duration range, report virtual power for that duration and avoid an automatic conversion.

### 3. Multi-duration critical-power model

If at least three valid all-out efforts have estimated power, fit:

`P(t) = CP + W' / t`

Use meaningfully separated durations and inspect residuals. Field work has shown agreement when 3-, 7-, and 12-minute all-out cycling tests were used, but virtual-power errors still propagate into CP; see [Karsten et al. (2014)](https://pubmed.ncbi.nlm.nih.gov/24022574/).

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown critical-power \
  --effort 180:340 420:285 720:270
```

CP and FTP are related performance-threshold concepts, not interchangeable definitions. Report the fitted result as `CP` and only secondarily as an FTP proxy.

## Do not default to 95% of 20-minute power

The common `FTP20 = 0.95 × 20-minute mean power` rule is an unvalidated individual assumption unless the athlete has established that relationship. In trained cyclists, [Borszcz et al. (2018)](https://pubmed.ncbi.nlm.nih.gov/29801189/) found small group bias but wide individual limits of agreement between FTP methods, and time to exhaustion at FTP20 varied substantially. If a user explicitly requests the rule, show both raw 20-minute virtual power and the heuristic result, label the multiplier as assumed, and do not let it override stronger lab or multi-duration evidence.

## Reconciliation and confidence

Never average lab pRCP, climb virtual power, CP, and a 20-minute heuristic blindly. Compare their construct validity and uncertainty:

- calibrated staged/steady lab power with a valid LT2 has the highest physiological specificity;
- aligned ramp pRCP is useful but has kinetics/protocol uncertainty;
- repeatable steep-climb virtual power can support an operational FTP range;
- CP from several valid efforts is stronger than a single duration but is still not FTP by definition;
- HR-only or speed-only inference is insufficient.

Report central value, interval, method label, direct inputs, assumptions, sensitivity, and confidence. State whether the result is safe for rough training-load configuration or too uncertain for FTP-based zones.
