"""JSON output writer."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Union
from datetime import date, time

from ..models.receipt import WeighingReceipt


class JSONWriter:
    """Writes parsed receipts to JSON format."""

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for non-serializable types."""
        if isinstance(obj, Decimal):
            return str(obj)  # Preserve precision
        if isinstance(obj, (date, time)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @classmethod
    def to_dict(cls, receipt: WeighingReceipt, exclude_none: bool = True) -> dict:
        """
        Convert receipt to dictionary.

        Args:
            receipt: WeighingReceipt to convert.
            exclude_none: Whether to exclude None values.

        Returns:
            Dictionary representation of receipt.
        """
        data = receipt.model_dump()

        if exclude_none:
            data = cls._remove_none_values(data)

        return data

    @classmethod
    def _remove_none_values(cls, d: dict) -> dict:
        """Recursively remove None values from dictionary."""
        if not isinstance(d, dict):
            return d

        return {
            k: cls._remove_none_values(v)
            for k, v in d.items()
            if v is not None and v != [] and v != {}
        }

    @classmethod
    def write(
        cls,
        receipt: WeighingReceipt,
        filepath: Union[str, Path],
        pretty: bool = True,
        exclude_none: bool = True,
    ) -> None:
        """
        Write receipt to JSON file.

        Args:
            receipt: WeighingReceipt to write.
            filepath: Output file path.
            pretty: Whether to format with indentation.
            exclude_none: Whether to exclude None values.
        """
        filepath = Path(filepath)
        data = cls.to_dict(receipt, exclude_none)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2 if pretty else None,
                default=cls._json_serializer,
            )

    @classmethod
    def write_batch(
        cls,
        receipts: list[WeighingReceipt],
        filepath: Union[str, Path],
        pretty: bool = True,
        exclude_none: bool = True,
    ) -> None:
        """
        Write multiple receipts to JSON array file.

        Args:
            receipts: List of WeighingReceipts to write.
            filepath: Output file path.
            pretty: Whether to format with indentation.
            exclude_none: Whether to exclude None values.
        """
        filepath = Path(filepath)
        data = [cls.to_dict(r, exclude_none) for r in receipts]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2 if pretty else None,
                default=cls._json_serializer,
            )

    @classmethod
    def to_json_string(
        cls,
        receipt: WeighingReceipt,
        pretty: bool = True,
        exclude_none: bool = True,
    ) -> str:
        """
        Convert receipt to JSON string.

        Args:
            receipt: WeighingReceipt to convert.
            pretty: Whether to format with indentation.
            exclude_none: Whether to exclude None values.

        Returns:
            JSON string representation.
        """
        data = cls.to_dict(receipt, exclude_none)
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2 if pretty else None,
            default=cls._json_serializer,
        )
