
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# --------------------------------------------------
# TEST ENVIRONMENT CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite:///./test_resolveai.db"
os.environ["QDRANT_PATH"] = "./data/test_qdrant"
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""


# --------------------------------------------------
# APPLICATION IMPORTS
# --------------------------------------------------

from app.main import app
from app.database import SessionLocal
from app.models import User
from app.security import create_access_token


# --------------------------------------------------
# AUTHENTICATED TEST CLIENT
# --------------------------------------------------

@pytest.fixture
def client():
    with TestClient(app) as c:

        # Retrieve the Admin created by application lifespan.
        db = SessionLocal()

        try:
            admin = (
                db.query(User)
                .filter(User.role == "Admin")
                .first()
            )

            if admin is None:
                pytest.fail(
                    "Test Admin account was not created "
                    "during application startup."
                )

            if not admin.is_active:
                pytest.fail(
                    "Test Admin account is inactive."
                )

            # Generate a valid JWT for the Admin.
            access_token = create_access_token(admin.id)

        finally:
            db.close()

        # Automatically authenticate existing API tests.
        c.headers.update({
            "Authorization": f"Bearer {access_token}"
        })

        yield c
