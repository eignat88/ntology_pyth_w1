import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.analyzer import OrderAnalyzer


class CalculateMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.analyzer = OrderAnalyzer(
            data_dir=root / "data",
            reports_dir=root / "reports",
            logs_dir=root / "logs",
            output_report_file=root / "reports" / "summary.csv",
            error_log_file=root / "logs" / "errors.log",
            status_column="status",
            delivered_status="delivered",
            amount_column="amount",
            required_columns=["status", "amount"],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_calculate_metrics_normalizes_status_and_amount(self):
        df = pd.DataFrame(
            {
                "status": [" Delivered ", "DELIVERED", "pending", ""],
                "amount": ["10", "15.5", "8", "20"],
            }
        )

        metrics = self.analyzer.calculate_metrics(df)

        self.assertEqual(metrics["total_orders"], 4)
        self.assertEqual(metrics["delivered_orders"], 2)
        self.assertEqual(metrics["total_amount"], 25.5)
        self.assertEqual(metrics["empty_status_orders"], 1)
        self.assertEqual(metrics["invalid_amount_orders"], 0)

    def test_calculate_metrics_raises_for_dirty_amounts(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "pending"],
                "amount": ["100", "oops"],
            }
        )

        with self.assertRaises(ValueError) as error:
            self.analyzer.calculate_metrics(df)

        self.assertIn("содержит нечисловые значения", str(error.exception))


if __name__ == "__main__":
    unittest.main()
