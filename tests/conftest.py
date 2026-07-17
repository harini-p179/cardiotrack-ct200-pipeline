import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import Base, get_db
from app.models.models import Document, Version, SectionNode, Selection
from app.schemas.schemas import TestCaseCreate, TestCaseResponse
from main import app

from sqlalchemy.pool import StaticPool

# Prevent pytest from collecting these schemas as test classes
TestCaseCreate.__test__ = False
TestCaseResponse.__test__ = False

# In-memory SQLite for isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Isolated database session for each test case."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient fixture with overridden DB dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
