import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_garmin_mcp_config import ANALYSIS_TOOLS, render


class McpConfigTests(unittest.TestCase):
    def test_generic_config_is_stdio_and_has_read_only_analysis_allowlist(self):
        config = json.loads(render("generic", "git+https://example.test/garmin_mcp"))
        self.assertEqual(config["transport"], "stdio")
        self.assertEqual(config["command"], "uvx")
        allowlist = config["env"]["GARMIN_ENABLED_TOOLS"].split(",")
        self.assertEqual(tuple(allowlist), ANALYSIS_TOOLS)
        # Read-only is the property that matters, and garmin_mcp's write tools
        # are not all prefix-shaped (add_weigh_in, log_food, schedule_workout,
        # upsert_and_log). Requiring get_* is what actually holds the line.
        for name in allowlist:
            self.assertTrue(name.startswith("get_"), f"non-read tool in allowlist: {name}")
        self.assertNotIn("", allowlist)

    def test_mcp_json_wraps_server(self):
        config = json.loads(render("mcp-json", "source"))
        self.assertIn("garmin", config["mcpServers"])
        server = config["mcpServers"]["garmin"]
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["env"]["GARMIN_ENABLED_TOOLS"].split(","), list(ANALYSIS_TOOLS)
        )

    def test_every_client_shape_carries_the_allowlist(self):
        """No supported client may be rendered without the read-only allowlist."""
        joined = ",".join(ANALYSIS_TOOLS)
        for client in ("generic", "mcp-json", "codex", "opencode"):
            with self.subTest(client=client):
                self.assertIn(joined, render(client, "source"))

    def test_opencode_uses_command_array(self):
        config = json.loads(render("opencode", "source", is_cn=True))
        server = config["mcp"]["servers"]["garmin"]
        self.assertEqual(server["command"][0], "uvx")
        self.assertEqual(server["environment"]["GARMIN_IS_CN"], "true")

    def test_codex_output_is_toml_shaped(self):
        rendered = render("codex", "source")
        self.assertIn("[mcp_servers.garmin]", rendered)
        self.assertIn('command = "uvx"', rendered)
        # Assert the env table is actually emitted, rather than asserting the
        # absence of a string the module can never produce.
        self.assertIn("GARMIN_ENABLED_TOOLS", rendered)
        multi = render("codex", "source", is_cn=True)
        self.assertIn('GARMIN_IS_CN = "true"', multi)


if __name__ == "__main__":
    unittest.main()
