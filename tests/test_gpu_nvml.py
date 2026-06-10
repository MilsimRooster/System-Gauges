import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import monitor
from monitor import GenericGpuReader, calculate_wmi_gpu_percent, safe_nvml_read, select_display_gpu_adapter, select_nvml_gpu_handle


class SafeNvmlReadTests(unittest.TestCase):
    def test_returns_value_when_nvml_call_succeeds(self):
        self.assertEqual(safe_nvml_read(lambda: 42, fallback="N/A"), 42)

    def test_returns_fallback_when_mobile_gpu_metric_is_unsupported(self):
        self.assertEqual(safe_nvml_read(lambda: (_ for _ in ()).throw(RuntimeError("not supported")), fallback="N/A"), "N/A")

    def test_nvml_support_is_optional(self):
        original = monitor.pynvml
        monitor.pynvml = None
        try:
            with self.assertRaisesRegex(RuntimeError, "NVML support is not installed"):
                select_nvml_gpu_handle()
        finally:
            monitor.pynvml = original


class GenericGpuReaderTests(unittest.TestCase):
    def test_selects_intel_or_amd_adapter_instead_of_basic_render_driver(self):
        class Adapter:
            def __init__(self, name, ram=None):
                self.Name = name
                self.AdapterRAM = ram

        adapter = select_display_gpu_adapter([
            Adapter("Microsoft Basic Render Driver"),
            Adapter("Intel(R) Iris(R) Xe Graphics", 2147483648),
        ])

        self.assertEqual(adapter.Name, "Intel(R) Iris(R) Xe Graphics")

    def test_calculates_wmi_gpu_percent_from_3d_engines(self):
        class Engine:
            def __init__(self, name, pct):
                self.Name = name
                self.UtilizationPercentage = pct

        pct = calculate_wmi_gpu_percent([
            Engine("pid_1_engtype_Copy", 90),
            Engine("pid_2_engtype_3D", 37),
            Engine("pid_3_engtype_3D", 12),
        ])

        self.assertEqual(pct, 37)

    def test_generic_reader_reports_adapter_name_usage_and_memory(self):
        class Adapter:
            Name = "AMD Radeon Graphics"
            AdapterRAM = 4294967296

        class Engine:
            Name = "pid_4_engtype_3D"
            UtilizationPercentage = 58

        class FakeWmi:
            def Win32_VideoController(self):
                return [Adapter()]

            def Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine(self):
                return [Engine()]

        reading = GenericGpuReader(lambda: FakeWmi()).read()

        self.assertEqual(reading["percent"], 58)
        self.assertEqual(reading["name"], "AMD Radeon Graphics")
        self.assertEqual(reading["memory_text"], "VRAM 4.0 GB")

    def test_generic_reader_degrades_when_perf_counters_are_missing(self):
        class Adapter:
            Name = "Intel(R) UHD Graphics"
            AdapterRAM = 0

        class FakeWmi:
            def Win32_VideoController(self):
                return [Adapter()]

            def Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine(self):
                raise AttributeError("missing GPU counter")

        reading = GenericGpuReader(lambda: FakeWmi()).read()

        self.assertEqual(reading["percent"], 0)
        self.assertEqual(reading["name"], "Intel(R) UHD Graphics")


if __name__ == "__main__":
    unittest.main()
