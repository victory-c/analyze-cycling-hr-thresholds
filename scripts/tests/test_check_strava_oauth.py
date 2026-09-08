import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_strava_oauth import ADVERTISED_SERVER, RESOURCE, classify


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.resource = {"resource": RESOURCE,
                         "authorization_servers": [ADVERTISED_SERVER]}
        self.server = {
            "issuer": ADVERTISED_SERVER,
            "authorization_endpoint": "https://www.strava.com/oauth/mcp/authorize",
            "token_endpoint": "https://www.strava.com/oauth/mcp/token",
        }

    def test_reproduced_same_origin_mismatch_is_not_accepted(self):
        self.server["issuer"] = "https://www.strava.com"
        result = classify(self.resource, self.server)
        self.assertEqual(result["status"], "issuer_mismatch")
        self.assertFalse(result["authenticated"])

    def test_consistency_does_not_imply_authenticated_or_eligible(self):
        result = classify(self.resource, self.server)
        self.assertEqual(result["status"], "metadata_consistent_login_not_verified")
        self.assertFalse(result["authenticated"])
        self.assertFalse(result["tools_discovered"])
        self.assertEqual(result["account_eligibility"], "not_checked")

    def test_changed_discovery_does_not_compare_stale_document(self):
        self.resource["authorization_servers"] = ["https://www.strava.com"]
        self.assertEqual(classify(self.resource, self.server)["status"],
                         "discovery_changed_reinspect_official_metadata")

    def test_unexpected_resource_is_rejected(self):
        self.resource["resource"] = "https://example.com/mcp"
        self.assertEqual(classify(self.resource, self.server)["status"],
                         "unexpected_resource")

    def test_missing_issuer_is_not_a_success(self):
        self.server.pop("issuer")
        self.assertEqual(classify(self.resource, self.server)["status"], "missing_issuer")

    def test_http_or_other_host_endpoint_requires_review(self):
        # Both endpoints are checked, not just token_endpoint: a hostile
        # authorization_endpoint is what would actually send the user to an
        # attacker's login page.
        for field in ("token_endpoint", "authorization_endpoint"):
            for url in ("http://www.strava.com/token", "https://example.com/token"):
                with self.subTest(field=field, url=url):
                    server = dict(self.server)
                    server[field] = url
                    self.assertEqual(classify(self.resource, server)["status"],
                                     "endpoint_changed_reinspect")

    def test_non_string_endpoint_is_reported_not_raised(self):
        # urlsplit() on a list raises TypeError, which main() does not catch,
        # so the guard here is what keeps a hostile document from replacing the
        # JSON report with a traceback.
        for field in ("token_endpoint", "authorization_endpoint"):
            with self.subTest(field=field):
                server = dict(self.server)
                server[field] = ["https://www.strava.com/oauth/mcp/token"]
                result = classify(self.resource, server)
                self.assertEqual(result["status"], "missing_endpoint")
                self.assertEqual(result["field"], field)


if __name__ == "__main__":
    unittest.main()
