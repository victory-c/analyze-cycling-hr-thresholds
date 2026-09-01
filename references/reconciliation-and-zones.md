# Reconciliation and zone construction

## Reconcile constructs, not just numbers

Create a table with one row per source and columns for construct, protocol, evidence, central estimate, plausible range, and limitations. Ask what each source actually measured.

- A sound incremental CPET can be the strongest source for VT1.
- A truncated or cadence-limited CPET may be weak for RCP or cycling LTHR.
- Repeated long, hard field efforts can be strong for operational cycling LTHR while being weak for VT1.
- Garmin's algorithmic threshold is usable only after sport and supporting activity evidence are verified.

When estimates disagree, investigate sensor modality, clock alignment, protocol length, cadence, heat, fatigue, HR drift, power availability, and whether the labels refer to the same construct. Do not split the difference automatically.

Heat can raise HR at a given workload and alter drift. Interpret outdoor high-HR evidence with environmental context; see [Racinais et al. (2022)](https://pubmed.ncbi.nlm.nih.gov/36507952/) and [Périard et al. (2021)](https://pubmed.ncbi.nlm.nih.gov/33735834/).

## Recommended hierarchy

1. Define three physiological domains using measured VT1 and LT2/LTHR.
2. If a five-zone device model is needed, subdivide within domains explicitly.
3. Preserve measured thresholds as anchors; do not move them to fit a device's template.

## Default dual-threshold five-zone model

Given integer `VT1` and `LTHR`, with `VT1 < LTHR`:

| Zone | BPM rule | Meaning |
|---|---:|---|
| Z1 | through `floor(0.90 × VT1)` | lower part of Domain 1 |
| Z2 | next bpm through `VT1 - 1` | upper part of Domain 1 |
| Z3 | `VT1` through `floor(0.90 × LTHR)` | lower part of Domain 2 |
| Z4 | next bpm through `LTHR - 1` | upper part of Domain 2 |
| Z5 | `LTHR` through known HRmax, or open-ended | Domain 3 |

The two 90% splits are pragmatic. Only VT1 and LTHR are physiological anchors. Report every boundary in bpm and as an exact percentage of LTHR so device rounding is visible.

## Garmin entry

If Garmin accepts custom BPM ranges, enter the four lower boundaries for Z2–Z5 and keep the independently derived LTHR in the athlete profile. Verify whether the setting applies globally or only to cycling.

If the device forces fixed percentages of LTHR, calculate what those percentages produce. For a template with Z2 = 73–88% LTHR:

- mathematical interval: `0.73 × LTHR` through `0.88 × LTHR`;
- device-visible integers depend on Garmin's rounding and inclusivity;
- compare the resulting upper Z2 boundary with measured VT1;
- if they conflict materially, use custom BPM zones elsewhere or treat Garmin labels as display bins, not physiology.

Never alter LTHR merely to make Garmin's Z2 coincide with VT1.

## Confidence and updates

Attach confidence to the anchors rather than pretending every zone edge has independent precision. If VT1 is ±3 bpm and LTHR is ±2 bpm, operational edges derived from them inherit that uncertainty.

Reassess after meaningful fitness change, illness, heat acclimation, medication change, or a well-controlled new test. Do not change zones from one anomalous ride.

## Single best follow-up test

When the evidence remains ambiguous, recommend one sport-specific staged cycling test using:

- a calibrated power meter or ergometer;
- the athlete's normal cadence and position;
- chest-strap HR;
- synchronized breath-by-breath gas exchange;
- capillary blood lactate near the end of each sufficiently long stage;
- a protocol that continues to a separately verified maximal endpoint when safe and appropriate.

This one session most directly resolves clock, workload, VT1, lactate-transition, RCP, and HRmax ambiguity.

