import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_field_hr import best_window, extract_points, interpolate_seconds, unwrap


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
