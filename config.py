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
MAX_AMOUNT = 1_000_000.00
AMOUNT_SCALE = 2

REQUIRED_COLUMNS = [
    "order_id",
    "person_id",
    "order_date",
    "status",
    "total_amount",
    "currency",
    "payment_method",
    "shipping_method",
]
