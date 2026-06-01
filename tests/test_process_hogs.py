import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import rank_process_hogs, top_hogs_button_text


class ProcessHogRankingTests(unittest.TestCase):
    def test_returns_top_three_by_ram_percentage(self):
        processes = [
            {"pid": 10, "name": "idle.exe", "memory_percent": 1.0},
            {"pid": 20, "name": "render.exe", "memory_percent": 8.0},
            {"pid": 30, "name": "browser.exe", "memory_percent": 30.0},
            {"pid": 40, "name": "copy.exe", "memory_percent": 2.0},
            {"pid": 50, "name": "editor.exe", "memory_percent": 4.0},
        ]

        ranked = rank_process_hogs(processes, limit=3)

        self.assertEqual([item["pid"] for item in ranked], [30, 20, 50])
        self.assertTrue(ranked[0]["hog_score"] > ranked[1]["hog_score"])
        self.assertTrue(ranked[1]["hog_score"] > ranked[2]["hog_score"])

    def test_ignores_processes_with_no_resource_pressure(self):
        processes = [
            {"pid": 10, "name": "idle.exe", "memory_percent": 0.0},
            {"pid": 20, "name": "worker.exe", "memory_percent": 0.2},
        ]

        ranked = rank_process_hogs(processes, limit=3)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["pid"], 20)

    def test_excludes_system_idle_process_from_rankings(self):
        processes = [
            {
                "pid": 0,
                "name": "System Idle Process",
                "memory_percent": 0.0,
            },
            {"pid": 20, "name": "SystemGauges.exe", "memory_percent": 0.3},
        ]

        ranked = rank_process_hogs(processes, limit=3)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["pid"], 20)

    def test_ignores_cpu_and_disk_when_ranking(self):
        processes = [
            {"pid": 10, "name": "cpu.exe", "memory_percent": 1.0, "cpu_percent": 500.0, "disk_bytes_per_sec": 900_000_000},
            {"pid": 20, "name": "ram.exe", "memory_percent": 3.0, "cpu_percent": 0.0, "disk_bytes_per_sec": 0},
        ]

        ranked = rank_process_hogs(processes, limit=2)

        self.assertEqual([item["pid"] for item in ranked], [20, 10])

    def test_top_hogs_button_text_matches_visibility(self):
        self.assertEqual(top_hogs_button_text(True), "Hide Top Hogs")
        self.assertEqual(top_hogs_button_text(False), "Show Top Hogs")


if __name__ == "__main__":
    unittest.main()
