import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from estimate_ftp_without_power_meter import climb_power, critical_power, lab_proxy  # noqa: E402


class FtpProxyTests(unittest.TestCase):
    def test_lab_proxy_uses_candidate_spread_and_instrument_error(self):
        result = lab_proxy([250, 258, 263], instrument_error_pct=2, high_end_valid=True)
        self.assertEqual(result["central_power_w"], 258.0)
        self.assertEqual(result["measurement_range_w"], [245.0, 268.3])

    def test_lab_proxy_is_withheld_without_high_end_confirmation(self):
        result = lab_proxy([250, 258, 263], instrument_error_pct=2, high_end_valid=False)
        self.assertIsNone(result["ftp_proxy_candidate_w"])

    def test_long_maximal_climb_is_eligible_proxy(self):
        result = climb_power(
            system_mass_kg=82,
            distance_m=10000,
            elevation_gain_m=700,
            duration_s=3000,
            cda_m2=0.32,
            crr=0.005,
            air_density=1.18,
            headwind_mps=0,
            drivetrain_efficiency=0.975,
            maximal_steady=True,
        )
        self.assertAlmostEqual(result["estimated_crank_power_w"], 213.3, places=1)
        self.assertEqual(result["ftp_proxy_candidate_w"], 213.3)

    def test_short_climb_is_not_auto_converted(self):
        result = climb_power(82, 5000, 400, 1200, 0.32, 0.005, 1.18, 0, 0.975, True)
        self.assertIsNone(result["ftp_proxy_candidate_w"])

    def test_critical_power_fit_recovers_known_parameters(self):
        cp, w_prime = 250.0, 15000.0
        efforts = [(duration, cp + w_prime / duration) for duration in (180, 420, 720)]
        result = critical_power(efforts)
        self.assertAlmostEqual(result["critical_power_w"], cp, places=1)
        self.assertAlmostEqual(result["w_prime_j"], w_prime, places=1)
        self.assertEqual(result["r_squared"], 1.0)

    def test_critical_power_requires_duration_spread(self):
        with self.assertRaises(ValueError):
            critical_power([(300, 300), (330, 295), (360, 290)])


if __name__ == "__main__":
    unittest.main()
