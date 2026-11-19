import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


@pytest.fixture(scope="session")
def client():
    with TestClient(create_app()) as c:
        yield c
