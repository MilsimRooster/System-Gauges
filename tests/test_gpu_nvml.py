import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import safe_nvml_read


class SafeNvmlReadTests(unittest.TestCase):
    def test_returns_value_when_nvml_call_succeeds(self):
        self.assertEqual(safe_nvml_read(lambda: 42, fallback="N/A"), 42)

    def test_returns_fallback_when_mobile_gpu_metric_is_unsupported(self):
        self.assertEqual(safe_nvml_read(lambda: (_ for _ in ()).throw(RuntimeError("not supported")), fallback="N/A"), "N/A")


if __name__ == "__main__":
    unittest.main()
