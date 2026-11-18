

from pydantic import BaseModel, Field

from src.domain.enum.item_status import ItemStatus
from src.domain.model.user import User


class ItemCollection(BaseModel):
    """
    """
    name: str = Field(..., description="Name of item.")
    description: str = Field(..., description="Description of item.")
    status: ItemStatus = Field(..., description="Status of item.")
    owner: User = Field(..., description="User owner of item")
    barcode: int = Field(..., description="Number with the barcode")
