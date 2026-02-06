"""Main parser class that orchestrates all extraction and validation."""

import asyncio
import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Union, List, Optional, Callable, Any, Dict, Tuple
from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from .models.ocr_input import OCRDocument
from .models.receipt import WeighingReceipt, ExtractionConfidence
from .extractors.base import BaseExtractor
from .extractors.document_type import DocumentTypeExtractor
from .extractors.date import DateExtractor
from .extractors.vehicle import VehicleExtractor
from .extractors.company import CompanyExtractor, IssuerExtractor
from .extractors.weights import WeightsExtractor
from .extractors.location import LocationExtractor
from .extractors.contact import ContactExtractor
from .validators.confidence import ConfidenceValidator
from .normalizers.datetime import DateTimeNormalizer
from .logging import ParserLogger
from .config import get_settings, ParserSettings
from .exceptions import (
    ParserException,
    InvalidOCRFormatError,
    EmptyDocumentError,
    JSONParseError,
    MissingRequiredFieldError,
    ExtractionError,
    FieldNotFoundError,
    LowConfidenceError,
    NormalizationError,
    DateParseError,
    WeightParseError,
)


logger = ParserLogger(__name__)


# =============================================================================
# Extractor Registry Pattern
# =============================================================================

@dataclass
class ExtractorConfig:
    """Configuration for a registered extractor."""
    name: str
    extractor_class: type
    field_mappings: Dict[str, str]  # extractor result key -> receipt field name
    is_multi_field: bool = False  # True if extractor returns multiple fields


class ExtractorRegistry:
    """
    Registry for managing extractors.

    Allows adding new extractors without modifying parser.py.

    Usage:
        registry = ExtractorRegistry()
        registry.register("document_type", DocumentTypeExtractor, {"value": "document_type"})
        registry.register("weights", WeightsExtractor,
                         {"total": "total_weight", "tare": "tare_weight", "net": "net_weight"},
                         is_multi_field=True)
    """

    def __init__(self):
        self._extractors: Dict[str, ExtractorConfig] = {}

    def register(
        self,
        name: str,
        extractor_class: type,
        field_mappings: Dict[str, str],
        is_multi_field: bool = False
    ) -> "ExtractorRegistry":
        """
        Register an extractor.

        Args:
            name: Unique identifier for the extractor
            extractor_class: The extractor class to instantiate
            field_mappings: Maps extractor output to receipt fields
            is_multi_field: Whether extractor returns multiple values

        Returns:
            Self for method chaining
        """
        self._extractors[name] = ExtractorConfig(
            name=name,
            extractor_class=extractor_class,
            field_mappings=field_mappings,
            is_multi_field=is_multi_field
        )
        return self

    def unregister(self, name: str) -> bool:
        """Remove an extractor from registry."""
        if name in self._extractors:
            del self._extractors[name]
            return True
        return False

    def get(self, name: str) -> Optional[ExtractorConfig]:
        """Get extractor config by name."""
        return self._extractors.get(name)

    def get_all(self) -> Dict[str, ExtractorConfig]:
        """Get all registered extractors."""
        return self._extractors.copy()

    def __contains__(self, name: str) -> bool:
        return name in self._extractors

    def __len__(self) -> int:
        return len(self._extractors)


def create_default_registry() -> ExtractorRegistry:
    """Create registry with default extractors."""
    registry = ExtractorRegistry()

    # Single-field extractors
    registry.register("document_type", DocumentTypeExtractor, {"value": "document_type"})
    registry.register("vehicle", VehicleExtractor, {"value": "vehicle_number"})
    registry.register("company", CompanyExtractor, {"value": "company_name"})
    registry.register("issuer", IssuerExtractor, {"value": "issuing_company"})
    registry.register("contact", ContactExtractor, {"value": "phone"})

    # Multi-field extractors
    registry.register(
        "date", DateExtractor,
        {"date": "date", "sequence": "sequence_number"},
        is_multi_field=True
    )
    registry.register(
        "weights", WeightsExtractor,
        {"total": "total_weight", "tare": "tare_weight", "net": "net_weight"},
        is_multi_field=True
    )
    registry.register(
        "location", LocationExtractor,
        {"gps": "gps_coordinates", "address": "address"},
        is_multi_field=True
    )

    return registry


# Global default registry
_default_registry = create_default_registry()


def get_default_registry() -> ExtractorRegistry:
    """Get the global default extractor registry."""
    return _default_registry


# =============================================================================
# Extraction Result Types
# =============================================================================

@dataclass
class ExtractionResult:
    """Result of a single field extraction."""
    field_name: str
    value: Any
    confidence: float
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# Main Parser Class
# =============================================================================

