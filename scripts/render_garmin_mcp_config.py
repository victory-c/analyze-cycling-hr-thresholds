#!/usr/bin/env python3
"""Render a minimal garmin_mcp stdio configuration for common MCP clients."""

from __future__ import annotations

import argparse
import json
import re

REPOSITORY = "git+https://github.com/Taxuspt/garmin_mcp.git"
ANALYSIS_TOOLS = (
    "get_activities_by_date",
    "get_activities",
    "get_activity",
    "get_activity_splits",
    "get_activity_hr_in_timezones",
    "get_activity_fit_data",
    "get_cycling_ftp",
    "get_lactate_threshold",
    "get_training_status",
    "get_user_profile",
    "get_userprofile_settings",
)


def server(source: str, *, is_cn: bool = False) -> dict:
    env = {"GARMIN_ENABLED_TOOLS": ",".join(ANALYSIS_TOOLS)}
    if is_cn:
        env["GARMIN_IS_CN"] = "true"
    return {
        "command": "uvx",
        "args": ["--python", "3.12", "--from", source, "garmin-mcp"],
        "env": env,
    }


def render(client: str, source: str, *, is_cn: bool = False) -> str:
    config = server(source, is_cn=is_cn)
    if client == "codex":
        args = ",\n  ".join(json.dumps(item) for item in config["args"])
        env = ", ".join(
            f"{key} = {json.dumps(value)}" for key, value in config["env"].items()
        )
        return (
            "[mcp_servers.garmin]\n"
            f"command = {json.dumps(config['command'])}\n"
            f"args = [\n  {args}\n]\n"
            f"env = {{ {env} }}\n"
        )
    if client == "opencode":
        return json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {
                    "servers": {
                        "garmin": {
                            "type": "local",
                            "command": [config["command"], *config["args"]],
                            "environment": config["env"],
                        }
                    }
                },
            },
            indent=2,
        ) + "\n"
    if client == "mcp-json":
        return json.dumps({"mcpServers": {"garmin": config}}, indent=2) + "\n"
    if client == "generic":
        return json.dumps(
            {"name": "garmin", "transport": "stdio", **config}, indent=2
        ) + "\n"
    raise ValueError(f"unsupported client: {client}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client",
        choices=("generic", "mcp-json", "codex", "opencode"),
        default="generic",
    )
    parser.add_argument(
        "--revision",
        required=True,
        help="reviewed full 40-character garmin_mcp commit SHA",
    )
    parser.add_argument("--cn", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.revision):
        parser.error("--revision must be a full 40-character commit SHA")
    source = f"{REPOSITORY}@{args.revision.lower()}"
    print(render(args.client, source, is_cn=args.cn), end="")


if __name__ == "__main__":
    main()
