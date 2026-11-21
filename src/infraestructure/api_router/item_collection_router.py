

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from src.application.ports.inbound.item_collection_port_in import ItemCollectionPortIn
from src.domain.api_dto.error_dto import error_response
from src.domain.api_dto.item_collection_dto import CREATE_ITEM_EXAMPLES, CreateItemRequest, ItemResponse
from src.domain.exception.user_exception import UserNotFoundError
from src.infraestructure.bootstrap.dependencies import get_item_collection_service

router = APIRouter(prefix="/users/{username}/items", tags=["items"])

ItemCollectionServiceDep = Annotated[ItemCollectionPortIn, Depends(get_item_collection_service)]
OwnerPath = Annotated[str, Path(description="Username of the owner.", examples=["alice"])]

_USER_NOT_FOUND = {404: error_response("User not found.", "User 'ghost' not found.")}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to a user",
    response_description="The created item.",
    responses=_USER_NOT_FOUND,
)
def create_item(
    username: OwnerPath,
    request: Annotated[CreateItemRequest, Body(openapi_examples=CREATE_ITEM_EXAMPLES)],
    item_service: ItemCollectionServiceDep,
) -> ItemResponse:
    """
    Validates a new item and registers it for the user in the URL.

    * **name**: mandatory, 1-200 characters.
    * **description**: mandatory, 1-2000 characters.
    * **barcode**: EAN-8, UPC-A, EAN-13 (including ISBN-13) or GTIN-14 as a JSON number (not a string),
      with a valid check digit. Leading zeros cannot be written in a JSON number: send UPC-A
      `012345678905` as `12345678905`.

    The item is created with status `validating`; the status and owner cannot be sent.
    """
    try:
        item = item_service.create_item(username, request.name, request.description, request.barcode)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ItemResponse.from_domain(item)


@router.get(
    "",
    summary="List the items of a user",
    response_description="The user's items, oldest first (empty if the user has none).",
    responses=_USER_NOT_FOUND,
)
def list_items(username: OwnerPath, item_service: ItemCollectionServiceDep) -> list[ItemResponse]:
    """
    Returns the items of the user in the URL, oldest first.
    """
    try:
        items = item_service.list_items(username)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ItemResponse.from_domain(item) for item in items]
