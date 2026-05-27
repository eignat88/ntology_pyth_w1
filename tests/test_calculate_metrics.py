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
            max_amount=1_000_000.0,
            amount_scale=2,
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

    def test_calculate_metrics_allows_mixed_valid_statuses_and_counts_only_delivered(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "pending", "Returned", "shipped"],
                "amount": ["100", "50", "70", "20"],
            }
        )

        metrics = self.analyzer.calculate_metrics(df)
        self.assertEqual(metrics["orders_count"], 1)
        self.assertEqual(metrics["total_revenue"], 100.0)
        self.assertEqual(metrics["average_check"], 100.0)

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

    def test_calculate_metrics_rejects_truly_not_allowed_status(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "in_transit_custom"],
                "amount": ["100", "50"],
            }
        )

        with self.assertRaises(StatusValidationError) as error:
            self.analyzer.calculate_metrics(df)

        self.assertEqual(error.exception.code, "ERR_STATUS_NOT_ALLOWED")
        self.assertEqual(error.exception.raw_value, "in_transit_custom")
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

    def test_validate_total_amount_rejects_non_positive_values(self):
        for raw in ["0", "0.00"]:
            with self.assertRaises(AmountValidationError) as error:
                self.analyzer.validate_total_amount(raw_value=raw, row_number=2)
            self.assertEqual(error.exception.code, "ERR_AMOUNT_NON_POSITIVE")

    def test_validate_total_amount_rejects_too_large_values(self):
        with self.assertRaises(AmountValidationError) as error:
            self.analyzer.validate_total_amount(raw_value="1000000.01", row_number=2)
        self.assertEqual(error.exception.code, "ERR_AMOUNT_TOO_LARGE")

    def test_validate_total_amount_rejects_scale_exceeded(self):
        with self.assertRaises(AmountValidationError) as error:
            self.analyzer.validate_total_amount(raw_value="12.345", row_number=2)
        self.assertEqual(error.exception.code, "ERR_AMOUNT_SCALE_EXCEEDED")

    def test_validate_rows_collects_detailed_errors_and_stats(self):
        df = pd.DataFrame(
            {
                "status": ["delivered", "unknown_status", " ", "delivered"],
                "amount": ["10", "20", "oops", "0"],
            }
        )

        result = self.analyzer.validate_rows(df, fail_fast=False)

        self.assertEqual(result["valid_rows_count"], 2)
        self.assertEqual(result["invalid_rows_count"], 2)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0]["row_number"], 3)
        self.assertEqual(result["warnings"][0]["field"], "status")
        self.assertEqual(result["warnings"][0]["error_code"], "ERR_STATUS_NOT_ALLOWED")
        self.assertEqual(result["critical_errors"][0]["row_number"], 4)
        self.assertEqual(result["critical_errors"][0]["field"], "amount")
        self.assertEqual(
            result["critical_errors"][0]["error_code"], "ERR_AMOUNT_FORMAT"
        )
        self.assertEqual(result["error_code_stats"]["ERR_STATUS_NOT_ALLOWED"], 1)
        self.assertEqual(result["error_code_stats"]["ERR_AMOUNT_FORMAT"], 1)
        self.assertEqual(result["error_code_stats"]["ERR_AMOUNT_NON_POSITIVE"], 1)

    def test_validate_rows_fail_fast_stops_on_first_critical_error(self):
        df = pd.DataFrame(
            {
                "status": ["unknown_status", "delivered", "delivered"],
                "amount": ["10", "oops", "99"],
            }
        )

        result = self.analyzer.validate_rows(df, fail_fast=True)

        self.assertEqual(result["valid_rows_count"], 1)
        self.assertEqual(result["invalid_rows_count"], 1)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["critical_errors"][0]["row_number"], 3)
        self.assertEqual(result["critical_errors"][0]["error_code"], "ERR_AMOUNT_FORMAT")


if __name__ == "__main__":
    unittest.main()
