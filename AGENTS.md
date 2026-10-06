# Coding agent instructions

Read and follow `SKILL.md` as the canonical analysis workflow.

For Garmin acquisition, ask the user to choose either the configured `Taxuspt/garmin_mcp` MCP backend or the read-only `scripts/fetch_garmin.py` direct backend. Follow `references/garmin-data-sources.md` and `references/coding-agent-integration.md`. These backends are alternate transports for one Garmin source, not independent physiological evidence. Never perform Garmin writes or commit private athlete data, credentials, tokens, activity IDs, or raw exports.
