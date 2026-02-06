"""CLI entry point for weighing receipt parser."""

import argparse
import sys
from pathlib import Path
from glob import glob
from decimal import Decimal

from .parser import WeighingReceiptParser, ParserException
from .output.json_writer import JSONWriter
from .output.csv_writer import CSVWriter
from .logging import configure_logging, ParserLogger
from .config import get_settings


def setup_logging(verbose: bool = False, log_format: str = None) -> None:
    """Configure logging.

    Args:
        verbose: Enable debug level logging
        log_format: Output format ('json' or 'text'). Defaults to settings value.
    """
    settings = get_settings()
    level = "DEBUG" if verbose else settings.log_level
    fmt = log_format or settings.log_format
    configure_logging(log_level=level, log_format=fmt)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="weighing-parser",
        description="Parse Korean vehicle weighing receipt OCR JSON files",
        epilog="Example: weighing-parser input.json -o output.json",
    )

    parser.add_argument(
        "input",
        nargs="+",
        help="Input OCR JSON file(s). Supports glob patterns (e.g., *.json)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path. Format determined by extension (.json or .csv)",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "csv"],
        help="Output format. Overrides extension detection",
    )

    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty print JSON output (default: True)",
    )

    parser.add_argument(
        "--no-pretty",
        action="store_false",
        dest="pretty",
        help="Compact JSON output",
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip weight validation",
    )

    parser.add_argument(
        "--tolerance",
        type=int,
        default=10,
        help="Weight validation tolerance in kg (default: 10)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--log-format",
        choices=["json", "text"],
        default=None,
        help="Log output format: 'json' for structured (default), 'text' for human-readable",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    return parser.parse_args()


def expand_input_paths(patterns: list[str]) -> list[Path]:
    """Expand glob patterns to file paths."""
    paths = []
    for pattern in patterns:
        # Try glob expansion
        matches = glob(pattern)
        if matches:
            paths.extend(Path(m) for m in matches)
        else:
            # Treat as literal path
            paths.append(Path(pattern))
    return paths


def determine_output_format(output_path: str, format_override: str | None) -> str:
    """Determine output format from path or override."""
    if format_override:
        return format_override

    if output_path:
        suffix = Path(output_path).suffix.lower()
        if suffix == ".csv":
            return "csv"
    return "json"


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose, args.log_format)
    logger = ParserLogger(__name__)

    # Expand input paths
    input_paths = expand_input_paths(args.input)

    # Filter to existing files
    existing_paths = [p for p in input_paths if p.exists()]
    if not existing_paths:
        logger.error("no_input_files", requested_paths=[str(p) for p in input_paths])
        return 1

    logger.info("processing_started", file_count=len(existing_paths))

    # Initialize parser
    # Note: Weight validation is now handled by WeighingReceipt model_validator
    # The --no-validate flag is deprecated but kept for backward compatibility
    parser = WeighingReceiptParser(
        weight_tolerance_kg=args.tolerance,
    )

    # Parse all files
    receipts = []
    for path in existing_paths:
        try:
            logger.parsing_started(file_path=str(path))
            receipt = parser.parse_file(path)
            receipts.append(receipt)

            # Log validation errors
            if receipt.validation_errors:
                for error in receipt.validation_errors:
                    logger.validation_error(
                        error_type="weight_validation",
                        message=error,
                        file_path=str(path)
                    )
            else:
                logger.parsing_completed(file_path=str(path), success=True)

        except ParserException as e:
            logger.parse_error(file_path=str(path), error=str(e), error_type="ParserException")
        except Exception as e:
            logger.parse_error(file_path=str(path), error=str(e), error_type=type(e).__name__)

    if not receipts:
        logger.error("no_successful_parses", attempted_files=len(existing_paths))
        return 1

    # Determine output format
    output_format = determine_output_format(args.output, args.format)

    # Write output
    if args.output:
        output_path = Path(args.output)
        logger.info("writing_output", output_path=str(output_path), format=output_format)

        if output_format == "csv":
            CSVWriter.write_batch(receipts, output_path)
        else:
            if len(receipts) == 1:
                JSONWriter.write(receipts[0], output_path, pretty=args.pretty)
            else:
                JSONWriter.write_batch(receipts, output_path, pretty=args.pretty)

        logger.info("output_written", output_path=str(output_path))
    else:
        # Print to stdout
        if output_format == "csv":
            print(CSVWriter.to_csv_string(receipts))
        else:
            if len(receipts) == 1:
                print(JSONWriter.to_json_string(receipts[0], pretty=args.pretty))
            else:
                import json

                data = [JSONWriter.to_dict(r) for r in receipts]
                print(
                    json.dumps(
                        data,
                        ensure_ascii=False,
                        indent=2 if args.pretty else None,
                        default=str,
                    )
                )

    # Summary
    error_count = sum(1 for r in receipts if r.validation_errors)
    logger.batch_summary(
        total_files=len(existing_paths),
        successful=len(receipts),
        failed=len(existing_paths) - len(receipts),
        with_warnings=error_count
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
