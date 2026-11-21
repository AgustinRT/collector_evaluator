

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from src.application.ports.inbound.user_port_in import UserPortIn
from src.domain.api_dto.error_dto import error_response
from src.domain.api_dto.user_dto import CREATE_USER_EXAMPLES, CreateUserRequest
from src.domain.exception.user_exception import UserAlreadyExistsError, UserNotFoundError
from src.domain.model.user import User
from src.infraestructure.bootstrap.dependencies import get_user_service

router = APIRouter(prefix="/users", tags=["users"])

UserServiceDep = Annotated[UserPortIn, Depends(get_user_service)]
UsernamePath = Annotated[str, Path(description="Username of the user.", examples=["alice"])]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    response_description="The created user.",
    responses={409: error_response("Username already exists.", "User 'alice' already exists.")},
)
def create_user(
    request: Annotated[CreateUserRequest, Body(openapi_examples=CREATE_USER_EXAMPLES)],
    user_service: UserServiceDep,
) -> User:
    """
    Registers a new user.

    * **username**: mandatory, 1-150 characters (surrounding spaces are removed), unique.
    * **email**: mandatory, must be a valid email address.
    * **location**: optional; `latitude` in [-90, 90] and `longitude` in [-180, 180], both required.

    The user is created with status `in_progress` (until its validation completes) and evaluation `0.0`;
    these fields cannot be sent.
    """
    try:
        return user_service.create_user(
            User(username=request.username, email=request.email, location=request.location)
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/{username}",
    summary="Get a user",
    response_description="The user.",
    responses={404: error_response("User not found.", "User 'ghost' not found.")},
)
def get_user(username: UsernamePath, user_service: UserServiceDep) -> User:
    """
    Returns the user with the given username.
    """
    try:
        return user_service.get_user(username)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
