import logging
from pathlib import Path

import pandas as pd


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

        if df[self.amount_column].isna().any():
            raise ValueError(f"Колонка {self.amount_column} содержит пустые значения")

        df[self.amount_column] = pd.to_numeric(df[self.amount_column], errors="raise")

        if df[self.amount_column].isna().any():
            raise ValueError(f"Колонка {self.amount_column} содержит некорректные значения")

        return df

    def filter_delivered_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Оставляет только доставленные заказы.
        """

        return df[df[self.status_column] == self.delivered_status]

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        """
        Рассчитывает метрики по доставленным заказам.
        """
        df = self.prepare_amount_column(df)

        status_raw = df[self.status_column]
        status_norm = status_raw.astype("string").str.strip().str.lower()
        delivered_mask = status_norm.eq(self.delivered_status.lower())
        delivered_df = df[delivered_mask]

        self.logger.debug("status value_counts: %s", status_norm.value_counts(dropna=False).to_dict())
        self.logger.debug(
            "amount sum by status: %s",
            df.groupby(status_norm, dropna=False)[self.amount_column].sum().to_dict(),
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
