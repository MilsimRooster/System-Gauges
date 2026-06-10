import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")


class DashboardLayoutTests(unittest.TestCase):
    def test_primary_gauges_are_arranged_three_over_two(self):
        self.assertIn("top_grid.addWidget(self.gpu, 0, 0, 1, 2)", SOURCE)
        self.assertIn("top_grid.addWidget(self.cpu, 0, 2, 1, 2)", SOURCE)
        self.assertIn("top_grid.addWidget(self.ram, 0, 4, 1, 2)", SOURCE)
        self.assertIn("top_grid.addWidget(self.frame_rate, 1, 1, 1, 2)", SOURCE)
        self.assertIn("top_grid.addWidget(self.network, 1, 3, 1, 2)", SOURCE)
        self.assertIn("top_grid_wrapper.addLayout(top_grid)", SOURCE)
        self.assertNotIn("top_grid.addWidget(self.frame_rate, 0, 3)", SOURCE)
        self.assertNotIn("top_grid.addWidget(self.network, 0, 4)", SOURCE)

    def test_top_hogs_ui_is_not_wired_into_dashboard(self):
        self.assertNotIn("self.hog_header", SOURCE)
        self.assertNotIn("self.hog_toggle_button", SOURCE)
        self.assertNotIn("self.top_hogs_action", SOURCE)
        self.assertNotIn("refresh_process_hogs()", SOURCE)
        self.assertNotIn("PROCESS_HOG_REFRESH_SECONDS", SOURCE)


if __name__ == "__main__":
    unittest.main()
