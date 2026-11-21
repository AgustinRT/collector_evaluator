

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from src.domain.enum.item_status import ItemStatus
from src.domain.enum.user_status import UserStatus
from src.domain.model.item_collection import ItemCollection
from src.domain.model.user import User

CollectionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
"""Mandatory, non-blank, at most 200 characters, not unique. Surrounding whitespace is removed."""

CollectionDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
"""Mandatory, non-blank, at most 2000 characters. Surrounding whitespace is removed."""

# Who and what can be grouped when a collection is CREATED. Users and items are not activated/verified
# yet (no process moves them to ACTIVE / ABLE), so the states on the way there are accepted too.
# Tighten to {ACTIVE} / {ABLE} once those processes exist.
COLLECTION_OWNER_STATUSES = frozenset({UserStatus.IN_PROGRESS, UserStatus.ACTIVE})
COLLECTABLE_ITEM_STATUSES = frozenset({ItemStatus.VALIDATING, ItemStatus.ABLE})


class Collection(BaseModel):
    """
    A named group of one or more items of the same user.

    Only structural rules are enforced here, because they always hold. The statuses required to create a
    collection are checked by the use case instead: an item may be disabled later, and the collections
    that contain it must still be readable.
    """
    id: int | None = Field(None, description="Identifier assigned by the database when the collection is stored.")
    name: CollectionName = Field(..., description="Name of collection.")
    description: CollectionDescription = Field(..., description="Description of collection.")
    owner: User = Field(..., description="User owner of the collection and of all its items.")
    items: list[ItemCollection] = Field(..., min_length=1, description="Items that compose the collection.")

    @model_validator(mode="after")
    def _items_belong_to_owner_once(self) -> "Collection":
        foreign = [item.id for item in self.items if item.owner.username != self.owner.username]
        if foreign:
            raise ValueError(f"items {foreign} do not belong to user '{self.owner.username}'")
        ids = [item.id for item in self.items if item.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("an item cannot appear twice in a collection")
        return self
