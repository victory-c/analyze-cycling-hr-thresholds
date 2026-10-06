# Garmin data-source backends

## Decision summary

The skill supports two interchangeable ways to acquire the **same Garmin Connect evidence**:

| Backend | Best for | Interface | Status |
|---|---|---|---|
| `garmin_mcp` | MCP-capable coding agents | MCP tools over local stdio or HTTP | Unofficial Garmin Connect client through `python-garminconnect` |
| `direct` | Any agent or shell with Python | `scripts/fetch_garmin.py` and versioned JSON | Unofficial, explicit read-only Garmin Connect endpoint calls |

They are not independent physiological sources. Do not count agreement between the MCP and direct output as replication; both ultimately read the same Garmin account and usually the same underlying endpoint/FIT file. A laboratory CPET, lactate test, or separately recorded field test remains independent evidence.

## Why there are official and unofficial routes

Garmin's official [Activity API](https://developer.garmin.com/gc-developer-program/activity-api/) provides activity details and FIT/GPX/TCX files after user consent. It belongs to the cloud-to-cloud [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/overview/). Garmin's current FAQ says that program is for business use, requires application and approval, and uses OAuth 2.0; it is not a self-service personal-account API ([program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/)).

Accordingly:

- use the official Activity API for an approved product or business integration;
- use the two backends in this repository only for a user's own data and only after the user knowingly chooses the unofficial Garmin Connect route;
- expect private endpoint shapes, authentication, and throttling behavior to change without notice;
- never describe the private route as Garmin-supported.

The direct backend's lowest practical layer is explicit endpoint calls over the authenticated transport supplied by [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect). Reimplementing Garmin SSO, MFA, bearer-token refresh, TLS behavior, and token hardening would add security risk without improving the physiological analysis. The project does **not** call high-level activity methods for data retrieval: endpoint paths and pagination are visible in `scripts/fetch_garmin.py`.

## Backend A: Taxuspt `garmin_mcp`

