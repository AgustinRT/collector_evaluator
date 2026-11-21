
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from src.domain.enum.user_status import UserStatus
from src.domain.model.location import Location

Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
"""Mandatory, non-blank, at most 150 characters. Surrounding whitespace is removed."""


class User(BaseModel):
    """
    A user. The defaults of status and evaluation are the state every new user starts in.
    """
    username: Username = Field(..., description="Name of user, is mandatory and unique.", examples=["alice"])
    email: EmailStr = Field(
        ..., description="Email address of user, is mandatory and must be valid.", examples=["alice@example.com"])
    location: Location | None = Field(None, description="Geolocation given at registration, optional.")
    status: UserStatus = Field(
        UserStatus.IN_PROGRESS,
        description="State of user. New users are IN_PROGRESS until their validation completes, then ACTIVE.",
        examples=["in_progress"])
    evaluation: float = Field(0.0, description="Valoration of user. New users start at 0.0.", examples=[0.0])
