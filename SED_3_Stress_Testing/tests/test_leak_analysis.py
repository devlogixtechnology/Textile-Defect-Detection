import unittest

from SED_3_Stress_Testing.scripts.analysis import detect_memory_growth


class LeakAnalysisTests(unittest.TestCase):
    def test_stable_memory_not_leak(self):
        values = [100, 101, 100, 102, 101]
        samples = [{"elapsed_seconds": i * 60, "process_rss_mb": value} for i, value in enumerate(values)]
        result = detect_memory_growth(samples, "process_rss_mb")
        self.assertFalse(result["leak_detected"])

    def test_continuously_growing_memory_flags_leak(self):
        values = [100, 180, 260, 340, 420]
        samples = [{"elapsed_seconds": i * 60, "process_rss_mb": value} for i, value in enumerate(values)]
        result = detect_memory_growth(samples, "process_rss_mb")
        self.assertTrue(result["leak_detected"])


if __name__ == "__main__":
    unittest.main()

