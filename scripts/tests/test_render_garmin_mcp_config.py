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
        self.assertFalse(any(name.startswith(("delete_", "upload_", "create_", "set_")) for name in allowlist))

    def test_mcp_json_wraps_server(self):
        config = json.loads(render("mcp-json", "source"))
        self.assertIn("garmin", config["mcpServers"])

    def test_opencode_uses_command_array(self):
        config = json.loads(render("opencode", "source", is_cn=True))
        server = config["mcp"]["servers"]["garmin"]
        self.assertEqual(server["command"][0], "uvx")
        self.assertEqual(server["environment"]["GARMIN_IS_CN"], "true")

    def test_codex_output_is_toml_shaped(self):
        rendered = render("codex", "source")
        self.assertIn("[mcp_servers.garmin]", rendered)
        self.assertIn('command = "uvx"', rendered)
        self.assertNotIn("GARMIN_PASSWORD", rendered)


if __name__ == "__main__":
    unittest.main()
