from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

OUTPUT_REPORT_FILE = REPORTS_DIR / "summary_report.csv"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"

STATUS_COLUMN = "status"
DELIVERED_STATUS = "Delivered"

AMOUNT_COLUMN = "total_amount"

REQUIRED_COLUMNS = [
    "order_id",
    "person_id",
    "order_date",
    "status",
    "total_amount",
    "currency",
    "payment_method",
    "shipping_method",
    "notes",
]
