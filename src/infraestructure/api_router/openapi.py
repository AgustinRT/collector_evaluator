"""
OpenAPI metadata. FastAPI serves it as Swagger UI (/docs), ReDoc (/redoc) and the raw spec (/openapi.json).
"""

import json

from fastapi import FastAPI

API_TITLE = "Collector Evaluator API"

# Keep in sync with the version in pyproject.toml (a test checks it).
API_VERSION = "0.1.0"

API_DESCRIPTION = """
Microservice to register **users**, their collectible **items** (DVDs, video games, music, books...) and the
**collections** that group them.

## Workflow
1. **Create a user** with `POST /users`. It starts with status `in_progress` and evaluation `0.0`.
2. **Add items** to the user with `POST /users/{username}/items`. Each item starts with status `validating`.
3. **List the user's items** with `GET /users/{username}/items`. Each item has an `id`.
4. **Group items into a collection** with `POST /users/{username}/collections`, passing the items' ids.
5. **List the collections** of a user with `GET /users/{username}/collections`, or the collections that include
   an item with `GET /users/{username}/items/{item_id}/collections`.

## Validation
Invalid requests are rejected with **422** and a description of each invalid field:
* **username**: mandatory, 1-150 characters, unique (a duplicate returns **409**).
* **email**: mandatory, must be a valid address.
* **location**: optional; if given, `latitude` must be in [-90, 90] and `longitude` in [-180, 180].
* **barcode**: a number with up to 14 digits and a valid EAN/UPC/GTIN check digit.
* **collection**: mandatory `name` (not unique) and `description`, and one or more ids of the user's own items.
  Only users `in_progress`/`active` and items `validating`/`able` qualify (**409** otherwise).
* Fields assigned by the service (`status`, `evaluation`, item `owner`) cannot be sent.
"""

OPENAPI_TAGS = [
    {"name": "users", "description": "Registration and lookup of users."},
    {"name": "items", "description": "Collectible items owned by a user."},
    {"name": "collections", "description": "Named groups of one or more items of a user."},
    {"name": "status", "description": "Service availability."},
]

LICENSE_INFO = {"name": "MIT", "identifier": "MIT"}


def openapi_json(app: FastAPI) -> str:
    """
    The OpenAPI spec of ``app`` as stable, human-readable JSON (the content of docs/openapi.json).
    """
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
