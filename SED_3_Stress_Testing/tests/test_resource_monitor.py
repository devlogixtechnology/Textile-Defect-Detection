import unittest

from SED_3_Stress_Testing.scripts.resource_monitor import ResourceMonitor


class ResourceMonitorTests(unittest.TestCase):
    def test_sample_generated_without_gpu(self):
        monitor = ResourceMonitor(interval_seconds=0.01, enable_gpu=True)
        sample = monitor.sample()
        data = sample.to_dict()
        self.assertIn("timestamp", data)
        self.assertIn("elapsed_seconds", data)
        self.assertIn("process_rss_mb", data)


if __name__ == "__main__":
    unittest.main()

