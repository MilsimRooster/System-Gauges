import unittest
from pathlib import Path


class BackgroundButtonSourceTests(unittest.TestCase):
    def test_background_menu_is_available_in_window(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn("self.background_button", source)
        self.assertIn('QPushButton("Background")', source)
        self.assertIn("create_background_menu", source)
        self.assertIn("self.background_button.setMenu", source)
        self.assertNotIn("Custom Video unavailable", source)
        self.assertNotIn("Clear Custom Video", source)


if __name__ == "__main__":
    unittest.main()
