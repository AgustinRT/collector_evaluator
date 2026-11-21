import pytest
from pydantic import ValidationError

from src.domain.enum.item_status import ItemStatus
from src.domain.model.item_collection import ItemCollection

SAMPLE_DVD_BARCODE = 5050582500417  # src/resources/sample_dvd/barcode.jpg


@pytest.fixture
def valid_fields(alice):
    return {"name": "Sample DVD", "description": "A DVD", "barcode": SAMPLE_DVD_BARCODE, "owner": alice}


def _error_types(exc_info) -> list[tuple[tuple, str]]:
    return [(error["loc"], error["type"]) for error in exc_info.value.errors()]


def test_new_item_starts_validating(valid_fields, alice):
    item = ItemCollection(**valid_fields)

    assert item.status is ItemStatus.VALIDATING
    assert item.owner == alice


def test_name_and_description_are_stripped(valid_fields):
    item = ItemCollection(**valid_fields | {"name": "  Sample DVD ", "description": " A DVD  "})

    assert (item.name, item.description) == ("Sample DVD", "A DVD")


@pytest.mark.parametrize("missing", ["name", "description", "barcode", "owner"])
def test_mandatory_fields(valid_fields, missing):
    del valid_fields[missing]

    with pytest.raises(ValidationError) as exc_info:
        ItemCollection(**valid_fields)

    assert _error_types(exc_info) == [((missing,), "missing")]


@pytest.mark.parametrize("field, value, error_type", [
    ("name", "   ", "string_too_short"),
    ("name", "n" * 201, "string_too_long"),
    ("description", "", "string_too_short"),
    ("description", "d" * 2001, "string_too_long"),
])
def test_name_and_description_must_be_non_blank_and_bounded(valid_fields, field, value, error_type):
    with pytest.raises(ValidationError) as exc_info:
        ItemCollection(**valid_fields | {field: value})

    assert _error_types(exc_info) == [((field,), error_type)]


# --- barcode --------------------------------------------------------------------------------------

@pytest.mark.parametrize("barcode", [
    SAMPLE_DVD_BARCODE,  # EAN-13
    9780306406157,       # ISBN-13 (EAN-13 of a book)
    96385074,            # EAN-8
    12345678905,         # UPC-A 012345678905: the leading zero cannot be kept in a number
    15050582500414,      # GTIN-14
])
def test_valid_barcodes_are_accepted(valid_fields, barcode):
    assert ItemCollection(**valid_fields | {"barcode": barcode}).barcode == barcode


@pytest.mark.parametrize("position", range(len(str(SAMPLE_DVD_BARCODE))))
def test_any_single_digit_typo_is_rejected(valid_fields, position):
    digits = list(str(SAMPLE_DVD_BARCODE))
    digits[position] = str((int(digits[position]) + 1) % 10)
    mistyped = int("".join(digits))

    with pytest.raises(ValidationError) as exc_info:
        ItemCollection(**valid_fields | {"barcode": mistyped})

    assert _error_types(exc_info) == [(("barcode",), "value_error")]
    assert "invalid check digit" in str(exc_info.value)


@pytest.mark.parametrize("barcode, error_type", [
    (0, "greater_than"),
    (-SAMPLE_DVD_BARCODE, "greater_than"),
    (10**14, "less_than"),            # more than 14 digits
    (str(SAMPLE_DVD_BARCODE), "int_type"),
    (float(SAMPLE_DVD_BARCODE), "int_type"),
    (True, "int_type"),
    (None, "int_type"),
])
def test_barcode_must_be_a_positive_integer_of_at_most_14_digits(valid_fields, barcode, error_type):
    with pytest.raises(ValidationError) as exc_info:
        ItemCollection(**valid_fields | {"barcode": barcode})

    assert _error_types(exc_info) == [(("barcode",), error_type)]
