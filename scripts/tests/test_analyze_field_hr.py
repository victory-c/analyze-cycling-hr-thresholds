import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_field_hr import best_window, extract_points, interpolate_seconds, inventory_activity_list, unwrap


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

    def test_interpolation_does_not_bridge_long_gap(self):
        runs = interpolate_seconds([(0.0, 100.0), (2.0, 102.0), (20.0, 140.0)], max_gap=5)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], [100.0, 101.0, 102.0])

    def test_best_window(self):
        result = best_window([[100.0] * 10 + [150.0] * 10], seconds=10)
        self.assertEqual(result["mean_bpm"], 150.0)
        self.assertEqual(result["start_second"], 10)


if __name__ == "__main__":
    unittest.main()
