

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enum.item_status import ItemStatus
from src.domain.model.item_collection import Barcode, ItemCollection, ItemDescription, ItemName


class CreateItemRequest(BaseModel):
    """
    Body of an item creation request. The owner comes from the URL and the status is assigned by the
    application, so sending them is rejected.
    """
    model_config = ConfigDict(extra="forbid")

    name: ItemName = Field(..., description="Name of item.", examples=["Sample DVD"])
    description: ItemDescription = Field(..., description="Description of item.", examples=["DVD, region 2, PAL."])
    barcode: Barcode = Field(
        ..., description="EAN/UPC/GTIN barcode as a number, with a valid check digit.", examples=[5050582500417])


class ItemResponse(BaseModel):
    """
    An item as returned by the API. The owner is identified by username only, so the owner's
    personal data is not repeated in every item.
    """
    id: int = Field(..., description="Identifier of the item, e.g. to add it to a collection.", examples=[1])
    name: str = Field(..., examples=["Sample DVD"])
    description: str = Field(..., examples=["DVD, region 2, PAL."])
    barcode: int = Field(..., examples=[5050582500417])
    status: ItemStatus = Field(
        ..., description="New items are `validating` until their verification completes.", examples=["validating"])
    owner: str = Field(..., description="Username of the owner.", examples=["alice"])

    @classmethod
    def from_domain(cls, item: ItemCollection) -> "ItemResponse":
        return cls(
            id=item.id,
            name=item.name,
            description=item.description,
            barcode=item.barcode,
            status=item.status,
            owner=item.owner.username,
        )


# Named examples shown in Swagger UI / ReDoc for the create-item request body.
CREATE_ITEM_EXAMPLES = {
    "dvd": {
        "summary": "DVD (EAN-13)",
        "description": "Barcode of the sample DVD in src/resources/sample_dvd/barcode.jpg.",
        "value": {"name": "Sample DVD", "description": "DVD, region 2, PAL.", "barcode": 5050582500417},
    },
    "book": {
        "summary": "Book (ISBN-13)",
        "description": "An ISBN-13 is an EAN-13 barcode.",
        "value": {"name": "A book", "description": "Hardcover, first edition.", "barcode": 9780306406157},
    },
}
