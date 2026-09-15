import unittest


class CompletionStatusTests(unittest.TestCase):
    def test_failed_run_cannot_be_treated_as_pass(self):
        summary = {
            "status": "failed",
            "duration_seconds_measured": 12,
            "duration_seconds_configured": 1800,
            "stability": {"memory_leak_detected": False},
        }
        dod_pass = (
            summary["status"] == "completed"
            and summary["duration_seconds_measured"] >= summary["duration_seconds_configured"]
            and not summary["stability"]["memory_leak_detected"]
        )
        self.assertFalse(dod_pass)


if __name__ == "__main__":
    unittest.main()

