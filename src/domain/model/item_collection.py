

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from src.domain.enum.item_status import ItemStatus
from src.domain.model.user import User

GTIN_MAX_DIGITS = 14


def _check_gtin(barcode: int) -> int:
    """
    Verifies the check digit of an EAN-8, UPC-A, EAN-13 (including ISBN-13) or GTIN-14 barcode.
    Leading zeros do not change the check digit, so the barcode can be handled as a number.
    """
    digits = str(barcode)
    payload, check_digit = digits[:-1], int(digits[-1])
    weighted_sum = sum(int(digit) * (3 if position % 2 == 0 else 1) for position, digit in enumerate(reversed(payload)))
    if (10 - weighted_sum % 10) % 10 != check_digit:
        raise ValueError("invalid check digit: not a valid EAN/UPC/GTIN barcode")
    return barcode


ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
"""Mandatory, non-blank, at most 200 characters. Surrounding whitespace is removed."""

ItemDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
"""Mandatory, non-blank, at most 2000 characters. Surrounding whitespace is removed."""

Barcode = Annotated[int, Field(strict=True, gt=0, lt=10**GTIN_MAX_DIGITS), AfterValidator(_check_gtin)]
"""EAN/UPC/GTIN barcode as a number (up to 14 digits) with a valid check digit."""


class ItemCollection(BaseModel):
    """
    A collectible item owned by a user. The default status is the state every new item starts in.
    """
    id: int | None = Field(None, description="Identifier assigned by the database when the item is stored.")
    name: ItemName = Field(..., description="Name of item.")
    description: ItemDescription = Field(..., description="Description of item.")
    status: ItemStatus = Field(
        ItemStatus.VALIDATING,
        description="Status of item. New items are VALIDATING until their verification completes.")
    owner: User = Field(..., description="User owner of item")
    barcode: Barcode = Field(..., description="Number with the barcode (EAN/UPC/GTIN).")
