from unittest.mock import create_autospec

import pytest

from src.application.ports.outbound.user_port_out import UserPortOut
from src.application.use_cases.user_service import UserService
from src.domain.enum.user_status import UserStatus
from src.domain.exception.user_exception import UserAlreadyExistsError, UserNotFoundError
from src.domain.model.location import Location
from src.domain.model.user import User

MADRID = Location(latitude=40.4168, longitude=-3.7038)


@pytest.fixture
def user_port_out():
    port = create_autospec(UserPortOut, instance=True)
    port.get_user.return_value = None
    port.create_user.side_effect = lambda user: user
    return port


def _candidate(**fields) -> User:
    return User(**({"username": "alice", "email": "alice@example.com"} | fields))


@pytest.mark.parametrize("location", [MADRID, None])
def test_create_user_persists_username_email_and_location_in_progress_with_zero_evaluation(user_port_out, location):
    created = UserService(user_port_out).create_user(_candidate(location=location))

    expected = User(
        username="alice", email="alice@example.com", location=location,
        status=UserStatus.IN_PROGRESS, evaluation=0.0,
    )
    user_port_out.create_user.assert_called_once_with(expected)
    assert created == expected


def test_create_user_ignores_status_and_evaluation_from_the_caller(user_port_out):
    UserService(user_port_out).create_user(_candidate(status=UserStatus.ACTIVE, evaluation=9.5))

    (persisted,), _ = user_port_out.create_user.call_args
    assert persisted.status is UserStatus.IN_PROGRESS
    assert persisted.evaluation == 0.0


def test_create_user_checks_the_username_is_free_before_persisting(user_port_out, alice):
    user_port_out.get_user.return_value = alice

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        UserService(user_port_out).create_user(_candidate(email="other@example.com"))

    assert exc_info.value.username == "alice"
    user_port_out.get_user.assert_called_once_with("alice")
    user_port_out.create_user.assert_not_called()


def test_create_user_propagates_duplicate_detected_by_the_database(user_port_out):
    # Two simultaneous requests: both pass the check, the database rejects the second insert.
    user_port_out.create_user.side_effect = UserAlreadyExistsError("alice")

    with pytest.raises(UserAlreadyExistsError):
        UserService(user_port_out).create_user(_candidate())


def test_get_user_returns_user(user_port_out, alice):
    user_port_out.get_user.return_value = alice

    assert UserService(user_port_out).get_user("alice") == alice
    user_port_out.get_user.assert_called_once_with("alice")


def test_get_user_raises_when_missing(user_port_out):
    with pytest.raises(UserNotFoundError):
        UserService(user_port_out).get_user("ghost")
