"""CSV output writer."""

import csv
from pathlib import Path
from typing import Union

from ..models.receipt import WeighingReceipt


class CSVWriter:
    """Writes parsed receipts to CSV format."""

    # Standard column order for CSV output
    COLUMNS = [
        "document_type",
        "date",
        "sequence_number",
        "vehicle_number",
        "company_name",
        "product_name",
        "category",
        "total_weight_kg",
        "total_weight_time",
        "tare_weight_kg",
        "tare_weight_time",
        "net_weight_kg",
        "issuing_company",
        "timestamp",
        "latitude",
        "longitude",
        "address",
        "phone",
        "validation_errors",
    ]

    @classmethod
    def write(
        cls,
        receipt: WeighingReceipt,
        filepath: Union[str, Path],
        include_header: bool = True,
    ) -> None:
        """
        Write single receipt to CSV file.

        Args:
            receipt: WeighingReceipt to write.
            filepath: Output file path.
            include_header: Whether to include column header row.
        """
        filepath = Path(filepath)
        row = receipt.to_flat_dict()

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cls.COLUMNS, extrasaction="ignore")
            if include_header:
                writer.writeheader()
            writer.writerow(row)

    @classmethod
    def write_batch(
        cls,
        receipts: list[WeighingReceipt],
        filepath: Union[str, Path],
        include_header: bool = True,
    ) -> None:
        """
        Write multiple receipts to CSV file.

        Args:
            receipts: List of WeighingReceipts to write.
            filepath: Output file path.
            include_header: Whether to include column header row.
        """
        filepath = Path(filepath)
        rows = [r.to_flat_dict() for r in receipts]

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cls.COLUMNS, extrasaction="ignore")
            if include_header:
                writer.writeheader()
            writer.writerows(rows)

    @classmethod
    def append(
        cls,
        receipt: WeighingReceipt,
        filepath: Union[str, Path],
    ) -> None:
        """
        Append receipt to existing CSV file.

        Args:
            receipt: WeighingReceipt to append.
            filepath: Output file path.
        """
        filepath = Path(filepath)
        row = receipt.to_flat_dict()

        # Check if file exists to determine if header needed
        file_exists = filepath.exists()

        with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cls.COLUMNS, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    @classmethod
    def to_csv_string(
        cls,
        receipts: list[WeighingReceipt],
        include_header: bool = True,
    ) -> str:
        """
        Convert receipts to CSV string.

        Args:
            receipts: List of WeighingReceipts to convert.
            include_header: Whether to include column header row.

        Returns:
            CSV formatted string.
        """
        import io

        output = io.StringIO()
        rows = [r.to_flat_dict() for r in receipts]

        writer = csv.DictWriter(output, fieldnames=cls.COLUMNS, extrasaction="ignore")
        if include_header:
            writer.writeheader()
        writer.writerows(rows)

        return output.getvalue()
