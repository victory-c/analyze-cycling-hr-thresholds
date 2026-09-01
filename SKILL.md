---
name: analyze-cycling-hr-thresholds
description: Independently estimate cycling LTHR/LT2, VT1/GET, VT2/RCP, and—when no on-bike power meter exists—defensible FTP or threshold-power proxies from Garmin cycling history and/or raw CPET breath-by-breath files; audit sensor and protocol quality; reconcile field and laboratory evidence without blind averaging; and produce physiologically defensible HR zones plus Garmin-ready settings. Use for cycling threshold analysis, CPET interpretation, indirect FTP estimation, Garmin zone setup, or disagreements between lab and field thresholds.
---

# Analyze Cycling Heart-Rate Thresholds

Estimate thresholds from each source independently, preserve uncertainty, and only then reconcile the results. Treat automated outputs as evidence summaries rather than diagnoses.

## Non-negotiable rules

- Do not anchor to an athlete's previous threshold, Garmin setting, HTML conclusion, or requested answer.
- Do not average lab and field estimates merely because both exist. Decide which physiological construct each source can identify.
- Prefer raw time series over derived summaries. Preserve timestamps, units, missingness, and sensor provenance.
- Verify sport specificity. A running lactate-threshold estimate is not a cycling LTHR.
- Separate physiological boundaries from convenient training-zone subdivisions.
- Never convert heart rate directly to watts. With no defensible power input, report FTP as not identifiable.
- Report uncertainty and data limitations. Do not diagnose a medical condition from these files.
- Keep private health data, activity IDs, coordinates, names, and raw exports out of any published repository.

## Workflow

1. Define the question and available sources. Distinguish LTHR/LT2, VT1/GET, VT2/RCP, HRmax, and operational zones.
2. Audit Garmin data by following [garmin-data-workflow.md](references/garmin-data-workflow.md).
3. Audit and analyze raw CPET data by following [cpet-threshold-methods.md](references/cpet-threshold-methods.md).
4. Complete the two estimates independently before viewing or using the other source's numerical conclusion.
5. Reconcile constructs and confidence using [reconciliation-and-zones.md](references/reconciliation-and-zones.md).
6. If FTP is requested without an on-bike meter, follow [ftp-without-power-meter.md](references/ftp-without-power-meter.md) and preserve the directly supported construct.
7. Calculate custom zones with `scripts/calculate_hr_zones.py`; use Garmin's fixed percentage model only as a comparison.
8. Write the result using [report-contract.md](references/report-contract.md).

## Garmin analysis

- Enumerate the complete cycling history with pagination. Record activity type, date, duration, HR coverage, sensor type when available, temperature, laps, power availability, and duplication.
- Inspect raw FIT/HR records for the strongest sustained efforts instead of selecting by headline max HR.
- Use repeated continuous best-window means, especially 20, 30, 40, and 60 minutes. Seek clustering across separate rides and conditions.
- Treat configured HR-zone boundaries, FTP, max HR, and Garmin threshold values as metadata to verify, not observations.
- If power is absent, state that workload stability and cardiac drift cannot be fully separated.
- Do not infer watts from HR or speed alone. Use a controlled climb model only when mass, route geometry, time, wind/aerodynamic assumptions, surface, and pacing are defensible.
- Use `scripts/analyze_field_hr.py` when Garmin/FIT data have been exported as JSON. Its results identify candidate efforts; an analyst must still judge terrain, pauses, heat, drift, and repeatability.

## Laboratory analysis

- Inventory raw columns, units, sampling irregularity, missingness, calibration or quality flags, protocol steps, cadence, and stop reason before detecting thresholds.
- Regularize irregular breath-by-breath observations on elapsed time before applying rolling smoothers. Compare several smoothing windows; a breakpoint that moves materially is weak evidence.
- Identify VT1 with convergent V-slope, VE/VO2, and PetO2 behavior. Identify RCP with VE/VCO2, ventilatory acceleration, and PetCO2 behavior.
- Use RER landmarks only as cross-checks. Do not define VT1 or RCP from a fixed RER alone.
- Align separate metabolic-cart and ergometer clocks by cross-correlating common HR streams. Never assume their timestamps start together.
- Audit whether maximal effort was achieved before equating the final stage with LT2, RCP, or HRmax.
- Use `scripts/analyze_cpet.py` for a first-pass, auditable candidate analysis. Inspect its QC and sensitivity output before interpreting breakpoints.

## FTP without an on-bike power meter

- Prefer synchronized, calibrated ergometer power at independently adjudicated LT2/RCP.
- Treat ramp `pRCP`, critical power, and modeled climb power as distinct constructs and label any FTP interpretation as a proxy.
- For a steady climb, calculate gravitational, rolling, and aerodynamic work and run sensitivity scenarios; one point estimate is insufficient.
- With several valid all-out efforts, fit CP rather than applying a single-duration conversion factor.
- Do not default to `95% × 20-minute power`; individual error can be large.
- Use `scripts/estimate_ftp_without_power_meter.py` for deterministic calculations, then assign confidence from protocol and input quality.

## Zone construction

Prefer three physiological domains first:

- Domain 1: below VT1.
- Domain 2: VT1 through below LT2/LTHR.
- Domain 3: at or above LT2/LTHR.

When five device zones are useful, use this transparent dual-threshold operational split unless the evidence supports a different prescription:

- Z1 upper = `floor(0.90 × VT1)`
- Z2 = next bpm through `VT1 - 1`
- Z3 = `VT1` through `floor(0.90 × LTHR)`
- Z4 = next bpm through `LTHR - 1`
- Z5 = `LTHR` and above

The 90% subdivisions are operational conveniences, not extra physiological thresholds. If rounding creates an empty or overlapping zone, stop and revise the model.

For Garmin, prefer custom BPM boundaries when the device permits them. A built-in percentage-of-LTHR scheme may force ranges such as Z2 = 73–88% of LTHR; calculate and disclose that mismatch rather than changing LTHR to make the zones fit.

## Commands

Calculate zones and Garmin boundaries:

```bash
python scripts/calculate_hr_zones.py --vt1 150 --lthr 188 --max-hr 204 --format markdown
```

Summarize exported field HR evidence:

```bash
python scripts/analyze_field_hr.py --fit-json activity_a.json activity_b.json --windows-min 20 30 40 60
```

Generate a first-pass CPET QC and breakpoint report:

```bash
python scripts/analyze_cpet.py --gas-xlsx gas.xlsx --ergometer-xlsx ergometer.xlsx --output-json cpet_analysis.json
```

Summarize synchronized laboratory threshold-power candidates:

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown lab --candidate-power-w 250 258 263 --instrument-error-pct 2 --high-end-valid
```

Estimate steady-climb virtual power or fit a multi-duration critical-power model by using the examples in [ftp-without-power-meter.md](references/ftp-without-power-meter.md).

Install script dependencies when needed:

```bash
python -m pip install -r scripts/requirements.txt
```

## Completion standard

Do not call the analysis complete unless the report includes source-specific methods, data-quality findings, independent numerical estimates or explicit non-identifiability, reconciliation logic, BPM zones with calculation basis, confidence/ranges, key caveats, Garmin entry guidance, any requested FTP proxy with its direct construct and assumptions, and the single most informative follow-up test.
