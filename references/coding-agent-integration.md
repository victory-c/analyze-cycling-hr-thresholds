# Coding-agent integration

The analysis method and Python tools are agent-neutral. `SKILL.md` is the canonical workflow, while this file explains how any coding agent can supply Garmin data.

## Capability decision

1. If the agent supports local MCP servers and the user chooses MCP, register `Taxuspt/garmin_mcp` as a local stdio server.
2. If MCP is unavailable, disabled, or undesired, run `scripts/fetch_garmin.py` and read its JSON files.
3. If the agent cannot run local commands, ask the user to run the direct CLI and attach the JSON/FIT exports.
4. If the user has an approved Garmin Developer Program integration, build a separate official adapter against its documented OAuth 2.0 API; do not route those credentials through the private backend.

This keeps the physiological analysis unchanged across Codex, Claude Code/Desktop, Cursor, Cline, OpenCode, IDE agents, CI workers, and ordinary shells.

## Portable agent prompt

```text
Read SKILL.md and follow it as the analysis contract. Ask me to choose one
Garmin acquisition backend: (a) the configured garmin_mcp tools, or (b) the
read-only scripts/fetch_garmin.py CLI. Treat these as alternate transports for
one Garmin source, never as independent evidence. Inventory the complete
cycling history with pagination, inspect raw FIT records for candidate efforts,
keep all athlete exports private, then analyze Garmin and CPET independently
before reconciliation. Do not perform Garmin writes.
```

## MCP clients

All MCP clients need the same server process:

```text
transport: stdio
command: uvx
args: --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp.git@<reviewed-40-character-commit-sha> garmin-mcp
```

Generate the surrounding client-specific shape with:

```bash
python scripts/render_garmin_mcp_config.py --revision <reviewed-40-character-commit-sha> --client generic
```

The `mcp-json`, `codex`, and `opencode` render targets are conveniences. For any other agent, translate only the outer configuration syntax; keep the command, arguments, read-only tool allowlist, and absence of passwords unchanged.

## CLI-only agents

CLI-only agents should treat `scripts/fetch_garmin.py` as a local data provider:

```text
inventory -> activities JSON -> candidate selection
candidate ID -> bundle JSON -> analyze_field_hr.py
derived JSON -> metadata audit only
CPET raw files -> analyze_cpet.py
independent conclusions -> reconciliation -> zones/report
```

Do not make agent-specific branches inside the threshold algorithms. Backend selection ends at the JSON/FIT boundary.

## Repository instructions

Agents that honor `AGENTS.md` get a short pointer to the same contract. Agents with their own project-rule format should be told to read `AGENTS.md` and `SKILL.md`; copying the full method into several vendor files invites drift.
