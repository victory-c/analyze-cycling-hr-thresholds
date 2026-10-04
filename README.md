# Cycling HR Threshold & FTP Analysis

[![Tests](https://github.com/victory-c/analyze-cycling-hr-thresholds/actions/workflows/tests.yml/badge.svg)](https://github.com/victory-c/analyze-cycling-hr-thresholds/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

A reusable Codex skill for reconciling Garmin field data and raw cycling CPET gas-exchange data into defensible heart-rate thresholds, training zones, and—when no on-bike power meter exists—carefully labeled FTP proxies.

The central principle is simple: analyze every source independently, audit its validity, and reconcile physiological constructs rather than averaging numbers that merely have similar labels.

## What it does

- Estimates cycling LTHR/LT2 from repeated sustained field efforts.
- Identifies VT1/GET and VT2/RCP candidates from breath-by-breath CPET data.
- Aligns metabolic-cart and ergometer clocks through their common HR traces.
- Separates VT1 and RCP power candidates across smoothing choices.
- Builds dual-threshold, Garmin-ready HR zones in bpm and `%LTHR`.
- Estimates FTP proxies without a field power meter from:
  - synchronized laboratory ergometer power at LT2/RCP;
  - controlled-climb physics;
  - multi-duration critical-power fitting.
- Reports confidence, plausible ranges, disagreements, and the single most useful follow-up test.

## Guardrails

This project deliberately refuses several tempting shortcuts:

- It does not convert heart rate directly to watts.
- It does not treat Garmin settings or an HTML lab conclusion as raw evidence.
- It does not assume a running threshold applies to cycling.
- It does not blindly average field and laboratory estimates.
- It does not automatically call ramp `pRCP`, critical power, or virtual climb power “FTP.”
- It does not default to `95% × 20-minute power` for an individual athlete.
- It does not publish names, coordinates, activity IDs, or raw health files.

## Install as a Codex skill

Clone the repository into the Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/victory-c/analyze-cycling-hr-thresholds.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/analyze-cycling-hr-thresholds"
```

Install Python dependencies used by the CPET analyzer:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/analyze-cycling-hr-thresholds"
python -m pip install -r scripts/requirements.txt
```

Invoke it in Codex with:

```text
$analyze-cycling-hr-thresholds
```

Example prompt:

```text
Use $analyze-cycling-hr-thresholds to analyze my complete Garmin cycling
history and raw CPET workbook independently, reconcile LTHR, VT1, and RCP,
estimate an FTP proxy if the available power evidence supports one, and give
me Garmin-ready HR zones with confidence ranges and caveats.
```

## Command-line tools

### Calculate HR zones

```bash
python scripts/calculate_hr_zones.py \
  --vt1 150 --lthr 188 --max-hr 204 --format markdown
```

### Summarize Garmin/FIT HR evidence

```bash
python scripts/analyze_field_hr.py \
  --fit-json activity_a.json activity_b.json \
  --windows-min 20 30 40 60
```

The output ranks sustained HR windows as candidate evidence. It does not automatically diagnose LTHR.

It also reads the column-oriented streams returned by the official Strava MCP's `get_activity_streams` tool, for example `{"time": [...], "heart_rate": [...]}`. Request `time` and `heart_rate` without `resolution`: downsampled streams leave gaps that the analyzer deliberately will not bridge. `--activity-list-json` also accepts Strava's `list_activities` output.

### Analyze raw CPET workbooks

```bash
python scripts/analyze_cpet.py \
  --gas-xlsx gas.xlsx \
  --ergometer-xlsx ergometer.xlsx \
  --output-json cpet_analysis.json
```

The analyzer inventories signal quality, regularizes irregular breaths, tests multiple smoothing windows, aligns clocks, and emits classified VT1/RCP candidates. Those candidates still require physiological adjudication.

### Estimate an FTP proxy without an on-bike meter

From independently validated laboratory threshold-power candidates:

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown lab \
  --candidate-power-w 250 258 263 \
  --instrument-error-pct 2 \
  --high-end-valid
```

From a controlled 50-minute climb:

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown climb \
  --system-mass-kg 82 \
  --distance-m 10000 \
  --elevation-gain-m 700 \
  --duration-s 3000 \
  --cda-m2 0.32 \
  --crr 0.005 \
  --air-density 1.18 \
  --headwind-mps 0 \
  --drivetrain-efficiency 0.975 \
  --maximal-steady
```

From several valid all-out duration–power pairs:

```bash
python scripts/estimate_ftp_without_power_meter.py --format markdown critical-power \
  --effort 180:340 420:285 720:270
```

Read [the FTP proxy methodology](references/ftp-without-power-meter.md) before interpreting these outputs.

## Method map

| Question | Preferred evidence | Output label |
|---|---|---|
| Cycling LTHR/LT2 | Repeated sustained cycling HR, ideally with power/context | LTHR/LT2 estimate and range |
| VT1/GET | Convergent gas-exchange markers | VT1/GET estimate and range |
| VT2/RCP | Convergent high-end gas-exchange markers | VT2/RCP or not identifiable |
| FTP without a field meter | Calibrated lab power at valid LT2/RCP | `pLT2`/`pRCP`, secondarily FTP proxy |
| FTP from a climb | Complete mechanics plus sensitivity scenarios | Virtual climb power, possibly FTP proxy |
| FTP from several efforts | Two-parameter CP model | CP, secondarily FTP proxy |

## Repository layout

```text
.
├── SKILL.md                         # Agent-facing workflow
├── agents/openai.yaml              # Skill UI metadata
├── references/                     # Methodological guidance
├── scripts/                        # Auditable analysis utilities
│   └── tests/                      # Unit tests
├── .github/                        # CI and contribution templates
├── CONTRIBUTING.md
├── CITATION.cff
└── LICENSE
```

## Methodology and evidence

- [Garmin field-data workflow](references/garmin-data-workflow.md)
- [CPET threshold methods](references/cpet-threshold-methods.md)
- [FTP estimation without an on-bike power meter](references/ftp-without-power-meter.md)
- [Reconciliation and zone construction](references/reconciliation-and-zones.md)
- [Final report contract](references/report-contract.md)

Primary research links are included next to the claims they support in the reference files.

## Development

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s scripts/tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Never commit real athlete exports or identifiable health data, including in tests and issue attachments.

## Disclaimer

This project supports training analysis; it is not a medical device and does not provide diagnosis or clearance for exercise. Automated breakpoints and FTP values are candidates that require protocol-aware interpretation.

## License

[MIT](LICENSE)
