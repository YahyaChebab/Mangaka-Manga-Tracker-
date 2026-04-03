"""
tests/test_main.py — Mangaka Manga Tracker
==========================================
Run with:
    pip install pytest pytest-asyncio httpx
    pytest test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── App imports ──────────────────────────────────────────────────────────────
from database import Base, get_db
from main import app

# ── In-memory SQLite test database ───────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_manga.db"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """Create all tables before each test, drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register_and_login(client, email="test@example.com", password="password123", username="testuser"):
    client.post("/api/register", json={
        "username": username, "email": email, "password": password
    })
    resp = client.post("/api/token", json={"email": email, "password": password})
    return resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def sample_manga_payload(**overrides):
    base = {
        "mal_id": 1,
        "title": "Berserk",
        "title_english": "Berserk",
        "cover_image": "https://cdn.myanimelist.net/images/manga/1/157897.jpg",
        "status": "reading",
        "chapters_read": 10,
        "total_chapters": 364,
        "user_score": 9.5,
        "is_favourite": False,
        "notes": "Great art",
        "manga_status": "Finished",
        "genres": "Action, Fantasy",
        "mal_score": 9.45,
        "synopsis": "A dark fantasy manga.",
        "author": "Kentaro Miura",
    }
    base.update(overrides)
    return base


# ════════════════════════════════════════════════════════════════════════════
# AUTH TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/register", json={
            "username": "alice", "email": "alice@example.com", "password": "password123"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["username"] == "alice"
        assert "hashed_password" not in data  # never leak the hash

    def test_register_duplicate_email(self, client):
        payload = {"username": "alice", "email": "alice@example.com", "password": "password123"}
        client.post("/api/register", json=payload)
        resp = client.post("/api/register", json={**payload, "username": "alice2"})
        assert resp.status_code == 400
        assert "Email already registered" in resp.json()["detail"]

    def test_register_duplicate_username(self, client):
        client.post("/api/register", json={
            "username": "alice", "email": "alice@example.com", "password": "password123"
        })
        resp = client.post("/api/register", json={
            "username": "alice", "email": "other@example.com", "password": "password123"
        })
        assert resp.status_code == 400
        assert "Username already taken" in resp.json()["detail"]

    def test_register_password_too_short(self, client):
        resp = client.post("/api/register", json={
            "username": "alice", "email": "alice@example.com", "password": "short"
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_register_invalid_email(self, client):
        resp = client.post("/api/register", json={
            "username": "alice", "email": "not-an-email", "password": "password123"
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/register", json={
            "username": "bob", "email": "bob@example.com", "password": "password123"
        })
        resp = client.post("/api/token", json={
            "email": "bob@example.com", "password": "password123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post("/api/register", json={
            "username": "bob", "email": "bob@example.com", "password": "password123"
        })
        resp = client.post("/api/token", json={
            "email": "bob@example.com", "password": "wrongpassword"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/token", json={
            "email": "nobody@example.com", "password": "password123"
        })
        assert resp.status_code == 401

    def test_get_me_authenticated(self, client):
        token = register_and_login(client)
        resp = client.get("/api/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get("/api/me", headers={"Authorization": "Bearer fake.token.here"})
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# CRUD TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestAddManga:
    def test_add_manga_success(self, client):
        token = register_and_login(client)
        resp = client.post("/api/manga", json=sample_manga_payload(),
                           headers=auth_headers(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Berserk"
        assert data["mal_id"] == 1
        assert data["chapters_read"] == 10

    def test_add_manga_unauthenticated(self, client):
        resp = client.post("/api/manga", json=sample_manga_payload())
        assert resp.status_code == 401

    def test_add_duplicate_manga(self, client):
        token = register_and_login(client)
        client.post("/api/manga", json=sample_manga_payload(), headers=auth_headers(token))
        resp = client.post("/api/manga", json=sample_manga_payload(), headers=auth_headers(token))
        assert resp.status_code == 409
        assert "already in your list" in resp.json()["detail"]

    def test_add_same_manga_different_users(self, client):
        """Two different users can each add the same mal_id without conflict."""
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        r1 = client.post("/api/manga", json=sample_manga_payload(), headers=auth_headers(token1))
        r2 = client.post("/api/manga", json=sample_manga_payload(), headers=auth_headers(token2))
        assert r1.status_code == 201
        assert r2.status_code == 201


class TestListManga:
    def test_list_returns_only_own_entries(self, client):
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        client.post("/api/manga", json=sample_manga_payload(mal_id=1, title="Berserk"),
                    headers=auth_headers(token1))
        client.post("/api/manga", json=sample_manga_payload(mal_id=2, title="One Piece"),
                    headers=auth_headers(token2))

        resp = client.get("/api/manga", headers=auth_headers(token1))
        assert resp.status_code == 200
        titles = [e["title"] for e in resp.json()]
        assert "Berserk" in titles
        assert "One Piece" not in titles

    def test_list_filter_by_status(self, client):
        token = register_and_login(client)
        client.post("/api/manga", json=sample_manga_payload(mal_id=1, status="reading"),
                    headers=auth_headers(token))
        client.post("/api/manga", json=sample_manga_payload(mal_id=2, title="Naruto", status="completed"),
                    headers=auth_headers(token))

        resp = client.get("/api/manga?status=reading", headers=auth_headers(token))
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["status"] == "reading"

    def test_list_filter_by_favourite(self, client):
        token = register_and_login(client)
        client.post("/api/manga", json=sample_manga_payload(mal_id=1, is_favourite=True),
                    headers=auth_headers(token))
        client.post("/api/manga", json=sample_manga_payload(mal_id=2, title="Naruto", is_favourite=False),
                    headers=auth_headers(token))

        resp = client.get("/api/manga?is_favourite=true", headers=auth_headers(token))
        assert resp.status_code == 200
        assert all(e["is_favourite"] for e in resp.json())

    def test_list_unauthenticated(self, client):
        resp = client.get("/api/manga")
        assert resp.status_code == 401


class TestGetManga:
    def test_get_own_entry(self, client):
        token = register_and_login(client)
        created = client.post("/api/manga", json=sample_manga_payload(),
                              headers=auth_headers(token)).json()
        resp = client.get(f"/api/manga/{created['id']}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_other_users_entry_returns_404(self, client):
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token1)).json()
        resp = client.get(f"/api/manga/{entry['id']}", headers=auth_headers(token2))
        assert resp.status_code == 404

    def test_get_nonexistent_entry(self, client):
        token = register_and_login(client)
        resp = client.get("/api/manga/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestUpdateManga:
    def test_update_success(self, client):
        token = register_and_login(client)
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token)).json()
        resp = client.put(f"/api/manga/{entry['id']}",
                          json={"status": "completed", "chapters_read": 364, "user_score": 10.0},
                          headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["chapters_read"] == 364
        assert data["user_score"] == 10.0

    def test_update_partial(self, client):
        """Only the provided fields should change."""
        token = register_and_login(client)
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token)).json()
        resp = client.put(f"/api/manga/{entry['id']}",
                          json={"is_favourite": True},
                          headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["is_favourite"] is True
        assert resp.json()["status"] == entry["status"]  # unchanged

    def test_update_other_users_entry(self, client):
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token1)).json()
        resp = client.put(f"/api/manga/{entry['id']}",
                          json={"status": "dropped"},
                          headers=auth_headers(token2))
        assert resp.status_code == 404

    def test_update_score_out_of_range(self, client):
        token = register_and_login(client)
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token)).json()
        resp = client.put(f"/api/manga/{entry['id']}",
                          json={"user_score": 11.0},
                          headers=auth_headers(token))
        assert resp.status_code == 422


