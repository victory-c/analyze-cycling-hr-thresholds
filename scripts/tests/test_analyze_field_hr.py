from datetime import datetime, timedelta, timezone
import gzip
import importlib.util
from io import BytesIO
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_field_hr import (
    best_window,
    extract_points,
    interpolate_seconds,
    inventory_activity_list,
    summarize_file,
    unwrap,
)

HAS_FIT_SDK = importlib.util.find_spec("garmin_fit_sdk") is not None
START = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)


def fit_bytes(legs):
    """Encode a FIT activity with one session per (sport, first_second, heart_rates) leg."""
    from garmin_fit_sdk import Encoder, Profile

    mesg_num = Profile["mesg_num"]
    encoder = Encoder()
    encoder.write_mesg({"mesg_num": mesg_num["FILE_ID"], "type": "activity", "manufacturer": "development", "time_created": START})
    for sport, first_second, heart_rates in legs:
        for offset, heart_rate in enumerate(heart_rates):
            moment = START + timedelta(seconds=first_second + offset)
            encoder.write_mesg({"mesg_num": mesg_num["RECORD"], "timestamp": moment, "heart_rate": heart_rate})
        encoder.write_mesg(
            {
                "mesg_num": mesg_num["SESSION"],
                "timestamp": START + timedelta(seconds=first_second + len(heart_rates) - 1),
                "start_time": START + timedelta(seconds=first_second),
                "total_elapsed_time": float(len(heart_rates) - 1),
                "sport": sport,
            }
        )
    return encoder.close()


