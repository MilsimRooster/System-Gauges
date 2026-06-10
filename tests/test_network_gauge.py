import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import format_network_speed, network_rate_percent


class NetworkGaugeTests(unittest.TestCase):
    def test_format_network_speed_uses_bits_per_second_units(self):
        self.assertEqual(format_network_speed(0), "0 bps")
        self.assertEqual(format_network_speed(1_250), "10.0 Kbps")
        self.assertEqual(format_network_speed(125_000), "1.0 Mbps")
        self.assertEqual(format_network_speed(125_000_000), "1.0 Gbps")

    def test_network_rate_percent_scales_to_target_mbps(self):
        self.assertEqual(network_rate_percent(0), 0)
        self.assertEqual(network_rate_percent(12_500_000, target_mbps=100), 100)
        self.assertEqual(network_rate_percent(6_250_000, target_mbps=100), 50)

    def test_monitor_source_wires_network_gauge(self):
        source = (Path(__file__).resolve().parents[1] / "monitor.py").read_text(encoding="utf-8")

        self.assertIn('Gauge("NET"', source)
        self.assertIn("self.network", source)
        self.assertIn("psutil.net_io_counters", source)
        self.assertIn('f"Down {format_network_speed(down)}"', source)
        self.assertIn('f"Up {format_network_speed(up)}"', source)


if __name__ == "__main__":
    unittest.main()
