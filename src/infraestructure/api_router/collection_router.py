

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from src.application.ports.inbound.collection_port_in import CollectionPortIn
from src.domain.api_dto.collection_dto import CREATE_COLLECTION_EXAMPLES, CollectionResponse, CreateCollectionRequest
from src.domain.api_dto.error_dto import error_response
from src.domain.exception.item_exception import ItemsNotCollectableError, ItemsNotFoundError
from src.domain.exception.user_exception import UserCannotOwnCollectionsError, UserNotFoundError
from src.infraestructure.bootstrap.dependencies import get_collection_service

router = APIRouter(prefix="/users/{username}", tags=["collections"])

CollectionServiceDep = Annotated[CollectionPortIn, Depends(get_collection_service)]
OwnerPath = Annotated[str, Path(description="Username of the owner.", examples=["alice"])]
ItemIdPath = Annotated[int, Path(gt=0, description="Id of one of the user's items.", examples=[1])]

_NOT_FOUND = (UserNotFoundError, ItemsNotFoundError)
_NOT_ALLOWED = (UserCannotOwnCollectionsError, ItemsNotCollectableError)


@router.post(
    "/collections",
    status_code=status.HTTP_201_CREATED,
    summary="Create a collection",
    response_description="The created collection, with its items.",
    responses={
        404: error_response("The user does not exist, or some items do not exist or belong to another user.",
                            "Items 7, 8 not found for user 'alice'."),
        409: error_response("The user's status or some items' status does not allow creating the collection.",
                            "Items cannot be added to a collection because of their status: 3 (disable)."),
    },
)
def create_collection(
    username: OwnerPath,
    request: Annotated[CreateCollectionRequest, Body(openapi_examples=CREATE_COLLECTION_EXAMPLES)],
    collection_service: CollectionServiceDep,
) -> CollectionResponse:
    """
    Groups one or more of the user's items into a new collection.

    * **name**: mandatory, 1-200 characters, does not need to be unique.
    * **description**: mandatory, 1-2000 characters.
    * **item_ids**: one or more ids (without repetitions) of items that belong to the user.

    Only users with status `in_progress` or `active` can create collections, and only items with status
    `validating` or `able` can be added (**409** otherwise).
    """
    try:
        collection = collection_service.create_collection(username, request.name, request.description, request.item_ids)
    except _NOT_FOUND as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except _NOT_ALLOWED as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CollectionResponse.from_domain(collection)


@router.get(
    "/collections",
    summary="List the collections of a user",
    response_description="The user's collections with their items, oldest first (empty if the user has none).",
    responses={404: error_response("User not found.", "User 'ghost' not found.")},
)
def list_collections(username: OwnerPath, collection_service: CollectionServiceDep) -> list[CollectionResponse]:
    """
    Returns the collections of the user in the URL, oldest first, each with its items.
    """
    try:
        collections = collection_service.list_collections(username)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [CollectionResponse.from_domain(collection) for collection in collections]


@router.get(
    "/items/{item_id}/collections",
    summary="List the collections that include an item",
    response_description="The collections that include the item, oldest first (empty if none).",
    responses={404: error_response("The user does not exist, or the item does not exist or belongs to another user.",
                                   "Item 7 not found for user 'alice'.")},
)
def list_item_collections(
    username: OwnerPath, item_id: ItemIdPath, collection_service: CollectionServiceDep,
) -> list[CollectionResponse]:
    """
    Returns the collections of the user in the URL that include the given item, oldest first.
    """
    try:
        collections = collection_service.list_item_collections(username, item_id)
    except _NOT_FOUND as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [CollectionResponse.from_domain(collection) for collection in collections]
