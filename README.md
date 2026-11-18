# collector_evaluator

## 1. Abstract
This is a microservice implemented in Python using FastAPI, designed to analyze collectible items. Its purpose is to enable the creation and management of users, as well as the creation and processing of information regarding collectible items (DVDs, video games, music, etc.). These items can be grouped into collections and assigned to a user, along with their specific location.
The service must retrieve information about the items, validate it against various external verification APIs, evaluate each item, and persist the data in a PostgreSQL database. Furthermore, it must be possible to list these collections for each user.

## 2. Technologies & Design Patterns

### Technologies
*   **Language:** Python 3.14 (as per environment).
*   **Framework:** [FastAPI](https://fastapi.tiangolo.com/) for the REST API layer.
*   **Asynchronous Communication:** [Kafka-python](https://github.com/dpereira/kafka-python) for event-driven updates.
*   **Persistence:** PostgreSQL 16
*   **Data Validation:** [Pydantic](https://docs.pydantic.dev/) for Domain Models, DTOs, and API schemas.
*   **Dependency Management:** [UV](https://github.com/astral-sh/uv) for project and environment management.

## Quick Start

### Start the development server

```bash
uv run fastapi dev
```

Visit http://localhost:8000

### Deploy to FastAPI Cloud

Sign up and log in at https://fastapicloud.com, then deploy with:

```bash
uv run fastapi deploy
```

## Project Structure

- `main.py` - Your FastAPI application
- `pyproject.toml` - Project dependencies

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
