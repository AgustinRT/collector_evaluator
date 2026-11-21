

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Body of an error response (except validation errors, which use FastAPI's standard 422 format).
    """
    detail: str = Field(..., description="Reason of the error.")


def error_response(description: str, example_detail: str) -> dict:
    """
    OpenAPI documentation of an error response, with its own example message.
    """
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {"application/json": {"example": {"detail": example_detail}}},
    }
