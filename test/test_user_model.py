import pytest
from pydantic import ValidationError

from src.domain.enum.user_status import UserStatus
from src.domain.model.location import Location
from src.domain.model.user import User

EMAIL = "alice@example.com"


# --- user -----------------------------------------------------------------------------------------

def test_new_user_starts_in_progress_with_zero_evaluation_and_no_location():
    user = User(username="alice", email=EMAIL)

    assert user.status is UserStatus.IN_PROGRESS
    assert user.evaluation == 0.0
    assert user.location is None


def test_username_is_stripped():
    assert User(username="  alice  ", email=EMAIL).username == "alice"


@pytest.mark.parametrize("username", ["", "   ", "a" * 151])
def test_username_must_be_non_blank_and_at_most_150_characters(username):
    with pytest.raises(ValidationError):
        User(username=username, email=EMAIL)


@pytest.mark.parametrize("missing", ["username", "email"])
def test_username_and_email_are_mandatory(missing):
    fields = {"username": "alice", "email": EMAIL}
    del fields[missing]

    with pytest.raises(ValidationError) as exc_info:
        User(**fields)

    assert [(error["loc"], error["type"]) for error in exc_info.value.errors()] == [((missing,), "missing")]


@pytest.mark.parametrize("email, normalized", [
    ("alice@example.com", "alice@example.com"),
    ("  alice@example.com  ", "alice@example.com"),
    ("Alice@Example.COM", "Alice@example.com"),  # the domain is case-insensitive, the local part is not
    ("ñandú@correo.es", "ñandú@correo.es"),
])
def test_valid_email_is_accepted_and_normalized(email, normalized):
    assert User(username="alice", email=email).email == normalized


@pytest.mark.parametrize("email", [
    "", "alice", "alice@", "@example.com", "alice@example", "alice@localhost", "alice@@example.com",
    "alice@exa mple.com", "a" * 65 + "@" + "b" * 190 + ".com",
])
def test_invalid_email_is_rejected(email):
    with pytest.raises(ValidationError) as exc_info:
        User(username="alice", email=email)

    assert exc_info.value.errors()[0]["loc"] == ("email",)


def test_location_is_kept_when_given():
    user = User(username="alice", email=EMAIL, location={"latitude": 40.4168, "longitude": -3.7038})

    assert user.location == Location(latitude=40.4168, longitude=-3.7038)


# --- location -------------------------------------------------------------------------------------

@pytest.mark.parametrize("latitude, longitude", [(0, 0), (90, 180), (-90, -180), (40.4168, -3.7038)])
def test_location_accepts_coordinates_within_range(latitude, longitude):
    location = Location(latitude=latitude, longitude=longitude)

    assert (location.latitude, location.longitude) == (latitude, longitude)


@pytest.mark.parametrize("field, value, error_type", [
    ("latitude", 90.0001, "less_than_equal"),
    ("latitude", -90.0001, "greater_than_equal"),
    ("longitude", 180.0001, "less_than_equal"),
    ("longitude", -180.0001, "greater_than_equal"),
    ("latitude", float("nan"), "less_than_equal"),
    ("longitude", float("inf"), "less_than_equal"),
    ("latitude", "40.4", "float_type"),
    ("longitude", True, "float_type"),
    ("latitude", None, "float_type"),
])
def test_location_rejects_invalid_coordinates(field, value, error_type):
    coordinates = {"latitude": 0.0, "longitude": 0.0, field: value}

    with pytest.raises(ValidationError) as exc_info:
        Location(**coordinates)

    assert [(error["loc"], error["type"]) for error in exc_info.value.errors()] == [((field,), error_type)]


@pytest.mark.parametrize("coordinates, expected_errors", [
    ({"latitude": 1.0}, [(("longitude",), "missing")]),
    ({"longitude": 1.0}, [(("latitude",), "missing")]),
    ({}, [(("latitude",), "missing"), (("longitude",), "missing")]),
    ({"latitude": 1.0, "longitude": 2.0, "altitude": 3.0}, [(("altitude",), "extra_forbidden")]),
])
def test_location_must_have_exactly_latitude_and_longitude(coordinates, expected_errors):
    with pytest.raises(ValidationError) as exc_info:
        Location(**coordinates)

    assert [(error["loc"], error["type"]) for error in exc_info.value.errors()] == expected_errors
