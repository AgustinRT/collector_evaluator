

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.domain.model.location import Location
from src.domain.model.user import Username


class CreateUserRequest(BaseModel):
    """
    Body of a user creation request. Status and evaluation are assigned by the application, so
    sending them is rejected.
    """
    model_config = ConfigDict(extra="forbid")

    username: Username = Field(..., description="Name of user, is mandatory and unique.", examples=["alice"])
    email: EmailStr = Field(
        ..., description="Email address of user, is mandatory and must be valid.", examples=["alice@example.com"])
    location: Location | None = Field(None, description="Geolocation of user, optional. Validated if given.")


# Named examples shown in Swagger UI / ReDoc for the create-user request body.
CREATE_USER_EXAMPLES = {
    "minimal": {
        "summary": "Username and email only",
        "value": {"username": "alice", "email": "alice@example.com"},
    },
    "with_location": {
        "summary": "With geolocation",
        "description": "Optional location in decimal degrees (here, Madrid).",
        "value": {"username": "bob", "email": "bob@example.com", "location": {"latitude": 40.4168, "longitude": -3.7038}},
    },
}
