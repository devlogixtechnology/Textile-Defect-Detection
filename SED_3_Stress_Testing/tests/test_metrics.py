import unittest

from SED_3_Stress_Testing.scripts.analysis import percentile, summarize_values, windowed_summary


class MetricTests(unittest.TestCase):
    def test_latency_percentiles(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(percentile(values, 50), 3)
        self.assertEqual(percentile(values, 95), 5)
        summary = summarize_values(values)
        self.assertEqual(summary["mean"], 3)
        self.assertEqual(summary["p99"], 5)
        self.assertEqual(summary["max"], 5)

    def test_windowed_summary(self):
        samples = [
            {"elapsed_seconds": 1, "aggregate_fps_window": 2, "mean_latency_ms_recent": 10, "p95_latency_ms_recent": 15, "process_rss_mb": 100},
            {"elapsed_seconds": 2, "aggregate_fps_window": 4, "mean_latency_ms_recent": 20, "p95_latency_ms_recent": 25, "process_rss_mb": 102},
            {"elapsed_seconds": 7, "aggregate_fps_window": 6, "mean_latency_ms_recent": 30, "p95_latency_ms_recent": 35, "process_rss_mb": 105},
        ]
        windows = windowed_summary(samples, window_seconds=5)
        self.assertEqual(len(windows), 2)
        self.assertAlmostEqual(windows[0]["mean_fps"], 3)
        self.assertAlmostEqual(windows[1]["mean_latency_ms"], 30)


if __name__ == "__main__":
    unittest.main()

