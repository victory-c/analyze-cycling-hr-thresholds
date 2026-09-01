import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_garmin as garmin


class FakeTransport:
    def __init__(self, responses=None, download=b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT"):
        self.responses = list(responses or [])
        self.download_payload = download
        self.calls = []

    def connectapi(self, path, **kwargs):
        self.calls.append(("get", path, kwargs))
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return {}

    def download(self, path, **kwargs):
        self.calls.append(("download", path, kwargs))
        return self.download_payload


class DirectBackendTests(unittest.TestCase):
    def test_activity_inventory_paginates_until_partial_page(self):
        transport = FakeTransport(responses=[[{"activityId": 1}, {"activityId": 2}], [{"activityId": 3}]])
        result = garmin.DirectGarminBackend(transport).activities(
            start_date="2026-01-01",
            end_date="2026-08-31",
            activity_type="cycling",
            page_size=2,
        )
        self.assertEqual(result["count"], 3)
        self.assertTrue(result["complete"])
        self.assertEqual(transport.calls[0][2]["params"]["start"], "0")
        self.assertEqual(transport.calls[1][2]["params"]["start"], "2")
        self.assertEqual(transport.calls[0][2]["params"]["activityType"], "cycling")

    def test_page_cap_is_disclosed_as_incomplete(self):
        transport = FakeTransport(responses=[[{"activityId": 1}]])
        result = garmin.DirectGarminBackend(transport).activities(
            start_date="2026-01-01",
            end_date="2026-01-31",
            page_size=1,
            max_pages=1,
        )
        self.assertFalse(result["complete"])

    def test_explicit_read_only_endpoints(self):
        transport = FakeTransport(responses=[{}, {}, {}, {}])
        backend = garmin.DirectGarminBackend(transport)
        backend.activity(42)
        backend.splits(42)
        backend.hr_time_in_zones(42)
        backend.details(42, max_chart_size=5000, max_polyline_size=0)
        paths = [call[1] for call in transport.calls]
        self.assertEqual(
            paths,
            [
                "/activity-service/activity/42",
                "/activity-service/activity/42/splits",
                "/activity-service/activity/42/hrTimeInZones",
                "/activity-service/activity/42/details",
            ],
        )
        self.assertTrue(all(call[0] == "get" for call in transport.calls))

    def test_derived_metrics_preserve_partial_failures(self):
        transport = FakeTransport(
            responses=[
                {"userData": {"displayName": "athlete"}},
                {"zones": []},
                RuntimeError("not available"),
                [],
                {},
                {},
                {"allMetrics": {}},
            ]
        )
        data = garmin.DirectGarminBackend(transport).derived_metrics("2026-08-31")
        self.assertEqual(data["cycling_ftp"]["error"], "RuntimeError")
        self.assertIn("running-derived", data["sport_warning"])
        self.assertIn("resting_heart_rate", data)
        self.assertEqual(len(transport.calls), 7)
        self.assertEqual(
            transport.calls[-1][1], "/userstats-service/wellness/daily/athlete"
        )

    def test_fit_download_uses_original_activity_endpoint(self):
        transport = FakeTransport(download=b"payload")
        payload = garmin.DirectGarminBackend(transport).fit_bytes(99)
        self.assertEqual(payload, b"payload")
        self.assertEqual(
            transport.calls,
            [("download", "/download-service/files/activity/99", {})],
        )


class ContractTests(unittest.TestCase):
    def test_envelope_identifies_unofficial_backend(self):
        payload = garmin.envelope("activities", {"activities": []})
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertFalse(payload["source"]["official"])
        self.assertTrue(payload["source"]["read_only"])
        self.assertIn("not independent", payload["caveats"][1])

    def test_zip_fit_payload_is_extracted(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("activity.fit", b"raw-fit")
        extracted, detected = garmin.extract_fit_bytes(buffer.getvalue())
        self.assertEqual(extracted, b"raw-fit")
        self.assertEqual(detected, "zip")

    def test_json_writer_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "result.json"
            garmin._write_json({"ok": True}, output)
            self.assertEqual(json.loads(output.read_text()), {"ok": True})

    def test_parser_has_no_password_option(self):
        help_text = garmin.build_parser().format_help()
        self.assertNotIn("--password", help_text)
        self.assertNotIn("--email", help_text)


if __name__ == "__main__":
    unittest.main()
