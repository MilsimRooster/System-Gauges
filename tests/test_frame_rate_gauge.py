import sys
import struct
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import (
    frame_rate_percent,
    gauge_color_rgb,
    gauge_history_color_rgb,
    parse_presentmon_fps,
    parse_rtss_fps_snapshot,
    presentmon_failure_message,
)


RTSS_SIGNATURE = struct.unpack("<I", b"RTSS")[0]


def make_rtss_snapshot(entries, foreground_index=0):
    entry_size = 288
    app_offset = 128
    app_count = max(len(entries), 4)
    data = bytearray(app_offset + (entry_size * app_count))
    struct.pack_into("<IIIII", data, 0, RTSS_SIGNATURE, 0x00020010, entry_size, app_offset, app_count)
    struct.pack_into("<I", data, 64, foreground_index)

    for index, entry in enumerate(entries):
        offset = app_offset + (entry_size * index)
        name = entry["name"].encode("mbcs", errors="ignore")[:259]
        struct.pack_into("<I", data, offset, entry.get("pid", index + 1000))
        data[offset + 4:offset + 4 + len(name)] = name
        struct.pack_into(
            "<IIII",
            data,
            offset + 268,
            entry.get("time0", 1000),
            entry.get("time1", 2000),
            entry.get("frames", 60),
            entry.get("frame_time", 0),
        )

    return bytes(data)


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

    def test_frame_rate_history_graph_treats_high_fps_as_good(self):
        self.assertEqual(gauge_history_color_rgb(100, high_is_good=True), (0, 255, 120))
        self.assertEqual(gauge_history_color_rgb(100), (255, 60, 0))

    def test_parse_presentmon_fps_uses_largest_non_systemgauges_capture(self):
        csv_text = "\n".join([
            "\ufeffApplication,ProcessID,MsBetweenPresents",
            "SystemGauges.exe,100,10",
            "Codex.exe,101,16.6667",
            "CoolGame.exe,200,16.6667",
            "CoolGame.exe,200,16.6667",
            "Launcher.exe,300,33.3333",
        ])

        reading = parse_presentmon_fps(csv_text)

        self.assertEqual(reading["application"], "CoolGame.exe")
        self.assertEqual(reading["frames"], 2)
        self.assertAlmostEqual(reading["fps"], 60.0, places=1)

    def test_parse_presentmon_fps_returns_none_without_frame_times(self):
        csv_text = "\n".join([
            "Application,ProcessID,MsBetweenPresents",
            "SystemGauges.exe,100,10",
            "CoolGame.exe,200,NA",
        ])

        self.assertIsNone(parse_presentmon_fps(csv_text))

    def test_parse_rtss_fps_snapshot_uses_foreground_app(self):
        snapshot = make_rtss_snapshot([
            {"name": "OldGame.exe", "time0": 1000, "time1": 2000, "frames": 30},
            {"name": "CoolGame.exe", "time0": 1000, "time1": 2000, "frames": 144},
        ], foreground_index=1)

        reading = parse_rtss_fps_snapshot(snapshot)

        self.assertEqual(reading["application"], "CoolGame.exe")
        self.assertAlmostEqual(reading["fps"], 144.0, places=1)
        self.assertEqual(reading["source"], "RTSS")

    def test_parse_rtss_fps_snapshot_falls_back_to_frame_time(self):
        snapshot = make_rtss_snapshot([
            {"name": "CoolGame.exe", "time0": 0, "time1": 0, "frames": 0, "frame_time": 16667},
        ])

        reading = parse_rtss_fps_snapshot(snapshot)

        self.assertEqual(reading["application"], "CoolGame.exe")
        self.assertAlmostEqual(reading["fps"], 60.0, places=1)

    def test_parse_rtss_fps_snapshot_returns_none_without_valid_app(self):
        snapshot = make_rtss_snapshot([
            {"name": "SystemGauges.exe", "time0": 1000, "time1": 2000, "frames": 60},
            {"name": "CoolGame.exe", "time0": 2000, "time1": 1000, "frames": 60},
        ])

        self.assertIsNone(parse_rtss_fps_snapshot(snapshot))

    def test_presentmon_failure_message_explains_access_denied(self):
        output = "error: failed to start trace session: access denied."

        self.assertEqual(presentmon_failure_message(output), "Needs admin or PerfLog")

    def test_presentmon_failure_message_does_not_treat_warning_as_failure(self):
        output = "\n".join([
            "Started recording.",
            "Stopped recording.",
            "warning: PresentMon requires elevated privilege in order to query processes",
        ])

        self.assertEqual(presentmon_failure_message(output), "No game frames")

    def test_presentmon_failure_message_explains_lost_etw_events(self):
        output = "\n".join([
            "Started recording.",
            "Stopped recording.",
            "warning: 27030 ETW events were lost.",
        ])

        self.assertEqual(presentmon_failure_message(output), "Run elevated")

    def test_monitor_source_wires_frame_rate_gauge(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn('Gauge("FPS", preferred_size=250, minimum_size=80, high_is_good=True)', source)
        self.assertIn("self.frame_rate", source)
        self.assertIn("update_frame_rate", source)
        self.assertIn("PresentMon", source)
        self.assertIn("RTSS", source)
        self.assertIn("RTSSSharedMemoryV2", source)
        self.assertIn("PresentMonWorker", source)
        self.assertIn("find_presentmon_executable", source)
        self.assertIn("PresentMonConsoleApplication", source)
        self.assertIn("--output_file", source)
        self.assertIn('"Game FPS"', source)
        self.assertIn('"UI render"', source)
        self.assertNotIn('"Game FPS later"', source)


if __name__ == "__main__":
    unittest.main()
