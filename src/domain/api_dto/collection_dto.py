

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.api_dto.item_collection_dto import ItemResponse
from src.domain.model.collection import Collection, CollectionDescription, CollectionName

ItemId = Annotated[int, Field(strict=True, gt=0)]


class CreateCollectionRequest(BaseModel):
    """
    Body of a collection creation request. The owner comes from the URL, so sending it is rejected.
    """
    model_config = ConfigDict(extra="forbid")

    name: CollectionName = Field(..., description="Name of collection (does not need to be unique).",
                                 examples=["Favourite films"])
    description: CollectionDescription = Field(..., description="Description of collection.",
                                               examples=["The DVDs I would never sell."])
    item_ids: list[ItemId] = Field(..., min_length=1, description="Ids of one or more of the user's items.",
                                   examples=[[1, 2]])

    @field_validator("item_ids")
    @classmethod
    def _no_duplicates(cls, item_ids: list[int]) -> list[int]:
        duplicates = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1})
        if duplicates:
            raise ValueError(f"item ids must not be repeated: {duplicates}")
        return item_ids


class CollectionResponse(BaseModel):
    """
    A collection as returned by the API, with its items. The owner is identified by username only.
    """
    id: int = Field(..., description="Identifier of the collection.", examples=[1])
    name: str = Field(..., examples=["Favourite films"])
    description: str = Field(..., examples=["The DVDs I would never sell."])
    owner: str = Field(..., description="Username of the owner.", examples=["alice"])
    items: list[ItemResponse] = Field(..., description="Items of the collection, ordered by id.")

    @classmethod
    def from_domain(cls, collection: Collection) -> "CollectionResponse":
        return cls(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            owner=collection.owner.username,
            items=[ItemResponse.from_domain(item) for item in collection.items],
        )


# Named examples shown in Swagger UI / ReDoc for the create-collection request body.
CREATE_COLLECTION_EXAMPLES = {
    "two_items": {
        "summary": "Collection with two items",
        "description": "`item_ids` are the `id` values returned when the items were created.",
        "value": {"name": "Favourite films", "description": "The DVDs I would never sell.", "item_ids": [1, 2]},
    },
    "single_item": {
        "summary": "Collection with one item",
        "value": {"name": "Signed copies", "description": "Items signed by the author.", "item_ids": [1]},
    },
}