class WeighingReceiptParser:
    """
    Main parser for Korean vehicle weighing receipts.

    Orchestrates all extractors, normalizers, and validators to parse
    OCR JSON input into structured WeighingReceipt output.

    Features:
    - Extractor registry pattern for extensibility
    - Centralized error handling via _extract_field helper
    - Graceful degradation on partial failures
    """

    def __init__(
        self,
        min_confidence: Optional[float] = None,
        weight_tolerance_kg: Optional[Union[int, Decimal]] = None,
        max_workers: Optional[int] = None,
        settings: Optional[ParserSettings] = None,
        registry: Optional[ExtractorRegistry] = None,
    ):
        """
        Initialize parser.

        Args:
            min_confidence: Minimum confidence threshold for extractions.
            weight_tolerance_kg: Tolerance in kg for weight validation.
            max_workers: Maximum number of worker threads for async operations.
            settings: Optional ParserSettings instance for Dependency Injection.
            registry: Optional ExtractorRegistry for custom extractors.
        """
        # Load settings
        self._settings = settings or get_settings()

        # Allow explicit parameters to override settings
        self.min_confidence = (
            min_confidence if min_confidence is not None
            else self._settings.min_confidence
        )
        self.weight_tolerance_kg = (
            Decimal(str(weight_tolerance_kg)) if weight_tolerance_kg is not None
            else self._settings.weight_tolerance_kg
        )

        # Extractor registry
        self._registry = registry or get_default_registry()

        # Instantiate extractors from registry
        self._extractors: Dict[str, BaseExtractor] = {}
        for name, config in self._registry.get_all().items():
            self._extractors[name] = config.extractor_class(self.min_confidence)

        # Validators
        self.confidence_validator = ConfidenceValidator()

        # Thread pool for async operations
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = (
            max_workers if max_workers is not None
            else self._settings.max_workers
        )

    # =========================================================================
    # Extractor Access (for backward compatibility)
    # =========================================================================

    @property
    def document_type_extractor(self) -> DocumentTypeExtractor:
        return self._extractors.get("document_type")

    @property
    def date_extractor(self) -> DateExtractor:
        return self._extractors.get("date")

    @property
    def vehicle_extractor(self) -> VehicleExtractor:
        return self._extractors.get("vehicle")

    @property
    def company_extractor(self) -> CompanyExtractor:
        return self._extractors.get("company")

    @property
    def issuer_extractor(self) -> IssuerExtractor:
        return self._extractors.get("issuer")

    @property
    def weights_extractor(self) -> WeightsExtractor:
        return self._extractors.get("weights")

    @property
    def location_extractor(self) -> LocationExtractor:
        return self._extractors.get("location")

    @property
    def contact_extractor(self) -> ContactExtractor:
        return self._extractors.get("contact")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_executor(self) -> ThreadPoolExecutor:
        """Lazy initialization of thread pool executor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        return self._executor

    def __del__(self):
        """Cleanup thread pool on destruction."""
        if hasattr(self, "_executor") and self._executor is not None:
            self._executor.shutdown(wait=False)

    def _extract_field(
        self,
        extractor: BaseExtractor,
        document: OCRDocument,
        field_name: str,
        extract_method: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract a single field with standardized error handling.

        This helper method eliminates repetitive try-except blocks by providing
        a unified extraction interface with consistent error handling.

        Args:
            extractor: The extractor instance to use
            document: OCR document to extract from
            field_name: Name of the field being extracted (for logging/errors)
            extract_method: Optional method name to call (default: "extract")

        Returns:
            ExtractionResult with value, confidence, and error info
        """
        method_name = extract_method or "extract"

        try:
            method = getattr(extractor, method_name)
            result = method(document)

            # Handle different return types
            if isinstance(result, tuple) and len(result) == 2:
                value, confidence = result
                return ExtractionResult(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    success=True
                )
            else:
                return ExtractionResult(
                    field_name=field_name,
                    value=result,
                    confidence=0.0,
                    success=True
                )

        except (DateParseError, WeightParseError) as e:
            logger.extraction_failed(field=field_name, error=str(e))
            return ExtractionResult(
                field_name=field_name,
                value=None,
                confidence=0.0,
                success=False,
                error_message=f"{field_name} parsing failed: {e.input_value}"
            )
        except (ExtractionError, NormalizationError) as e:
            logger.extraction_failed(field=field_name, error=str(e))
            return ExtractionResult(
                field_name=field_name,
                value=None,
                confidence=0.0,
                success=False,
                error_message=f"{field_name} extraction failed: {e.message}"
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.extraction_failed(field=field_name, error=str(e))
            return ExtractionResult(
                field_name=field_name,
                value=None,
                confidence=0.0,
                success=False,
                error_message=f"{field_name} extraction error: {str(e)}"
            )

    def _extract_multi_field(
        self,
        extractor: BaseExtractor,
        document: OCRDocument,
        field_names: List[str],
        extract_method: Optional[str] = None,
    ) -> Tuple[List[ExtractionResult], float]:
        """
        Extract multiple fields from a single extractor call.

        Args:
            extractor: The extractor instance
            document: OCR document
            field_names: List of field names corresponding to return values
            extract_method: Optional method name (default: "extract")

        Returns:
            Tuple of (list of ExtractionResults, average confidence)
        """
        method_name = extract_method or "extract"

        try:
            method = getattr(extractor, method_name)
            result = method(document)

            # Unpack tuple results
            if isinstance(result, tuple):
                values = list(result[:-1])  # All but last (confidence)
                confidence = result[-1] if isinstance(result[-1], (int, float)) else 0.0
            else:
                values = [result]
                confidence = 0.0

            results = []
            for i, field_name in enumerate(field_names):
                value = values[i] if i < len(values) else None
                results.append(ExtractionResult(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    success=True
                ))

            return results, confidence

        except (DateParseError, WeightParseError) as e:
            logger.extraction_failed(field=",".join(field_names), error=str(e))
            return [
                ExtractionResult(
                    field_name=fn,
                    value=None,
                    confidence=0.0,
                    success=False,
                    error_message=f"parsing failed: {e.input_value}"
                ) for fn in field_names
            ], 0.0
        except (ExtractionError, NormalizationError) as e:
            logger.extraction_failed(field=",".join(field_names), error=str(e))
            return [
                ExtractionResult(
                    field_name=fn,
                    value=None,
                    confidence=0.0,
                    success=False,
                    error_message=f"extraction failed: {e.message}"
                ) for fn in field_names
            ], 0.0
        except (ValueError, TypeError, AttributeError) as e:
            logger.extraction_failed(field=",".join(field_names), error=str(e))
            return [
                ExtractionResult(
                    field_name=fn,
                    value=None,
                    confidence=0.0,
                    success=False,
                    error_message=f"extraction error: {str(e)}"
                ) for fn in field_names
            ], 0.0

    # =========================================================================
    # Main Parsing Methods
    # =========================================================================

    def parse_file(self, filepath: Union[str, Path]) -> WeighingReceipt:
        """
        Parse a single OCR JSON file.

        Args:
            filepath: Path to OCR JSON file.

        Returns:
            Parsed WeighingReceipt.

        Raises:
            FileNotFoundError: If file doesn't exist.
            JSONParseError: If JSON parsing fails.
            MissingRequiredFieldError: If required OCR fields are missing.
            EmptyDocumentError: If document has no pages.
        """
        filepath = Path(filepath)
        filepath_str = str(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"OCR file not found: {filepath_str}")

        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise JSONParseError(original_error=str(e), filepath=filepath_str)

        if not isinstance(data, dict):
            raise InvalidOCRFormatError(
                "OCR data must be a JSON object",
                filepath=filepath_str
            )

        required_fields = ["apiVersion", "confidence", "text", "pages"]
        for field in required_fields:
            if field not in data:
                raise MissingRequiredFieldError(field, filepath=filepath_str)

        try:
            document = OCRDocument(**data)
        except PydanticValidationError as e:
            first_error = e.errors()[0] if e.errors() else {"msg": str(e)}
            field_path = ".".join(str(loc) for loc in first_error.get("loc", []))
            raise InvalidOCRFormatError(
                f"Invalid OCR field '{field_path}': {first_error.get('msg', 'validation failed')}",
                filepath=filepath_str,
                details={"validation_errors": e.errors()}
            )
        except TypeError as e:
            raise InvalidOCRFormatError(f"Type error in OCR data: {e}", filepath=filepath_str)

        return self.parse(document)

    def parse(self, document: OCRDocument) -> WeighingReceipt:
        """
        Parse OCR document to structured receipt.

        Args:
            document: Parsed OCR document.

        Returns:
            Parsed WeighingReceipt.

        Raises:
            EmptyDocumentError: If document has no pages or no text content.
        """
        # Validate input
        if not document.pages:
            raise EmptyDocumentError()
        if not document.text or not document.text.strip():
            raise EmptyDocumentError()
        if not document.get_lines():
            raise EmptyDocumentError()

        # Initialize collection containers
        extracted_data: Dict[str, Any] = {"raw_text": document.get_full_text()}
        confidence_scores: List[ExtractionConfidence] = []
        validation_errors: List[str] = []

        # === Extract single-value fields ===
        single_field_extractions = [
            ("document_type", "document_type", "extract"),
            ("vehicle", "vehicle_number", "extract"),
            ("company", "company_name", "extract"),
            ("issuer", "issuing_company", "extract"),
            ("contact", "phone", "extract"),
        ]

        for extractor_name, field_name, method in single_field_extractions:
            extractor = self._extractors.get(extractor_name)
            if extractor:
                result = self._extract_field(extractor, document, field_name, method)
                extracted_data[field_name] = result.value

                if result.success and result.confidence > 0:
                    confidence_scores.append(
                        self.confidence_validator.check_confidence(field_name, result.confidence)
                    )
                    if result.confidence < self.min_confidence:
                        validation_errors.append(
                            f"Low confidence for {field_name}: {result.confidence:.2%}"
                        )
                elif not result.success and result.error_message:
                    validation_errors.append(result.error_message)

        # === Extract date with sequence (special handling) ===
        date_extractor = self._extractors.get("date")
        if date_extractor:
            results, conf = self._extract_multi_field(
                date_extractor, document,
                ["date", "sequence_number"],
                "extract_with_sequence"
            )
            for r in results:
                extracted_data[r.field_name] = r.value
                if not r.success and r.error_message:
                    validation_errors.append(r.error_message)
            if conf > 0:
                confidence_scores.append(
                    self.confidence_validator.check_confidence("date", conf)
                )

        # === Extract weights (returns 4 values: total, tare, net, confidence) ===
        weights_extractor = self._extractors.get("weights")
        if weights_extractor:
            results, conf = self._extract_multi_field(
                weights_extractor, document,
                ["total_weight", "tare_weight", "net_weight"],
                "extract"
            )
            for r in results:
                extracted_data[r.field_name] = r.value
                if not r.success and r.error_message:
                    validation_errors.append(r.error_message)
            if conf > 0:
                confidence_scores.append(
                    self.confidence_validator.check_confidence("weights", conf)
                )

        # === Extract location (returns 3 values: gps, address, confidence) ===
        location_extractor = self._extractors.get("location")
        if location_extractor:
            results, conf = self._extract_multi_field(
                location_extractor, document,
                ["gps_coordinates", "address"],
                "extract"
            )
            for r in results:
                extracted_data[r.field_name] = r.value
                if not r.success and r.error_message:
                    validation_errors.append(r.error_message)
            if conf > 0:
                confidence_scores.append(
                    self.confidence_validator.check_confidence("location", conf)
                )

        # === Extract timestamp (not from registry, special case) ===
        try:
            timestamp = DateTimeNormalizer.parse_timestamp(document.get_full_text())
            extracted_data["timestamp"] = timestamp
        except DateParseError as e:
            logger.extraction_failed(field="timestamp", error=str(e))
            validation_errors.append(f"timestamp parsing failed: {e.input_value}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.extraction_failed(field="timestamp", error=str(e))
            validation_errors.append(f"timestamp extraction error: {str(e)}")

        # === Document-level confidence validation ===
        doc_conf_warning = self.confidence_validator.validate_document_confidence(
            document.confidence
        )
        if doc_conf_warning:
            validation_errors.append(doc_conf_warning)

        # Field-level confidence warnings
        for score in confidence_scores:
            warning = self.confidence_validator.get_warning_message(
                score.field_name, score.confidence
            )
            if warning:
                validation_errors.append(warning)

        # === Build final receipt ===
        extracted_data["confidence_scores"] = confidence_scores
        extracted_data["validation_errors"] = validation_errors
        extracted_data["weight_tolerance_kg"] = self.weight_tolerance_kg

        return WeighingReceipt(**extracted_data)

    def parse_batch(self, filepaths: list[Union[str, Path]]) -> list[WeighingReceipt]:
        """Parse multiple OCR JSON files."""
        results = []
        for filepath in filepaths:
            try:
                receipt = self.parse_file(filepath)
                results.append(receipt)
            except Exception as e:
                logger.parse_error(
                    file_path=str(filepath),
                    error=str(e),
                    error_type=type(e).__name__
                )
                error_receipt = WeighingReceipt(validation_errors=[f"Parse error: {e}"])
                results.append(error_receipt)
        return results

    # =========================================================================
    # Async Methods
    # =========================================================================

    async def parse_async(self, document: OCRDocument) -> WeighingReceipt:
        """Parse OCR document asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._get_executor(), self.parse, document)

    async def parse_file_async(self, filepath: Union[str, Path]) -> WeighingReceipt:
        """Parse a single OCR JSON file asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._get_executor(), self.parse_file, filepath)

    async def parse_batch_async(
        self, filepaths: List[Union[str, Path]]
    ) -> List[WeighingReceipt]:
        """Parse multiple OCR JSON files concurrently."""
        tasks = [self.parse_file_async(fp) for fp in filepaths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        receipts = []
        for filepath, result in zip(filepaths, results):
            if isinstance(result, Exception):
                logger.parse_error(
                    file_path=str(filepath),
                    error=str(result),
                    error_type=type(result).__name__
                )
                receipts.append(
                    WeighingReceipt(validation_errors=[f"Parse error: {result}"])
                )
            else:
                receipts.append(result)

        return receipts
