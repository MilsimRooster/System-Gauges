import unittest
from pathlib import Path


class GaugeLiquidGlassSourceTests(unittest.TestCase):
    def test_gauge_ring_keeps_glass_highlights(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn("track_alpha", source)
        self.assertIn("shine_span", source)
        self.assertIn("shine_start", source)
        self.assertIn("QColor(245, 255, 252, 150)", source)


if __name__ == "__main__":
    unittest.main()