[`Taxuspt/garmin_mcp`](https://github.com/Taxuspt/garmin_mcp) wraps `python-garminconnect` and exposes Garmin data as MCP tools. For this workflow, allow only these read tools:

```text
get_activities_by_date
get_activities
get_activity
get_activity_splits
get_activity_hr_in_timezones
get_activity_fit_data
get_cycling_ftp
get_lactate_threshold
get_training_status
get_user_profile
get_userprofile_settings
```

The allowlist excludes the server's edit, create, upload, scheduling, and delete tools. `get_activity_fit_data(activity_id, include_records=true)` is the important raw-stream path because the server intentionally omits the large `get_activity_details` endpoint.

### One-time authentication

Use Python 3.12 and authenticate before starting the MCP client:

```bash
uvx --python 3.12 --from 'git+https://github.com/Taxuspt/garmin_mcp.git@<reviewed-40-character-commit-sha>' garmin-mcp-auth
```

The upstream tool stores tokens locally under `~/.garminconnect` by default. Do not put `GARMIN_EMAIL` or `GARMIN_PASSWORD` in an agent configuration. Treat the token store like a password.

### Generate a client configuration

The renderer prints configuration; it does not edit global files:

```bash
python scripts/render_garmin_mcp_config.py --revision <reviewed-40-character-commit-sha> --client generic
python scripts/render_garmin_mcp_config.py --revision <reviewed-40-character-commit-sha> --client mcp-json
python scripts/render_garmin_mcp_config.py --revision <reviewed-40-character-commit-sha> --client codex
python scripts/render_garmin_mcp_config.py --revision <reviewed-40-character-commit-sha> --client opencode
```

`mcp-json` emits the common `mcpServers` shape used by several desktop and editor clients. `generic` emits the transport-neutral server record. `opencode` follows the current `mcp.servers` local-server schema in the official [OpenCode MCP documentation](https://opencode.ai/v2/docs/mcp-servers). Register the generated local stdio server using the coding agent's own MCP settings. For Codex, the official [MCP documentation](https://developers.openai.com/codex/mcp/) describes both CLI and `config.toml` registration.

### MCP acquisition sequence

1. Call `get_activities_by_date` with bounded pages until `has_more` is false.
2. Keep cycling subtypes; detect duplicate indoor/outdoor imports and multisport legs.
3. For candidate efforts, call `get_activity`, `get_activity_splits`, and `get_activity_hr_in_timezones`.
4. Call `get_activity_fit_data(..., include_records=true)` for raw timestamped HR and power/cadence when present.
5. Call the derived-metric tools only as metadata. Verify sport provenance, particularly for lactate threshold.
6. Save large tool results to local JSON files and pass those files to `analyze_field_hr.py`.

## Backend B: direct private API CLI

This backend works with any coding agent that can execute a command and read JSON. The main analysis dependencies still support Python 3.10+, but this optional backend is pinned to a `garminconnect` release requiring Python 3.12+.

Install:

```bash
python3.12 -m pip install -r scripts/requirements-garmin-direct.txt
```

Authenticate interactively once:

```bash
python3.12 scripts/fetch_garmin.py auth
```

No email or password command-line flags exist. Subsequent commands load refreshable tokens from `~/.garminconnect`; use `--token-store` to select a different local path and `--cn` for `connect.garmin.cn`.

### Complete inventory

```bash
python3.12 scripts/fetch_garmin.py activities \
  --start-date 2020-01-01 \
  --end-date 2026-09-01 \
  --activity-type cycling \
  --output private/garmin/activities.json
```

Omit `--max-pages` when completeness matters. The JSON explicitly marks `complete: false` if a page cap may have truncated the result.

### Candidate activity bundle

```bash
python3.12 scripts/fetch_garmin.py bundle \
  --activity-id 123456789 \
  --output private/garmin/activity-123456789.json
```

The bundle contains the activity summary, splits, historical time-in-zone result, and full FIT record/lap/session messages. FIT input is accepted whether Garmin returns raw FIT, ZIP, or gzip bytes. No downsampling is performed by this parser.

Individual commands are also available:

```bash
python3.12 scripts/fetch_garmin.py activity --activity-id 123456789
python3.12 scripts/fetch_garmin.py splits --activity-id 123456789
python3.12 scripts/fetch_garmin.py hr-zones --activity-id 123456789
python3.12 scripts/fetch_garmin.py details --activity-id 123456789
python3.12 scripts/fetch_garmin.py fit-json --activity-id 123456789 --output private/garmin/fit.json
python3.12 scripts/fetch_garmin.py fit-download --activity-id 123456789 --output private/garmin/original.zip
```

Fetch configured and derived metadata separately:

```bash
python3.12 scripts/fetch_garmin.py derived --date 2026-09-01 \
  --output private/garmin/derived.json
```

The raw `latestLactateThreshold` payload is deliberately not relabeled as cycling. In practice it is commonly running-derived; cycling use requires an explicit cycling field or other sport provenance.

## Stable exchange contract

Every direct command that returns JSON uses this envelope:

```json
{
  "schema_version": "1.0",
  "kind": "activities",
  "source": {
    "backend": "garmin-connect-private-api",
    "official": false,
    "read_only": true,
    "region": "GLOBAL",
    "retrieved_at_utc": "2026-09-01T00:00:00Z"
  },
  "data": {},
  "caveats": []
}
```

Agents should branch on `schema_version` and `kind`, not on filenames or prose. Raw Garmin response objects are preserved inside `data`; this avoids pretending unstable private fields are a permanent normalized standard.

## Security and privacy checklist

- Ask the user to choose `mcp` or `direct`; do not silently authenticate a new service.
- Keep every retrieval read-only. Never add a write endpoint to the analysis allowlist.
- Never request the user's password in chat or accept it as a CLI flag.
- Do not print bearer/refresh tokens, request headers, full exception URLs, or token file contents.
- Keep token stores and athlete exports outside the Git repository. Confirm `git status` before committing.
- Activity IDs, coordinates, names, dates, device identifiers, and health measurements are private data.
- Use bounded retries and respect `429` responses. Do not increase concurrency to evade Garmin throttling.
- Re-authenticate locally if tokens expire; do not copy tokens into an agent prompt.

## Validation boundary

Unit tests inject a fake transport and synthetic FIT containers. CI never logs into Garmin and therefore proves endpoint construction, pagination, read-only behavior, envelopes, and parsing paths—not continued availability of Garmin's private service. A live smoke test is necessarily opt-in and account-specific.
