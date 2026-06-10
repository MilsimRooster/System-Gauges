import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import frame_rate_percent


class FrameRateGaugeTests(unittest.TestCase):
    def test_frame_rate_percent_scales_to_target_fps(self):
        self.assertEqual(frame_rate_percent(30, target_fps=60), 50)
        self.assertEqual(frame_rate_percent(60, target_fps=60), 100)

    def test_frame_rate_percent_clamps_out_of_range_values(self):
        self.assertEqual(frame_rate_percent(-10, target_fps=60), 0)
        self.assertEqual(frame_rate_percent(240, target_fps=60), 100)
        self.assertEqual(frame_rate_percent(60, target_fps=0), 0)

    def test_monitor_source_wires_frame_rate_gauge(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn('Gauge("FPS"', source)
        self.assertIn("self.frame_rate", source)
        self.assertIn("update_frame_rate", source)
        self.assertIn('"UI render"', source)


if __name__ == "__main__":
    unittest.main()