class FieldAnalysisTests(unittest.TestCase):
    def test_unwraps_mcp_envelope(self):
        wrapped = {"structuredContent": {"result": {"records": [{"timestamp": 1, "heartRate": 100}]}}}
        self.assertIn("records", unwrap(wrapped))

    def test_extracts_and_normalizes_points(self):
        payload = {
            "records": [
                {"timestamp": "2026-01-01T00:00:01Z", "heartRate": 101},
                {"timestamp": "2026-01-01T00:00:03Z", "heartRate": 103},
            ]
        }
        self.assertEqual(extract_points(payload), [(0.0, 101.0), (2.0, 103.0)])

    def test_extracts_strava_mcp_parallel_streams(self):
        payload = {"heart_rate": [144, 168, 189], "time": [10, 11, 13], "moving": [False, True, True]}
        self.assertEqual(extract_points(payload), [(0.0, 144.0), (1.0, 168.0), (3.0, 189.0)])

    def test_extracts_streams_from_mcp_text_content(self):
        streams = {"time": [0, 1], "heart_rate": [120, 121]}
        wrapped = {"content": [{"type": "text", "text": json.dumps(streams)}]}
        self.assertEqual(extract_points(wrapped), [(0.0, 120.0), (1.0, 121.0)])

    def test_rejects_misaligned_streams(self):
        self.assertEqual(extract_points({"time": [0, 1, 2], "heart_rate": [120, 121]}), [])

    def test_inventories_strava_activity_list(self):
        activities = {"activities": [{"id": "1", "sport_type": "Ride"}, {"id": "2", "sport_type": "WeightTraining"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activities.json"
            path.write_text(json.dumps(activities), encoding="utf-8")
            result = inventory_activity_list(path)
        self.assertEqual(result["sports"], {"Ride": 1, "WeightTraining": 1})

    def test_extracts_intervals_icu_stream_list(self):
        payload = [
            {"type": "time", "data": [0, 1, 2]},
            {"type": "heartrate", "data": [140, None, 142]},
            {"type": "watts", "data": [200, 210, 205]},
        ]
        self.assertEqual(extract_points(payload), [(0.0, 140.0), (2.0, 142.0)])

    def test_extracts_strava_rest_key_by_type_streams(self):
        payload = {"time": {"data": [0, 1]}, "heartrate": {"data": [120, 121]}}
        self.assertEqual(extract_points(payload), [(0.0, 120.0), (1.0, 121.0)])

    def test_inventories_intervals_icu_activity_list(self):
        activities = [
            {"id": "i1", "type": "Ride", "has_heartrate": True, "device_watts": True, "source": "GARMIN_CONNECT"},
            {"id": "i2", "type": "Ride", "has_heartrate": True, "device_watts": False, "source": "GARMIN_CONNECT"},
            {"id": "i3", "type": "Ride", "source": "STRAVA"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activities.json"
            path.write_text(json.dumps(activities), encoding="utf-8")
            result = inventory_activity_list(path)
        self.assertEqual(result["activities_with_summary_hr"], 2)
        self.assertEqual(result["activities_with_summary_power"], 1)
        self.assertEqual(result["strava_sourced_stubs"], 1)

    def test_reports_unsupported_file_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ride.gpx"
            path.write_text("<gpx></gpx>", encoding="utf-8")
            result = summarize_file(path, [], max_gap=12)
        self.assertIn("unsupported file format", result["error"])

    def test_interpolation_does_not_bridge_long_gap(self):
        runs = interpolate_seconds([(0.0, 100.0), (2.0, 102.0), (20.0, 140.0)], max_gap=5)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], [100.0, 101.0, 102.0])

    def test_best_window(self):
        result = best_window([[100.0] * 10 + [150.0] * 10], seconds=10)
        self.assertEqual(result["mean_bpm"], 150.0)
        self.assertEqual(result["start_second"], 10)


@unittest.skipUnless(HAS_FIT_SDK, "garmin-fit-sdk is not installed")
class FitFileTests(unittest.TestCase):
    def summarize(self, name, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / name
            path.write_bytes(data)
            return summarize_file(path, [], max_gap=12)

    def test_decodes_cycling_fit(self):
        result = self.summarize("ride.fit", fit_bytes([("cycling", 0, [140, 141, 142, 143, 144])]))
        self.assertEqual(result["input_format"], "fit")
        self.assertEqual(result["fit_sessions"], [{"sport": "cycling", "sub_sport": None}])
        self.assertEqual(result["raw_hr_samples"], 5)
        self.assertEqual(result["hr_max_bpm"], 144.0)

    def test_multisport_fit_keeps_only_cycling_records(self):
        data = fit_bytes([("running", 0, [170, 171, 172]), ("cycling", 10, [140, 141, 142])])
        result = self.summarize("brick.fit", data)
        self.assertEqual(result["raw_hr_samples"], 3)
        self.assertEqual(result["hr_max_bpm"], 142.0)

    def test_rejects_fit_without_cycling_session(self):
        result = self.summarize("run.fit", fit_bytes([("running", 0, [150, 151, 152])]))
        self.assertEqual(result["error"], "FIT file has no cycling session (found: running)")

    def test_keeps_generic_sport_fit_with_warning(self):
        result = self.summarize("magene.fit", fit_bytes([("generic", 0, [140, 141, 142])]))
        self.assertEqual(result["raw_hr_samples"], 3)
        self.assertIn("sport_warning", result)

    def test_reads_gzip_and_zip_wrapped_fit(self):
        data = fit_bytes([("cycling", 0, [140, 141, 142])])
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("12345_ACTIVITY.fit", data)
        for name, wrapped in (("ride.fit.gz", gzip.compress(data)), ("export.zip", archive.getvalue())):
            with self.subTest(name=name):
                self.assertEqual(self.summarize(name, wrapped)["raw_hr_samples"], 3)

    def test_keeps_records_from_truncated_fit_with_warning(self):
        data = fit_bytes([("cycling", 0, [140, 141, 142, 143, 144])])
        result = self.summarize("crashed.fit", data[:-20])
        self.assertEqual(result["raw_hr_samples"], 5)
        self.assertIn("fit_decode_warnings", result)


if __name__ == "__main__":
    unittest.main()
