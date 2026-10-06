# Client and source routing

## Discover capabilities before using tools

The skill works in Claude and Codex. Its common contract is Markdown instructions
and Python scripts, not a particular tool prefix or SDK. Inspect the tools
actually exposed in the active session and their argument/return schemas.
Use the client's tool search or MCP tool listing when provided. Do not copy a
tool name from another client and assume it is callable here.

Record which of these capabilities are available for the user's question:

| Capability | Suitable evidence and limitations |
|---|---|
| Cycling activity listing | A bounded date range with pagination and duplicate detection |
| Timestamped HR and power | Raw records with units, coverage, time basis and pause information |
| Activity summaries only | Candidate screening; insufficient for sustained-window estimates or reslicing |
| Profile or configured zones | Settings to audit, not independently measured thresholds |
| Raw CPET files | Separate laboratory evidence; no connected account required |
| Garmin zone writes | Optional, only when the user requests them and a real write tool exists |

Prefer the best original record for each ride. Garmin and Strava often contain
the same recording. Label origin and recording device separately and do not
count synchronized copies as repeat field tests. Estimated power is not measured
power. A device model does not prove the HR sensor was a chest strap.

## Source paths

**Garmin MCP:** Discover activity, stream/FIT, weather and profile tools. Module
versions differ; tools such as `get_activity_streams` or `analyze_decoupling`
are examples to look for, not guaranteed dependencies. Follow all pages,
preserve raw timestamps and timer events, and inspect returned QC/warnings.
The repository's supported Garmin backends (the read-only `garmin_mcp` allowlist
and the direct CLI) are described in [garmin-data-sources.md](garmin-data-sources.md).

**Official Strava MCP:** Connect directly to `https://mcp.strava.com/mcp` in the
client. Discover its actual tools after OAuth and any eligibility check. It is
currently read-only and subscriber access is subject to rollout. Do not invent
a stream endpoint from the REST API documentation or promise high-resolution
power/HR before seeing the available schema. Use summaries as summaries. When
data quality is insufficient, continue with original Garmin data or a local file
the user supplies. Do not turn this skill into an API proxy or share OAuth tokens
between clients.

Observed after successful Claude Code OAuth on September 6, 2026: the official
server advertised 11 tools, including a tool displayed as Check Eligibility
and `get_activity_streams`. The latter's inspected schema required
`activity_id` as a string and `streams` as an array. Confirmed stream names
included `time` (elapsed seconds), `heart_rate` (bpm), and `watts`. Its optional
`resolution` was a positive integer, with omission requesting maximum granularity
according to the tool description. Unknown stream names were silently ignored
and missing streams omitted. Reinspect the live schema before use; check which
streams actually returned and their alignment, coverage, and units. Tool
discovery alone did not validate activity access or the returned stream shape.

A live read on October 4, 2026 returned parallel arrays such as
`{"time": [...], "heart_rate": [...], "moving": [...]}`; a ride recorded without
a power meter returned no `watts`. Save the full-resolution result to private
storage and pass it to the field helper; omit `resolution`, because downsampled
streams leave gaps the helper deliberately will not bridge.

**intervals.icu:** No official MCP server was found. Community MCP servers and the
REST API both use the athlete's own API key (Basic auth with username `API_KEY`),
which the account holder configures; never request it in chat. Fetch
`/api/v1/activity/{id}/streams.json?types=time,heartrate,watts` or the original
file from `/api/v1/activity/{id}/file`. Activities that intervals.icu imported
from Strava are returned as empty stubs, so they cannot replace the Strava MCP or
original device files.

**Local files:** The field helper (`scripts/analyze_field_hr.py --activity`) reads
original FIT files (raw, Strava bulk-export `.fit.gz`, or Garmin `.zip`), JSON
record lists with explicit timestamps and HR, and JSON stream arrays from the
Strava MCP, intervals.icu, or the Strava REST API. A minimal record list:

```json
{"records": [{"timestamp": 0, "heart_rate": 110}, {"timestamp": 1, "heart_rate": 111}]}
```

`timestamp` is ISO-8601 or numeric seconds; HR is bpm. See
[activity inputs](garmin-data-workflow.md#activity-inputs-for-the-field-helper)
for each source. The helper does not read GPX or TCX; convert those with an
appropriate decoder first, retaining units, missingness, provenance and pause
boundaries. Export separately per continuous effort if timer events would
otherwise be lost. It can unwrap common JSON MCP envelopes, but validate the
actual extracted sample count; conversational summaries are not raw records.
Keep account data and intermediate exports in private working storage. CPET XLSX
uses the existing CPET helper and quality workflow.

## Claude and Codex discovery

Personal skill locations for the same complete skill folder:

- Codex: `~/.codex/skills/analyze-cycling-hr-thresholds/` (or the configured Codex home).
- Claude Code: `~/.claude/skills/analyze-cycling-hr-thresholds/`.

Keep a canonical copy and update the other copy deliberately, or use a symlink
where the client supports it. Do not overwrite an existing divergent skill.
`agents/openai.yaml` is optional Codex UI metadata, not a dependency for Claude.
Resolve helper and reference paths from the installed skill's directory.

In Codex, invoke `$analyze-cycling-hr-thresholds`; in Claude Code, invoke
`/analyze-cycling-hr-thresholds`. Natural-language selection also depends on the
client loading the skill. For Claude web/desktop custom skills, upload a ZIP
containing the skill folder through the client's skills UI when available;
uploading the skill does not connect an MCP or provide local filesystem access.

## Connection setup and diagnosis (only when needed)

Check existing entries before adding a server under another name. Respect the
user's chosen client; setting up one client does not automatically authorize
changing the other client's configuration.

Codex:

```sh
codex mcp get strava --json
codex mcp add strava --url https://mcp.strava.com/mcp
codex mcp login strava
```

Claude Code (the scope below is an example for personal configuration):

```sh
claude mcp get strava-mcp
claude mcp add --scope user --transport http strava-mcp https://mcp.strava.com/mcp
```

Then use `/mcp` inside Claude Code to authenticate. Claude web/desktop also has
the Strava connector under Customize → Connectors. OAuth consent must be
completed by the account holder; do not request passwords or tokens in chat.

Distinguish configured, authenticated, tools discovered, eligible, and successful
read. Check a small read-only request before calling a connection usable.

On September 6, 2026, Codex CLI 0.147.0 failed before consent with an issuer
mismatch. Strava's public protected-resource metadata advertised
`https://www.strava.com/mcp-issuer`, while that server's discovery document
returned issuer `https://www.strava.com`. This is an observed compatibility
failure, not proof of an account restriction or permanent client exclusivity.
Recheck with `python scripts/check_strava_oauth.py`; it reads only public
discovery documents and cannot authenticate or establish account eligibility.
Use the current native login command after metadata or client fixes. Do not
disable issuer/TLS checks, spoof another client's identity, or reuse its tokens.
If the mismatch persists, report the exact failing stage and continue any
available local or Garmin analysis. Do not substitute an unofficial API wrapper.

## Official references

- [Strava connector and client support](https://support.strava.com/en-us/articles/15401531-strava-mcp-connector)
- [Strava API and MCP policy](https://www.strava.com/legal/api_policy)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude custom skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
