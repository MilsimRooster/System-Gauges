import unittest
from pathlib import Path


class GaugeLiquidGlassSourceTests(unittest.TestCase):
    def test_gauge_ring_keeps_glass_highlights(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn("track_alpha", source)
        self.assertIn("def draw_liquid_glass_surface", source)
        self.assertIn("QLinearGradient", source)
        self.assertIn("QPainterPath", source)
        self.assertIn("top_edge", source)
        self.assertIn("right_edge", source)
        self.assertIn("top_glare_path", source)
        self.assertIn("shine_span", source)
        self.assertIn("shine_start", source)
        self.assertIn("QColor(245, 255, 252, 150)", source)

    def test_gauge_glint_uses_gradient_falloff_not_solid_white_arc(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")
        glass_source = source[
            source.index("def draw_liquid_glass_surface") : source.index("    def paintEvent", source.index("def draw_liquid_glass_surface"))
        ]

        self.assertNotIn("QColor(255, 255, 255, 216)", glass_source)
        self.assertIn("top_glare.setColorAt(0.00, QColor(255, 255, 255, 0))", glass_source)
        self.assertNotIn("glint_width", glass_source)
        self.assertNotIn("painter.drawArc(arc.adjusted", glass_source)
        self.assertIn("top_glare_path.addEllipse(glass_rect)", glass_source)
        self.assertIn("top_glare.setColorAt(0.18, QColor(255, 255, 255, 84 if compact else 66))", glass_source)
        self.assertIn("top_glare.setColorAt(0.82, QColor(255, 255, 255, 0))", glass_source)
        self.assertIn("right_edge.setColorAt(0.00, QColor(255, 255, 255, 0))", glass_source)
        self.assertIn("right_edge.setColorAt(0.34, QColor(122, 239, 228, 64 if compact else 48))", glass_source)
        self.assertIn("right_edge.setColorAt(1.00, QColor(255, 255, 255, 0))", glass_source)


if __name__ == "__main__":
    unittest.main()