class TestDeleteManga:
    def test_delete_success(self, client):
        token = register_and_login(client)
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token)).json()
        resp = client.delete(f"/api/manga/{entry['id']}", headers=auth_headers(token))
        assert resp.status_code == 204
        # Confirm it's gone
        get_resp = client.get(f"/api/manga/{entry['id']}", headers=auth_headers(token))
        assert get_resp.status_code == 404

    def test_delete_other_users_entry(self, client):
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        entry = client.post("/api/manga", json=sample_manga_payload(),
                            headers=auth_headers(token1)).json()
        resp = client.delete(f"/api/manga/{entry['id']}", headers=auth_headers(token2))
        assert resp.status_code == 404
        # Original entry still exists for owner
        still_there = client.get(f"/api/manga/{entry['id']}", headers=auth_headers(token1))
        assert still_there.status_code == 200

    def test_delete_nonexistent(self, client):
        token = register_and_login(client)
        resp = client.delete("/api/manga/99999", headers=auth_headers(token))
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# STATS TESTS
# ════════════════════════════════════════════════════════════════════════════

class TestStats:
    def test_stats_empty(self, client):
        token = register_and_login(client)
        resp = client.get("/api/stats", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["avg_score"] is None

    def test_stats_counts(self, client):
        token = register_and_login(client)
        payloads = [
            sample_manga_payload(mal_id=1, status="reading", user_score=8.0),
            sample_manga_payload(mal_id=2, title="Naruto", status="completed", user_score=7.0),
            sample_manga_payload(mal_id=3, title="One Piece", status="plan_to_read", user_score=None,
                                 is_favourite=True),
        ]
        for p in payloads:
            client.post("/api/manga", json=p, headers=auth_headers(token))

        resp = client.get("/api/stats", headers=auth_headers(token))
        data = resp.json()
        assert data["total"] == 3
        assert data["reading"] == 1
        assert data["completed"] == 1
        assert data["plan_to_read"] == 1
        assert data["favourites"] == 1
        assert round(data["avg_score"], 2) == 7.5  # avg of 8.0 and 7.0

    def test_stats_scoped_to_user(self, client):
        token1 = register_and_login(client, email="u1@example.com", username="user1")
        token2 = register_and_login(client, email="u2@example.com", username="user2")
        for i in range(3):
            client.post("/api/manga",
                        json=sample_manga_payload(mal_id=i + 1, title=f"Manga {i}"),
                        headers=auth_headers(token1))

        resp = client.get("/api/stats", headers=auth_headers(token2))
        assert resp.json()["total"] == 0

    def test_stats_unauthenticated(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"