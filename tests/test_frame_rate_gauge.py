import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import frame_rate_percent, gauge_color_rgb


class FrameRateGaugeTests(unittest.TestCase):
    def test_frame_rate_percent_scales_to_target_fps(self):
        self.assertEqual(frame_rate_percent(30, target_fps=60), 50)
        self.assertEqual(frame_rate_percent(60, target_fps=60), 100)

    def test_frame_rate_percent_clamps_out_of_range_values(self):
        self.assertEqual(frame_rate_percent(-10, target_fps=60), 0)
        self.assertEqual(frame_rate_percent(240, target_fps=60), 100)
        self.assertEqual(frame_rate_percent(60, target_fps=0), 0)

    def test_frame_rate_gauge_treats_high_fps_as_good(self):
        self.assertEqual(gauge_color_rgb(100, high_is_good=True), (0, 200, 120))
        self.assertEqual(gauge_color_rgb(100), (255, 70, 70))

    def test_monitor_source_wires_frame_rate_gauge(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn('Gauge("FPS", preferred_size=250, minimum_size=80, high_is_good=True)', source)
        self.assertIn("self.frame_rate", source)
        self.assertIn("update_frame_rate", source)
        self.assertIn('"UI render"', source)
        self.assertNotIn('"Game FPS later"', source)


if __name__ == "__main__":
    unittest.main()
