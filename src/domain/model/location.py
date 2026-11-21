

from pydantic import BaseModel, ConfigDict, Field


class Location(BaseModel):
    """
    Geolocation (WGS84 decimal degrees) provided by the user. Both coordinates are required, must be
    numbers (not strings or booleans) and must be within their valid range.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    latitude: float = Field(
        ..., strict=True, ge=-90, le=90, description="Latitude in degrees, -90 to 90.", examples=[40.4168])
    longitude: float = Field(
        ..., strict=True, ge=-180, le=180, description="Longitude in degrees, -180 to 180.", examples=[-3.7038])
