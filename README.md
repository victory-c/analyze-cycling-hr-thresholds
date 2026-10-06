# Cycling HR Threshold & FTP Analysis

[![Tests](https://github.com/victory-c/analyze-cycling-hr-thresholds/actions/workflows/tests.yml/badge.svg)](https://github.com/victory-c/analyze-cycling-hr-thresholds/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

A reusable skill and CLI toolkit for **Claude, Codex, and other coding agents**, using Garmin data (MCP, a direct read-only CLI, or exports), the **official Strava MCP**, or local activity and cycling CPET files to produce defensible heart-rate thresholds, training zones, and—when no on-bike power meter exists—carefully labeled FTP proxies.

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
- Discovers the current client's tools without hard-coded provider prefixes; supports field-only or lab-only analysis and avoids counting synchronized Garmin/Strava copies as independent efforts.
- Acquires Garmin evidence through either:
  - [`Taxuspt/garmin_mcp`](https://github.com/Taxuspt/garmin_mcp) for MCP-capable agents; or
  - an explicit read-only Garmin Connect API CLI for any agent that can execute Python and read JSON.

## Guardrails

This project deliberately refuses several tempting shortcuts:

- It does not convert heart rate directly to watts.
- It does not treat Garmin settings or an HTML lab conclusion as raw evidence.
- It does not assume a running threshold applies to cycling.
- It does not blindly average field and laboratory estimates.
- It does not automatically call ramp `pRCP`, critical power, or virtual climb power “FTP.”
- It does not default to `95% × 20-minute power` for an individual athlete.
- It does not publish names, coordinates, activity IDs, or raw health files.

## Install

The same skill folder works in Claude and Codex. Choose the installation below for
your client; installing the skill does **not** connect an account or grant access
to health data. If the target folder already exists, review its changes before
updating it instead of overwriting a divergent copy.

`SKILL.md` is the canonical workflow, `AGENTS.md` is a compact repository instruction, and every analysis/data-acquisition utility is an ordinary Python CLI. Other coding agents (Cursor, Cline, OpenCode, other MCP clients, IDE agents, CI workers, or a plain shell) can use the same files; read [coding-agent integration](references/coding-agent-integration.md) for the portable prompt and backend decision. Product-specific rule files are intentionally not copies of the full methodology; keeping one canonical contract prevents drift.

### Codex

Clone the repository into the Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/victory-c/analyze-cycling-hr-thresholds.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/analyze-cycling-hr-thresholds"
```

Install Python dependencies used by the CPET analyzer and FIT decoding:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/analyze-cycling-hr-thresholds"
python -m pip install -r scripts/requirements.txt
```

Invoke it in Codex with:

```text
$analyze-cycling-hr-thresholds
```

### Claude Code

```bash
mkdir -p "$HOME/.claude/skills"
git clone https://github.com/victory-c/analyze-cycling-hr-thresholds.git \
  "$HOME/.claude/skills/analyze-cycling-hr-thresholds"
cd "$HOME/.claude/skills/analyze-cycling-hr-thresholds"
python -m pip install -r scripts/requirements.txt
```

Invoke `/analyze-cycling-hr-thresholds` in Claude Code. For Claude web/desktop
custom skills, upload a ZIP containing the skill folder through the skills UI
when available. That does not give a hosted client access to your local files;
provide the relevant exports in that client.

### Example prompt

```text
Use the analyze-cycling-hr-thresholds skill to analyze my last 90 days of
cycling from the available Garmin or official Strava connection and any
CPET files I provide. Analyze sources independently, reconcile LTHR, VT1,
and RCP, and estimate an FTP proxy only if power evidence supports one.
Give me HR zones with confidence ranges and caveats; do not change my settings.
```

### Other coding agents

For another coding agent, clone the repository anywhere accessible and instruct the agent to read `AGENTS.md` and `SKILL.md`. It can then use MCP or the direct CLI described below.

### Connect data sources separately

Use a Garmin backend (below), the official Strava MCP at
`https://mcp.strava.com/mcp`, or local exports. Neither both providers nor a CPET
test is required. The skill discovers actual capabilities; summaries alone do
not support full-resolution threshold analysis.

The skill is client-portable, but MCP authentication compatibility is separate.
On September 6, 2026, Claude Code authentication and tool discovery succeeded;
Codex CLI 0.147.0 rejected inconsistent Strava OAuth issuer metadata before
consent. This is not a claim that Strava permanently supports only Claude.
Activity access and eligibility still require a successful read. The skill does
not bypass issuer validation or reuse another client's tokens.

See [client setup, capability routing, and connection diagnostics](references/client-and-source-routing.md)
for the observed schemas, native setup commands, and official documentation.
This optional diagnostic reads public metadata only (no login or private data):

```bash
python scripts/check_strava_oauth.py
```

Exit status `0` means metadata is consistent, **not** that you are logged in;
status `1` reports a mismatch, changed discovery, or fetch/parse failure.

## Choose a Garmin backend

These are alternate transports for the **same Garmin source**. Using both does not create two independent physiological datasets; the CPET or another separately collected test remains the independent source.

| Choice | Use when | Agent interface | Garmin API status |
|---|---|---|---|
| `garmin_mcp` | The agent supports local MCP servers | MCP tools | Unofficial Garmin Connect API via `python-garminconnect` |
| Direct CLI | The agent can run Python and read files | Versioned JSON/FIT | Unofficial, explicit read-only Garmin Connect endpoints |
| Official Activity API | You have an approved business integration | Your own OAuth 2.0 adapter | Official Garmin Developer Program |

Garmin's official [Activity API](https://developer.garmin.com/gc-developer-program/activity-api/) is a strong production route, but the [Developer Program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/) currently describes it as an application/approval-based business program, not a self-service personal-account API. See [Garmin data-source backends](references/garmin-data-sources.md) for the feasibility analysis, security model, endpoint coverage, and caveats.

### Option A: `garmin_mcp`

Authenticate locally once, without putting a password in the agent configuration:

```bash
uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
```

Render a minimal read-only MCP configuration:

```bash
python scripts/render_garmin_mcp_config.py --client generic
python scripts/render_garmin_mcp_config.py --client mcp-json
python scripts/render_garmin_mcp_config.py --client codex
python scripts/render_garmin_mcp_config.py --client opencode
```

The renderer only prints configuration and never edits global settings. The allowlist excludes Garmin write tools.

### Option B: direct read-only API CLI

The direct backend uses `python-garminconnect` for hardened authentication/token refresh and makes the analysis endpoint calls explicitly. Its optional dependency currently requires Python 3.12+.

```bash
python3.12 -m pip install -r scripts/requirements-garmin-direct.txt
python3.12 scripts/fetch_garmin.py auth
```

Fetch a complete paginated cycling inventory and a full candidate bundle:

```bash
python3.12 scripts/fetch_garmin.py activities \
  --start-date 2020-01-01 --end-date 2026-09-01 \
  --activity-type cycling \
  --output private/garmin/activities.json

python3.12 scripts/fetch_garmin.py bundle \
  --activity-id 123456789 \
  --output private/garmin/activity-123456789.json
```

The bundle preserves summary, lap/split, historical HR-zone, and full FIT record/session/lap data. `derived` retrieves configured zones, cycling FTP, raw lactate-threshold payload, max metrics, training status, and profile settings as metadata:

```bash
python3.12 scripts/fetch_garmin.py derived --date 2026-09-01 \
  --output private/garmin/derived.json
```

The CLI has no email/password flags, makes no write calls, and wraps JSON in a versioned provenance envelope. CI uses fake transports only and never authenticates to Garmin.

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
  --windows-min 20 30 40 60 --max-interpolation-gap-seconds 5
```

The output ranks sustained HR windows as candidate evidence. It does not automatically diagnose LTHR.

`--activity` (alias `--fit-json`) also accepts original FIT files from any head unit, including Strava bulk-export `.fit.gz` files and Garmin "Export Original" `.zip` files, as well as stream JSON from the official Strava MCP, the intervals.icu API, and the Strava REST API:

```bash
python scripts/analyze_field_hr.py \
  --activity ride.fit strava_streams.json intervals_streams.json \
  --windows-min 20 30 40 60
```

Request Strava MCP streams without `resolution`: downsampled streams leave gaps that the analyzer deliberately will not bridge. intervals.icu returns empty stubs for activities that it imported from Strava. See [activity inputs](references/garmin-data-workflow.md#activity-inputs-for-the-field-helper) for each source.

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
├── AGENTS.md                        # Portable coding-agent entrypoint
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

- [Claude/Codex and Garmin/Strava/local source routing](references/client-and-source-routing.md)
- [Field-data workflow](references/garmin-data-workflow.md)
- [Garmin data-source feasibility and backends](references/garmin-data-sources.md)
- [Coding-agent integration](references/coding-agent-integration.md)
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

The direct Garmin backend is optional and has its own pinned requirements file so the core analyzers remain usable without Garmin dependencies.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Never commit real athlete exports or identifiable health data, including in tests and issue attachments.

## Disclaimer

This project supports training analysis; it is not a medical device and does not provide diagnosis or clearance for exercise. Automated breakpoints and FTP values are candidates that require protocol-aware interpretation.

## License

[MIT](LICENSE)
