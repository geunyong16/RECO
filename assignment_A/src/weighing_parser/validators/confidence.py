"""Confidence score validation and flagging."""

from typing import Optional
from ..models.receipt import ExtractionConfidence


class ConfidenceValidator:
    """Validates and flags low confidence extractions."""

    # Default thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.7
    CRITICAL_THRESHOLD = 0.5

    def __init__(
        self,
        low_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        critical_threshold: float = CRITICAL_THRESHOLD,
    ):
        """
        Initialize validator.

        Args:
            low_threshold: Threshold below which confidence is flagged as low.
            critical_threshold: Threshold below which confidence is flagged as critical.
        """
        self.low_threshold = low_threshold
        self.critical_threshold = critical_threshold

    def check_confidence(
        self, field_name: str, confidence: float
    ) -> ExtractionConfidence:
        """
        Check confidence level and create confidence record.

        Args:
            field_name: Name of the extracted field.
            confidence: Confidence score (0-1).

        Returns:
            ExtractionConfidence record with flag set if low confidence.
        """
        low_flag = confidence < self.low_threshold
        return ExtractionConfidence(
            field_name=field_name,
            confidence=confidence,
            low_confidence_flag=low_flag,
        )

    def get_warning_message(
        self, field_name: str, confidence: float
    ) -> Optional[str]:
        """
        Get warning message for low confidence extraction.

        Args:
            field_name: Name of the extracted field.
            confidence: Confidence score (0-1).

        Returns:
            Warning message if confidence is below threshold, None otherwise.
        """
        if confidence < self.critical_threshold:
            return (
                f"CRITICAL: '{field_name}' has very low confidence "
                f"({confidence:.2%}), verify manually"
            )
        elif confidence < self.low_threshold:
            return (
                f"WARNING: '{field_name}' has low confidence "
                f"({confidence:.2%})"
            )
        return None

    def validate_document_confidence(
        self, overall_confidence: float
    ) -> Optional[str]:
        """
        Validate overall document OCR confidence.

        Args:
            overall_confidence: Overall document confidence score.

        Returns:
            Warning message if confidence is low.
        """
        if overall_confidence < self.critical_threshold:
            return (
                f"Document has very low OCR confidence ({overall_confidence:.2%}), "
                "results may be unreliable"
            )
        elif overall_confidence < self.low_threshold:
            return (
                f"Document has low OCR confidence ({overall_confidence:.2%})"
            )
        return None

    def filter_low_confidence_fields(
        self, confidence_scores: list[ExtractionConfidence]
    ) -> list[ExtractionConfidence]:
        """
        Filter to only low confidence fields.

        Args:
            confidence_scores: List of confidence records.

        Returns:
            List of records with low confidence flag set.
        """
        return [c for c in confidence_scores if c.low_confidence_flag]

    def get_summary(
        self, confidence_scores: list[ExtractionConfidence]
    ) -> dict:
        """
        Get summary statistics of confidence scores.

        Args:
            confidence_scores: List of confidence records.

        Returns:
            Dictionary with min, max, avg, and low_count.
        """
        if not confidence_scores:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "low_count": 0,
                "total_count": 0,
            }

        confidences = [c.confidence for c in confidence_scores]
        low_count = sum(1 for c in confidence_scores if c.low_confidence_flag)

        return {
            "min": min(confidences),
            "max": max(confidences),
            "avg": sum(confidences) / len(confidences),
            "low_count": low_count,
            "total_count": len(confidence_scores),
        }
