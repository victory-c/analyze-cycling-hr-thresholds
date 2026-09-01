import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_cpet import (  # noqa: E402
    align_hr,
    classified_threshold_power_candidates,
    detect_thresholds,
    elapsed_seconds,
    excel_column_index,
    regularize,
)


class CpetAnalysisTests(unittest.TestCase):
    def test_excel_column_and_time_parsing(self):
        self.assertEqual(excel_column_index("A"), 0)
        self.assertEqual(excel_column_index("J"), 9)
        self.assertEqual(excel_column_index("AA"), 26)
        self.assertEqual(elapsed_seconds("01:02:03.5"), 3723.5)

    def test_regularize_and_candidate_detection(self):
        seconds = np.arange(0, 601, 2, dtype=float)
        vo2 = 500 + 4 * seconds
        vco2 = np.where(seconds < 300, 0.8 * vo2, 0.8 * (500 + 4 * 300) + 1.15 * (vo2 - (500 + 4 * 300)))
        ve = 10 + 0.02 * vco2 + np.maximum(seconds - 450, 0) * 0.20
        raw = pd.DataFrame(
            {
                "time": seconds,
                "hr": 90 + 0.14 * seconds,
                "vo2": vo2,
                "vco2": vco2,
                "ve": ve,
                "ve_vo2": 30 - 0.02 * np.minimum(seconds, 300) + 0.025 * np.maximum(seconds - 300, 0),
                "ve_vco2": 34 - 0.01 * np.minimum(seconds, 450) + 0.04 * np.maximum(seconds - 450, 0),
                "peto2": 110 - 0.02 * np.minimum(seconds, 300) + 0.02 * np.maximum(seconds - 300, 0),
                "petco2": 35 + 0.01 * np.minimum(seconds, 450) - 0.03 * np.maximum(seconds - 450, 0),
            }
        )
        regular = regularize(raw)
        self.assertEqual(len(regular), 601)
        result = detect_thresholds(regular, smooth_seconds=20, start=0, end=600)
        self.assertIsNotNone(result["vt1_consensus_candidate_seconds"])
        self.assertIsNotNone(result["rcp_consensus_candidate_seconds"])

    def test_hr_clock_alignment(self):
        index = np.arange(0, 300)
        cart = pd.DataFrame({"hr": 120 + 15 * np.sin(index / 25)}, index=index)
        ergo = pd.DataFrame({"hr": 120 + 15 * np.sin((index - 7) / 25)}, index=index)
        result = align_hr(cart, ergo, max_lag=20)
        self.assertEqual(result["ergometer_time_minus_cart_time_seconds"], 7)
        self.assertGreater(result["correlation"], 0.99)

    def test_threshold_power_candidates_remain_classified(self):
        ergometer = pd.DataFrame(
            {"hr": np.arange(100, 201), "power": np.arange(150, 251), "cadence": 85},
            index=np.arange(0, 101),
        )
        sensitivity = [
            {
                "smoothing_seconds": 20,
                "vt1_consensus_candidate_seconds": 20,
                "rcp_consensus_candidate_seconds": 70,
            },
            {
                "smoothing_seconds": 30,
                "vt1_consensus_candidate_seconds": 22,
                "rcp_consensus_candidate_seconds": 72,
            },
        ]
        result = classified_threshold_power_candidates(ergometer, sensitivity, lag=5)
        self.assertEqual(result["vt1"]["candidate_power_values_w"], [175.0, 177.0])
        self.assertEqual(result["rcp"]["candidate_power_values_w"], [225.0, 227.0])
        self.assertEqual(result["rcp"]["central_power_w"], 226.0)


if __name__ == "__main__":
    unittest.main()
