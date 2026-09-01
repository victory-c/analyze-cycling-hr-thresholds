import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calculate_hr_zones import build_zones


class ZoneCalculationTests(unittest.TestCase):
    def test_expected_dual_threshold_boundaries(self):
        result = build_zones(vt1=150, lthr=188, max_hr=204)
        pairs = [(zone["lower_bpm"], zone["upper_bpm"]) for zone in result["zones"]]
        self.assertEqual(pairs, [(None, 135), (136, 149), (150, 169), (170, 187), (188, 204)])
        self.assertEqual(
            result["garmin_custom_lower_boundaries_bpm"],
            {"Z2": 136, "Z3": 150, "Z4": 170, "Z5": 188},
        )

    def test_open_ended_zone_five(self):
        result = build_zones(vt1=145, lthr=180)
        self.assertIsNone(result["zones"][-1]["upper_bpm"])

    def test_rejects_invalid_anchor_order(self):
        with self.assertRaises(ValueError):
            build_zones(vt1=185, lthr=180)


if __name__ == "__main__":
    unittest.main()
