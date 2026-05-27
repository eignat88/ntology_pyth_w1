import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.analyzer import AmountValidationError, OrderAnalyzer, StatusValidationError


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
                "status": [" Delivered ", "DELIVERED"],
                "amount": ["10", "15.5"],
            }
        )

        metrics = self.analyzer.calculate_metrics(df)

        self.assertEqual(metrics["orders_count"], 2)
        self.assertEqual(metrics["total_revenue"], 25.5)
        self.assertEqual(metrics["average_check"], 12.75)

    def test_calculate_metrics_rejects_non_delivered_status_as_business_error(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "pending"],
                "amount": ["100", "50"],
            }
        )

        with self.assertRaises(StatusValidationError) as error:
            self.analyzer.calculate_metrics(df)

        self.assertEqual(error.exception.code, "ERR_STATUS_NOT_ALLOWED")
        self.assertEqual(error.exception.raw_value, "pending")
        self.assertEqual(error.exception.row_number, 3)

    def test_calculate_metrics_rejects_empty_status(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "   "],
                "amount": ["100", "50"],
            }
        )

        with self.assertRaises(StatusValidationError) as error:
            self.analyzer.calculate_metrics(df)

        self.assertEqual(error.exception.code, "ERR_STATUS_EMPTY")
        self.assertEqual(error.exception.raw_value, "   ")
        self.assertEqual(error.exception.row_number, 3)

    def test_calculate_metrics_raises_for_dirty_amounts(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "pending"],
                "amount": ["100", "oops"],
            }
        )

        with self.assertRaises(AmountValidationError) as error:
            self.analyzer.calculate_metrics(df)

        self.assertEqual(error.exception.code, "ERR_AMOUNT_FORMAT")
        self.assertEqual(error.exception.raw_value, "oops")
        self.assertEqual(error.exception.row_number, 3)

    def test_validate_total_amount_rejects_special_and_non_decimal_values(self):
        bad_values = ["", "   ", "NaN", "null", "INF", "-inf", "1e309", "500 RUB"]

        for raw in bad_values:
            with self.assertRaises(AmountValidationError):
                self.analyzer.validate_total_amount(raw_value=raw, row_number=2)

    def test_validate_total_amount_trims_and_accepts_decimal(self):
        value = self.analyzer.validate_total_amount(raw_value=" 123.45 ", row_number=5)
        self.assertEqual(value, 123.45)


if __name__ == "__main__":
    unittest.main()
