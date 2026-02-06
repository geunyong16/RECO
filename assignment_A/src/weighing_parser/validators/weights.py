"""Weight validation logic.

DEPRECATED: Weight validation is now handled by WeighingReceipt model_validator.
This class is retained for standalone validation use cases and will be removed in v2.0.
"""

import warnings
from decimal import Decimal
from typing import Tuple, Optional, Union


class WeightValidator:
    """
    Validates weight measurements and calculations.

    .. deprecated::
        This class is deprecated. Weight validation is now handled by
        ``WeighingReceipt.model_validator``. Use domain model validation instead.
        This class will be removed in v2.0.
    """

    # Allow small discrepancies due to rounding
    DEFAULT_TOLERANCE_KG = Decimal("10")

    def __init__(self, tolerance_kg: Union[int, Decimal] = DEFAULT_TOLERANCE_KG):
        """
        Initialize validator.

        Args:
            tolerance_kg: Maximum allowed difference in kg for validation.
        """
        warnings.warn(
            "WeightValidator는 deprecated 되었습니다. "
            "WeighingReceipt model_validator 사용을 권장합니다. "
            "이 클래스는 v2.0에서 제거될 예정입니다.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.tolerance_kg = Decimal(str(tolerance_kg))

    def validate_weight_equation(
        self,
        total_kg: Union[int, Decimal],
        tare_kg: Union[int, Decimal],
        net_kg: Union[int, Decimal],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that net_weight = total_weight - tare_weight.

        Args:
            total_kg: Total weight in kg.
            tare_kg: Tare (vehicle) weight in kg.
            net_kg: Net weight in kg.

        Returns:
            Tuple of (is_valid, error_message).
            error_message is None if valid.
        """
        total = Decimal(str(total_kg))
        tare = Decimal(str(tare_kg))
        net = Decimal(str(net_kg))

        expected_net = total - tare
        difference = abs(expected_net - net)

        if difference > self.tolerance_kg:
            return (
                False,
                f"Weight mismatch: {total} - {tare} = {expected_net}, "
                f"but net weight is {net} (difference: {difference} kg)",
            )
        return True, None

    def validate_positive_weights(
        self,
        total_kg: Optional[Union[int, Decimal]],
        tare_kg: Optional[Union[int, Decimal]],
        net_kg: Optional[Union[int, Decimal]],
    ) -> list[str]:
        """
        Validate that all weights are positive.

        Returns:
            List of error messages for invalid weights.
        """
        errors = []

        if total_kg is not None and Decimal(str(total_kg)) < 0:
            errors.append(f"Total weight is negative: {total_kg} kg")

        if tare_kg is not None and Decimal(str(tare_kg)) < 0:
            errors.append(f"Tare weight is negative: {tare_kg} kg")

        if net_kg is not None and Decimal(str(net_kg)) < 0:
            errors.append(f"Net weight is negative: {net_kg} kg")

        return errors

    def validate_weight_order(
        self,
        total_kg: Optional[Union[int, Decimal]],
        tare_kg: Optional[Union[int, Decimal]],
        net_kg: Optional[Union[int, Decimal]],
    ) -> list[str]:
        """
        Validate logical weight relationships.

        - Total should be greater than or equal to tare
        - Total should be greater than or equal to net
        - Net should be less than total

        Returns:
            List of error messages for invalid relationships.
        """
        errors = []

        if total_kg is not None and tare_kg is not None:
            total = Decimal(str(total_kg))
            tare = Decimal(str(tare_kg))
            if total < tare:
                errors.append(
                    f"Total weight ({total} kg) is less than "
                    f"tare weight ({tare} kg)"
                )

        if total_kg is not None and net_kg is not None:
            total = Decimal(str(total_kg))
            net = Decimal(str(net_kg))
            if net > total:
                errors.append(
                    f"Net weight ({net} kg) is greater than "
                    f"total weight ({total} kg)"
                )

        return errors

    def validate_all(
        self,
        total_kg: Optional[Union[int, Decimal]],
        tare_kg: Optional[Union[int, Decimal]],
        net_kg: Optional[Union[int, Decimal]],
    ) -> list[str]:
        """
        Run all weight validations.

        Returns:
            List of all validation error messages.
        """
        errors = []

        # Check positive weights
        errors.extend(self.validate_positive_weights(total_kg, tare_kg, net_kg))

        # Check weight order
        errors.extend(self.validate_weight_order(total_kg, tare_kg, net_kg))

        # Check weight equation if all values present
        if total_kg is not None and tare_kg is not None and net_kg is not None:
            is_valid, error = self.validate_weight_equation(total_kg, tare_kg, net_kg)
            if not is_valid and error:
                errors.append(error)

        return errors
