
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.domain.enum.user_status import UserStatus

_NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class User(BaseModel):
    """
    """
    username: Annotated[_NonBlankStr, StringConstraints(max_length=150)] = Field(
        ..., description="Name of user, is mandatory.")
    status: UserStatus = Field(..., description="state of user")
    evaluation: float = Field(..., description="valoration of user")