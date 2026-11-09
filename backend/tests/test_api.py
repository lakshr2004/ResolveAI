
def payload():
    return {
        "customer_name": "Asha Sharma",
        "customer_email": "asha@example.com",
        "subject": "Cannot log in to my account",
        "description": "I reset my password but still cannot sign in to my account.",
    }


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_ticket_create_get_history_status(client):
    created = client.post("/api/tickets", json=payload())
    assert created.status_code == 201

    ticket = created.json()
    tid = ticket["ticket_id"]

    assert client.get(f"/api/tickets/{tid}").status_code == 200

    history = client.get(f"/api/tickets/{tid}/history").json()
    assert history[0]["new_status"] == "Open"

    changed = client.patch(
        f"/api/tickets/{tid}/status",
        json={"status": "In Progress", "note": "Agent investigating"},
    )

    assert changed.status_code == 200
    assert changed.json()["status"] == "In Progress"

    assert len(client.get(f"/api/tickets/{tid}/history").json()) == 2


def test_search_and_analytics_are_db_backed(client):
    client.post("/api/tickets", json=payload())

    assert client.get("/api/tickets?q=asha").json()["total"] >= 1

    overview = client.get("/api/analytics/overview").json()
    assert overview["total_tickets"] >= 1

    assert isinstance(
        client.get("/api/analytics/categories").json(),
        list,
    )


def test_missing_ticket(client):
    assert client.get("/api/tickets/does-not-exist").status_code == 404


def test_reject_unsupported_upload_type(client):
    response = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "payload.exe",
                b"not executable content",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400


def test_reject_empty_upload(client):
    response = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "empty.md",
                b"",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 400


def test_reject_oversized_upload(client):
    oversized_content = b"A" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "large.txt",
                oversized_content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 413


def test_reject_fake_pdf(client):
    response = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "fake.pdf",
                b"This is not a real PDF document.",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400


def test_reject_mismatched_mime_type(client):
    response = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "guide.md",
                b"# Support Guide\n\nThis is a sufficiently long document.",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400


def test_system_health_shape(client):
    response = client.get("/api/system/status")

    assert response.status_code == 200
    assert "groq_configured" in response.json()



def test_security_headers_are_present(client):
    response = client.get("/health")

    assert response.status_code == 200

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

    assert (
        response.headers["Referrer-Policy"]
        == "strict-origin-when-cross-origin"
    )

    assert (
        response.headers["Permissions-Policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


def test_reject_request_with_oversized_content_length(client):
    response = client.post(
        "/api/tickets",
        headers={
            "Content-Length": str(13 * 1024 * 1024),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."

def test_reject_streamed_oversized_request():
    import asyncio

    from starlette.responses import JSONResponse
    from app.main import RequestBodyLimitMiddleware

    async def app(scope, receive, send):
        while True:
            message = await receive()

            if message["type"] == "http.request":
                if not message.get("more_body", False):
                    break

        response = JSONResponse({"status": "processed"})
        await response(scope, receive, send)

    middleware = RequestBodyLimitMiddleware(
        app,
        max_body_bytes=10,
    )

    messages = [
        {
            "type": "http.request",
            "body": b"A" * 8,
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"B" * 8,
            "more_body": False,
        },
    ]

    async def receive():
        return messages.pop(0)

    sent_messages = []

    async def send(message):
        sent_messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "POST",
        "path": "/test",
        "headers": [],
    }

    asyncio.run(
        middleware(scope, receive, send)
    )

    response_start = next(
        message
        for message in sent_messages
        if message["type"] == "http.response.start"
    )
    assert response_start["status"] == 413