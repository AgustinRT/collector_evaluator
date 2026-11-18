

from typing import List

from pydantic import BaseModel, Field

from src.domain.model.item_collection import ItemCollection
from src.domain.model.user import User


class Collection(BaseModel):
    """
    """
    name: str = Field(..., description="Name of collection.")
    description: str = Field(..., description="Description of collection.")
    owner: User = Field(..., description="User owner of item")
    items: List[ItemCollection] = Field(..., description="List of items that compose the collection")