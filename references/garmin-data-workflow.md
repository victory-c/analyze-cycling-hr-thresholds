# Garmin field-data workflow

## Goal

Estimate cycling LTHR/LT2 evidence from sustained field HR, independently of the laboratory result. Garmin data usually cannot locate VT1 confidently unless workload was controlled and power, lactate, gas exchange, or a validated surrogate was recorded.

## 1. Build a complete inventory

Paginate through the entire activity history. Retain cycling subtypes and identify indoor/outdoor duplicates, multisport legs, recordings with zero duration, and activities with no HR.

For each usable activity capture:

- date, sport/subsport, elapsed and moving duration;
- average/max HR and HR coverage;
- recording interval and gaps;
- device and HR-sensor provenance when exposed;
- laps, temperature, elevation, cadence, speed, and power availability;
- Garmin-set max HR, resting HR, zones, FTP, threshold, and the sport to which each derived metric applies.

Do not interpret a configured boundary as measured evidence. A user's zones may have changed during the history, and historical time-in-zone summaries may therefore be incomparable.

## 2. Screen data quality

Prefer chest-strap HR for threshold work. Optical HR can be usable, but flag cadence lock, sudden step changes, implausible plateaus, dropouts, and spikes. Preserve the actual sensor provenance as unknown if the export does not prove it.

Check that timestamps are monotonic. Quantify coverage, median sample interval, long gaps, and interpolation. Garmin smart recording may be irregular; do not fill long gaps as though HR were continuously observed.

Heat, dehydration, fatigue, altitude, stimulants, illness, and accumulated cardiac drift can elevate HR for a given workload. They are reasons to interpret a ride in context, not automatic reasons to discard it.

## 3. Select threshold-relevant efforts

Rank rides by continuous best-window mean HR for 20, 30, 40, and 60 minutes. Inspect several top candidates rather than only the highest value. Favor:

- uninterrupted, hard, approximately steady efforts;
- minimal coasting, descending, stops, or obvious stochastic surges;
- enough duration to expose whether HR stabilized or drifted;
- repetitions across different days;
- known power or terrain context when available.

For a conventional 30-minute field test, the final 20-minute mean HR can be one LTHR estimate, but it is not universally valid and should not override contradictory time-series evidence.

## 4. Inspect each candidate

Plot or tabulate HR by minute and five-minute block. Check:

- onset kinetics and whether the candidate window begins after HR has risen;
- late-window slope and decoupling;
- pauses and missing samples;
- whether cadence or terrain changes explain HR changes;
- whether similar HR is sustainable in other rides;
- whether maximal HR spikes are physiologically plausible.

Power, when present, materially strengthens interpretation. With HR only, a rising HR trace may reflect rising effort, cardiovascular drift, or both.

If field power is absent, do not regress watts directly from HR or speed. For a continuous climb with reliable mass, geometry, weather, surface, and time, follow [ftp-without-power-meter.md](ftp-without-power-meter.md) to estimate virtual power with explicit sensitivity bounds.

## 5. Form an independent field conclusion

Report:

- a central LTHR/LT2 estimate only if repeated sustained evidence clusters;
- a plausible range rather than false precision;
- the specific windows and rides supporting it;
- sensor, power, environmental, and protocol limitations;
- whether VT1 is identifiable. Usually mark VT1 as not identified from unstructured HR-only rides.

Do not use the laboratory value while making this conclusion. Unblind the second source only during reconciliation.

## Garmin-derived metrics

Garmin's lactate-threshold field may come from running. Verify the sport and algorithm context before using it. Stale FTP, max HR, and zone settings are clues to configuration history, not validation of physiology.

Official Garmin manuals describe the device's percentage-based zone behavior, but device model and firmware vary:

- [Edge 540 heart-rate zones](https://www8.garmin.com/manuals/webhelp/GUID-17DE938E-466A-4746-BDBF-7A6FC1B3A32C/EN-GB/GUID-94A5A126-6BB2-47F6-8040-EAD29EC66C2B.html)
- [Forerunner heart-rate zone settings](https://www8.garmin.com/manuals/webhelp/GUID-25E3235D-44D2-4384-A591-DD1D71BEBCB1/TR-TR/GUID-30C91919-943C-44E9-8048-901AC0881AEA.html)
