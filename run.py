from config import (
    DATA_DIR,
    REPORTS_DIR,
    LOGS_DIR,
    OUTPUT_REPORT_FILE,
    ERROR_LOG_FILE,
    STATUS_COLUMN,
    DELIVERED_STATUS,
    AMOUNT_COLUMN,
    REQUIRED_COLUMNS,
)
from src.analyzer import OrderAnalyzer


def main() -> None:
    analyzer = OrderAnalyzer(
        data_dir=DATA_DIR,
        reports_dir=REPORTS_DIR,
        logs_dir=LOGS_DIR,
        output_report_file=OUTPUT_REPORT_FILE,
        error_log_file=ERROR_LOG_FILE,
        status_column=STATUS_COLUMN,
        delivered_status=DELIVERED_STATUS,
        amount_column=AMOUNT_COLUMN,
        required_columns=REQUIRED_COLUMNS,
    )

    result = analyzer.process_all_files()

    print("Пакетная обработка завершена.")
    print(f"Всего CSV-файлов найдено: {result['total_files']}")
    print(f"Успешно обработано файлов: {result['processed_files']}")
    print(f"Файлов с ошибками: {result['error_files']}")
    print(f"Итоговый отчёт сохранён: {result['report_path']}")
    print(f"Лог ошибок: {result['log_path']}")


if __name__ == "__main__":
    main()
