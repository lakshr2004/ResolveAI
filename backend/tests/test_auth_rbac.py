
import uuid

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, create_access_token


# --------------------------------------------------
# TEST HELPERS
# --------------------------------------------------

def ticket_payload():
    return {
        "customer_name": "Asha Sharma",
        "customer_email": "asha@example.com",
        "subject": "Cannot log in to my account",
        "description": (
            "I reset my password but still cannot "
            "sign in to my account."
        ),
    }


def create_test_user(role):
    """
    Create a test user with the requested role
    and return a valid JWT access token.
    """

    db = SessionLocal()

    try:
        unique_email = (
            f"{role.lower()}-{uuid.uuid4().hex[:10]}@example.com"
        )

        user = User(
            email=unique_email,
            full_name=f"Test {role}",
            password_hash=hash_password("TestPassword123!"),
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return create_access_token(user.id)

    finally:
        db.close()


def create_ticket(client):
    response = client.post(
        "/api/tickets",
        json=ticket_payload(),
    )

    assert response.status_code == 201

    return response.json()["ticket_id"]


def add_internal_note(client, ticket_id):
    response = client.post(
        f"/api/agents/{ticket_id}/notes",
        json={
            "note": "Internal investigation note",
        },
    )

    assert response.status_code == 201


# --------------------------------------------------
# AUTHENTICATION TESTS
# --------------------------------------------------

def test_unauthenticated_request_returns_401(client):
    """
    Protected endpoints must reject requests
    without a JWT access token.
    """

    client.headers.pop("Authorization", None)

    response = client.get("/api/tickets")

    assert response.status_code == 401


# --------------------------------------------------
# ROLE AUTHORIZATION TESTS
# --------------------------------------------------

def test_viewer_cannot_access_admin_only_endpoint(client):
    """
    Viewer must receive 403 on Admin-only endpoints.
    """

    viewer_token = create_test_user("Viewer")

    client.headers.update({
        "Authorization": f"Bearer {viewer_token}"
    })

    response = client.get("/api/system/status")

    assert response.status_code == 403


# --------------------------------------------------
# VIEWER DATA PRIVACY TESTS
# --------------------------------------------------

def test_viewer_cannot_see_customer_pii_or_internal_notes(client):
    """
    Viewer can access ticket details but must not
    receive customer PII or internal notes.
    """

    ticket_id = create_ticket(client)

    add_internal_note(client, ticket_id)

    viewer_token = create_test_user("Viewer")

    client.headers.update({
        "Authorization": f"Bearer {viewer_token}"
    })

    response = client.get(
        f"/api/tickets/{ticket_id}"
    )

    assert response.status_code == 200

    ticket = response.json()

    assert ticket["ticket_id"] == ticket_id
    assert ticket["customer_name"] is None
    assert ticket["customer_email"] is None
    assert ticket["notes"] == []
    assert ticket["subject"] == ticket_payload()["subject"]


# --------------------------------------------------
# AGENT DATA ACCESS TESTS
# --------------------------------------------------

def test_agent_can_see_customer_pii_and_internal_notes(client):
    """
    Agent must retain access to customer information
    and internal notes.
    """

    ticket_id = create_ticket(client)

    agent_token = create_test_user("Agent")

    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    add_internal_note(client, ticket_id)

    response = client.get(
        f"/api/tickets/{ticket_id}"
    )

    assert response.status_code == 200

    ticket = response.json()

    assert ticket["customer_name"] == "Asha Sharma"
    assert ticket["customer_email"] == "asha@example.com"
    assert len(ticket["notes"]) == 1

    assert (
        ticket["notes"][0]["note"]
        == "Internal investigation note"
    )

    assert ticket["notes"][0]["author"] == "Test Agent"


# --------------------------------------------------
# ADMIN DATA ACCESS TESTS
# --------------------------------------------------

def test_admin_can_see_customer_pii_and_internal_notes(client):
    """
    Admin must retain full ticket visibility.
    """

    ticket_id = create_ticket(client)

    add_internal_note(client, ticket_id)

    response = client.get(
        f"/api/tickets/{ticket_id}"
    )

    assert response.status_code == 200

    ticket = response.json()

    assert ticket["customer_name"] == "Asha Sharma"
    assert ticket["customer_email"] == "asha@example.com"
    assert len(ticket["notes"]) == 1

    assert (
        ticket["notes"][0]["note"]
        == "Internal investigation note"
    )

    assert ticket["notes"][0]["author"] == "ResolveAI Admin"


# --------------------------------------------------
# USER MANAGEMENT TESTS
# --------------------------------------------------

def test_admin_can_create_agent_user(client):
    """
    Admin should be able to create an Agent account.
    """

    unique_email = f"agent-{uuid.uuid4().hex[:10]}@example.com"

    response = client.post(
        "/api/users",
        json={
            "email": unique_email,
            "full_name": "New Test Agent",
            "password": "SecurePassword123!",
            "role": "Agent",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == unique_email
    assert data["full_name"] == "New Test Agent"
    assert data["role"] == "Agent"
    assert data["is_active"] is True

    assert "password_hash" not in data
    assert "password" not in data


def test_admin_cannot_create_duplicate_email(client):
    """
    Duplicate email should return HTTP 409.
    """

    unique_email = f"duplicate-{uuid.uuid4().hex[:10]}@example.com"

    payload = {
        "email": unique_email,
        "full_name": "Duplicate Test User",
        "password": "SecurePassword123!",
        "role": "Agent",
    }

    first_response = client.post(
        "/api/users",
        json=payload,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/users",
        json=payload,
    )

    assert second_response.status_code == 409


def test_agent_cannot_create_users(client):
    """
    Agent must not have permission to create users.
    """

    agent_token = create_test_user("Agent")

    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    unique_email = f"unauthorized-{uuid.uuid4().hex[:10]}@example.com"

    response = client.post(
        "/api/users",
        json={
            "email": unique_email,
            "full_name": "Unauthorized User",
            "password": "SecurePassword123!",
            "role": "Viewer",
        },
    )

    assert response.status_code == 403


# --------------------------------------------------
# USER LISTING TESTS
# --------------------------------------------------

def test_admin_can_list_users(client):
    """
    Admin should be able to list all users.
    """

    response = client.get("/api/users")

    assert response.status_code == 200

    users = response.json()

    assert isinstance(users, list)
    assert len(users) >= 1

    admin = next(
        (user for user in users if user["role"] == "Admin"),
        None,
    )

    assert admin is not None
    assert admin["email"] == "admin@resolveai.local"

    # Password data must never be exposed
    for user in users:
        assert "password" not in user
        assert "password_hash" not in user


def test_agent_cannot_list_users(client):
    """
    Agent must not access user management.
    """

    agent_token = create_test_user("Agent")

    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    response = client.get("/api/users")

    assert response.status_code == 403


def test_viewer_cannot_list_users(client):
    """
    Viewer must not access user management.
    """

    viewer_token = create_test_user("Viewer")

    client.headers.update({
        "Authorization": f"Bearer {viewer_token}"
    })

    response = client.get("/api/users")

    assert response.status_code == 403


# --------------------------------------------------
# USER ROLE UPDATE TESTS
# --------------------------------------------------

def test_admin_can_update_agent_role_to_viewer(client):
    """
    Admin should be able to change an Agent's role to Viewer.
    """

    unique_email = f"role-update-{uuid.uuid4().hex[:10]}@example.com"

    create_response = client.post(
        "/api/users",
        json={
            "email": unique_email,
            "full_name": "Role Update User",
            "password": "SecurePassword123!",
            "role": "Agent",
        },
    )

    assert create_response.status_code == 201

    user_id = create_response.json()["id"]

    response = client.patch(
        f"/api/users/{user_id}/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "Viewer"


def test_admin_can_update_viewer_role_to_agent(client):
    """
    Admin should be able to promote a Viewer to Agent.
    """

    unique_email = f"promotion-{uuid.uuid4().hex[:10]}@example.com"

    create_response = client.post(
        "/api/users",
        json={
            "email": unique_email,
            "full_name": "Promotion User",
            "password": "SecurePassword123!",
            "role": "Viewer",
        },
    )

    assert create_response.status_code == 201

    user_id = create_response.json()["id"]

    response = client.patch(
        f"/api/users/{user_id}/role",
        json={"role": "Agent"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "Agent"


def test_agent_cannot_update_user_role(client):
    """
    Agent must not be allowed to update user roles.
    """

    agent_token = create_test_user("Agent")

    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    response = client.patch(
        "/api/users/999999/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 403


def test_viewer_cannot_update_user_role(client):
    """
    Viewer must not be allowed to update user roles.
    """

    viewer_token = create_test_user("Viewer")

    client.headers.update({
        "Authorization": f"Bearer {viewer_token}"
    })

    response = client.patch(
        "/api/users/999999/role",
        json={"role": "Agent"},
    )

    assert response.status_code == 403


def test_admin_cannot_change_own_role(client):
    """
    Admin must not be allowed to downgrade their own role.
    """

    from app.models import User
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        admin = db.query(User).filter(
            User.role == "Admin"
        ).first()

        assert admin is not None
        admin_id = admin.id

    finally:
        db.close()

    response = client.patch(
        f"/api/users/{admin_id}/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 400


def test_admin_cannot_change_another_admin_role(client):
    """
    Existing Admin accounts must be protected from role downgrade.
    """

    from app.models import User
    from app.database import SessionLocal
    from app.security import hash_password

    db = SessionLocal()

    try:
        another_admin = User(
            email=f"another-admin-{uuid.uuid4().hex[:10]}@example.com",
            full_name="Another Admin",
            password_hash=hash_password("SecurePassword123!"),
            role="Admin",
            is_active=True,
        )

        db.add(another_admin)
        db.commit()
        db.refresh(another_admin)

        admin_id = another_admin.id

    finally:
        db.close()

    response = client.patch(
        f"/api/users/{admin_id}/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 403    


# --------------------------------------------------
# USER ACCOUNT STATUS TESTS
# --------------------------------------------------

def test_admin_can_deactivate_agent(client):
    email = f"deactivate-{uuid.uuid4().hex[:10]}@example.com"

    create_response = client.post(
        "/api/users",
        json={
            "email": email,
            "full_name": "Deactivate Agent",
            "password": "SecurePassword123!",
            "role": "Agent",
        },
    )

    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    response = client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_can_activate_viewer(client):
    email = f"activate-{uuid.uuid4().hex[:10]}@example.com"

    create_response = client.post(
        "/api/users",
        json={
            "email": email,
            "full_name": "Activate Viewer",
            "password": "SecurePassword123!",
            "role": "Viewer",
        },
    )

    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    # First deactivate
    client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": False},
    )

    response = client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": True},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_agent_cannot_update_user_status(client):
    agent_token = create_test_user("Agent")

    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    response = client.patch(
        "/api/users/999999/status",
        json={"is_active": False},
    )

    assert response.status_code == 403


def test_viewer_cannot_update_user_status(client):
    viewer_token = create_test_user("Viewer")

    client.headers.update({
        "Authorization": f"Bearer {viewer_token}"
    })

    response = client.patch(
        "/api/users/999999/status",
        json={"is_active": False},
    )

    assert response.status_code == 403


def test_admin_cannot_deactivate_own_account(client):
    from app.models import User
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        admin = db.query(User).filter(
            User.role == "Admin"
        ).first()

        assert admin is not None
        admin_id = admin.id

    finally:
        db.close()

    response = client.patch(
        f"/api/users/{admin_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 400


def test_admin_cannot_deactivate_another_admin(client):
    from app.models import User
    from app.database import SessionLocal
    from app.security import hash_password

    db = SessionLocal()

    try:
        another_admin = User(
            email=f"protected-admin-{uuid.uuid4().hex[:10]}@example.com",
            full_name="Protected Admin",
            password_hash=hash_password("SecurePassword123!"),
            role="Admin",
            is_active=True,
        )

        db.add(another_admin)
        db.commit()
        db.refresh(another_admin)

        admin_id = another_admin.id

    finally:
        db.close()

    response = client.patch(
        f"/api/users/{admin_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 403    

# --------------------------------------------------
# INACTIVE USER JWT SECURITY TEST
# --------------------------------------------------

def test_deactivated_user_cannot_access_api_with_existing_token(client):
    """
    A previously issued JWT must stop working after account deactivation.
    """

    from app.models import User
    from app.database import SessionLocal

    # Create Agent and obtain an existing JWT
    agent_token = create_test_user("Agent")

    db = SessionLocal()

    try:
        agent = db.query(User).filter(
            User.role == "Agent"
        ).order_by(User.id.desc()).first()

        assert agent is not None

        agent.is_active = False
        db.commit()

    finally:
        db.close()

    # Try accessing API using the previously issued JWT
    client.headers.update({
        "Authorization": f"Bearer {agent_token}"
    })

    response = client.get("/api/tickets")

    assert response.status_code == 401


# =========================================================
# JWT-002 DATABASE-BACKED JTI REVOCATION REGRESSION TESTS
# =========================================================

def test_login_generates_token_with_unique_jti(client):
    from app.security import decode_access_token
    token = create_test_user("Agent")
    res = decode_access_token(token)
    assert res is not None
    _, jti = res
    assert isinstance(jti, str)
    assert len(jti) == 36


def test_logout_revokes_presented_token_and_blocks_subsequent_requests(client):
    token = create_test_user("Agent")
    client.headers.update({"Authorization": f"Bearer {token}"})

    res1 = client.get("/api/tickets")
    assert res1.status_code == 200

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    res2 = client.get("/api/tickets")
    assert res2.status_code == 401


def test_another_user_token_remains_valid_after_logout(client):
    token1 = create_test_user("Agent")
    token2 = create_test_user("Viewer")

    client.headers.update({"Authorization": f"Bearer {token1}"})
    assert client.post("/api/auth/logout").status_code == 200

    assert client.get("/api/tickets").status_code == 401

    client.headers.update({"Authorization": f"Bearer {token2}"})
    assert client.get("/api/tickets").status_code == 200


def test_repeated_logout_is_idempotent(client):
    token = create_test_user("Agent")
    client.headers.update({"Authorization": f"Bearer {token}"})

    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/tickets").status_code == 401


def test_expired_token_returns_401(client):
    from app.security import create_access_token
    from app.models import User
    from app.database import SessionLocal
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    db = SessionLocal()
    try:
        user = db.query(User).first()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "jti": str(uuid.uuid4()),
            "iat": now - timedelta(hours=2),
            "nbf": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "type": "access",
        }
        expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    finally:
        db.close()

    client.headers.update({"Authorization": f"Bearer {expired_token}"})
    assert client.get("/api/tickets").status_code == 401


def test_invalid_signature_returns_401(client):
    token = create_test_user("Agent")
    tampered_token = token + "tampered"
    client.headers.update({"Authorization": f"Bearer {tampered_token}"})
    assert client.get("/api/tickets").status_code == 401


def test_missing_jti_token_is_rejected(client):
    from app.models import User
    from app.database import SessionLocal
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    db = SessionLocal()
    try:
        user = db.query(User).first()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=30),
            "type": "access",
        }
        nojti_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    finally:
        db.close()

    client.headers.update({"Authorization": f"Bearer {nojti_token}"})
    assert client.get("/api/tickets").status_code == 401


def test_revocation_survives_new_session(client):
    token = create_test_user("Agent")
    client.headers.update({"Authorization": f"Bearer {token}"})
    assert client.post("/api/auth/logout").status_code == 200

    from app.models import RevokedToken
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        revoked_records = db.query(RevokedToken).all()
        assert len(revoked_records) > 0
    finally:
        db.close()

    assert client.get("/api/tickets").status_code == 401    