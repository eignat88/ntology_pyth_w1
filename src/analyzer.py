import logging
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd


class AmountValidationError(ValueError):
    """Ошибка валидации значения суммы с кодом и контекстом строки."""

    def __init__(self, code: str, raw_value: object, row_number: int):
        self.code = code
        self.raw_value = raw_value
        self.row_number = row_number
        super().__init__(
            f"{code}: invalid total_amount at row {row_number}, raw_value={raw_value!r}"
        )


class StatusValidationError(ValueError):
    """Ошибка валидации статуса заказа с кодом и контекстом строки."""

    def __init__(self, code: str, raw_value: object, row_number: int):
        self.code = code
        self.raw_value = raw_value
        self.row_number = row_number
        super().__init__(
            f"{code}: invalid status at row {row_number}, raw_value={raw_value!r}"
        )


class OrderAnalyzer:
    """
    Класс для пакетного анализа CSV-файлов с заказами интернет-магазина.

    Основные функции:
    - поиск CSV-файлов в папке data;
    - чтение данных;
    - проверка структуры файла;
    - фильтрация доставленных заказов;
    - расчёт метрик;
    - сохранение общего отчёта;
    - логирование ошибок.
    """

    def __init__(
        self,
        data_dir: Path,
        reports_dir: Path,
        logs_dir: Path,
        output_report_file: Path,
        error_log_file: Path,
        status_column: str,
        delivered_status: str,
        amount_column: str,
        max_amount: float,
        amount_scale: int,
        required_columns: list[str],
    ):
        self.data_dir = Path(data_dir)
        self.reports_dir = Path(reports_dir)
        self.logs_dir = Path(logs_dir)
        self.output_report_file = Path(output_report_file)
        self.error_log_file = Path(error_log_file)

        self.status_column = status_column
        self.delivered_status = delivered_status
        self.amount_column = amount_column
        self.max_amount = float(max_amount)
        self.amount_scale = int(amount_scale)
        self.required_columns = required_columns

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._setup_logger()

    def _setup_logger(self) -> None:
        """
        Настраивает логирование ошибок в файл logs/errors.log.
        """

        self.logger = logging.getLogger("OrderAnalyzer")
        self.logger.setLevel(logging.ERROR)

        # Защита от дублирования обработчиков при повторном создании объекта
        if not self.logger.handlers:
            file_handler = logging.FileHandler(self.error_log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def get_csv_files(self) -> list[Path]:
        """
        Возвращает список всех CSV-файлов из папки data.
        """

        return sorted(self.data_dir.glob("*.csv"))

    def load_file(self, file_path: Path) -> pd.DataFrame:
        """
        Загружает CSV-файл в DataFrame.

        Если файл пустой, повреждённый или не читается,
        pandas выбросит исключение, которое будет обработано выше.
        """

        return pd.read_csv(file_path)

    def validate_columns(self, df: pd.DataFrame, file_path: Path) -> None:
        """
        Проверяет, что в файле есть все обязательные колонки.
        """

        missing_columns = [
            column for column in self.required_columns if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"В файле отсутствуют обязательные колонки: {missing_columns}"
            )

    def prepare_amount_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Преобразует колонку total_amount в числовой тип.

        Строгий режим: любое невалидное значение (пустое или нечисловое)
        считается ошибкой файла.
        """

        df = df.copy()

        df[self.amount_column] = [
            self.validate_total_amount(raw_value=value, row_number=index + 2)
            for index, value in enumerate(df[self.amount_column].tolist())
        ]

        return df

    def validate_total_amount(self, raw_value: object, row_number: int) -> float:
        """
        Валидирует total_amount и возвращает число.

        Правила:
        - trim + нормализация строки до проверки;
        - ошибками считаются пустое значение, NaN/NULL/INF/-INF (любой регистр);
        - допускается только десятичный формат: ^\\d+(\\.\\d+)?$.
        """

        raw_as_string = "" if raw_value is None else str(raw_value)
        normalized_value = raw_as_string.strip()
        normalized_upper = normalized_value.upper()

        invalid_tokens = {"", "NAN", "NULL", "INF", "-INF"}
        decimal_pattern = r"^\d+(\.\d+)?$"

        if normalized_upper in invalid_tokens or not re.fullmatch(
            decimal_pattern, normalized_value
        ):
            raise AmountValidationError(
                code="ERR_AMOUNT_FORMAT",
                raw_value=raw_value,
                row_number=row_number,
            )

        amount = Decimal(normalized_value)

        if amount <= 0:
            raise AmountValidationError(
                code="ERR_AMOUNT_NON_POSITIVE",
                raw_value=raw_value,
                row_number=row_number,
            )

        if amount > Decimal(str(self.max_amount)):
            raise AmountValidationError(
                code="ERR_AMOUNT_TOO_LARGE",
                raw_value=raw_value,
                row_number=row_number,
            )

        scale = -amount.as_tuple().exponent if amount.as_tuple().exponent < 0 else 0
        if scale > self.amount_scale:
            raise AmountValidationError(
                code="ERR_AMOUNT_SCALE_EXCEEDED",
                raw_value=raw_value,
                row_number=row_number,
            )

        return float(amount)

    def normalize_status(self, raw_status: object) -> str:
        """Нормализует статус: trim + lower."""

        raw_as_string = "" if raw_status is None else str(raw_status)
        return raw_as_string.strip().lower()

    def validate_status(self, raw_status: object, row_number: int) -> str:
        """
        Валидирует статус по бизнес-правилам.

        Для текущего сценария разрешён только delivered.
        Пустой статус: ERR_STATUS_EMPTY.
        Любой другой статус: ERR_STATUS_NOT_ALLOWED.
        """

        normalized_status = self.normalize_status(raw_status)

        if normalized_status == "":
            raise StatusValidationError(
                code="ERR_STATUS_EMPTY",
                raw_value=raw_status,
                row_number=row_number,
            )

        allowed_statuses = {self.delivered_status.lower(), "pending", "cancelled", "returned"}

        if normalized_status not in allowed_statuses:
            raise StatusValidationError(
                code="ERR_STATUS_NOT_ALLOWED",
                raw_value=raw_status,
                row_number=row_number,
            )

        if normalized_status != self.delivered_status.lower():
            raise StatusValidationError(
                code="ERR_STATUS_NOT_ALLOWED",
                raw_value=raw_status,
                row_number=row_number,
            )

        return normalized_status

    def filter_delivered_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Оставляет только доставленные заказы.
        """

        status_norm = [
            self.validate_status(raw_status=value, row_number=index + 2)
            for index, value in enumerate(df[self.status_column].tolist())
        ]

        delivered_mask = pd.Series(status_norm, index=df.index).eq(self.delivered_status.lower())

        return df[delivered_mask]

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        """
        Рассчитывает метрики по доставленным заказам.
        """
        df = self.prepare_amount_column(df)

        status_norm = [
            self.validate_status(raw_status=value, row_number=index + 2)
            for index, value in enumerate(df[self.status_column].tolist())
        ]
        status_norm_series = pd.Series(status_norm, index=df.index)
        delivered_df = df[status_norm_series.eq(self.delivered_status.lower())]

        self.logger.debug("status value_counts: %s", status_norm_series.value_counts(dropna=False).to_dict())
        self.logger.debug(
            "amount sum by status: %s",
            df.groupby(status_norm_series, dropna=False)[self.amount_column].sum().to_dict(),
        )

        orders_count = int(len(delivered_df))
        total_revenue = (
            float(delivered_df[self.amount_column].sum(min_count=1))
            if orders_count > 0
            else 0.0
        )
        average_check = (
            float(delivered_df[self.amount_column].mean())
            if orders_count > 0
            else 0.0
        )

        return {
            "total_revenue": total_revenue,
            "average_check": average_check,
            "orders_count": orders_count,
        }

    def process_file(self, file_path: Path) -> dict | None:
        """
        Обрабатывает один CSV-файл.

        Возвращает словарь с метриками или None,
        если файл не удалось обработать.
        """

        try:
            df = self.load_file(file_path)

            if df.empty:
                raise ValueError("Файл пустой")

            self.validate_columns(df, file_path)
            df = self.prepare_amount_column(df)
            metrics = self.calculate_metrics(df)

            return {
                "file_name": file_path.name,
                **metrics,
            }

        except Exception as error:
            self.logger.error(
                "Ошибка при обработке файла %s: %s",
                file_path.name,
                error,
            )
            return None

    def save_report(self, results: list[dict]) -> None:
        """
        Сохраняет общий отчёт в CSV-файл reports/summary_report.csv.
        """

        report_df = pd.DataFrame(results)

        report_df.to_csv(
            self.output_report_file,
            index=False,
            encoding="utf-8-sig",
        )

    def process_all_files(self) -> dict:
        """
        Обрабатывает все CSV-файлы в папке data.

        Возвращает статистику:
        - сколько файлов успешно обработано;
        - сколько файлов обработано с ошибкой;
        - путь к итоговому отчёту.
        """

        csv_files = self.get_csv_files()

        results = []
        error_files_count = 0

        for file_path in csv_files:
            result = self.process_file(file_path)

            if result is None:
                error_files_count += 1
            else:
                results.append(result)

        self.save_report(results)

        return {
            "processed_files": len(results),
            "error_files": error_files_count,
            "total_files": len(csv_files),
            "report_path": self.output_report_file,
            "log_path": self.error_log_file,
        }
