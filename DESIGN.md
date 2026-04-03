# DESIGN.md — Mangaka: Manga Tracker

## Domain and Motivation

**Mangaka** is a personal manga tracking application inspired by MyAnimeList (MAL).
Users can search for manga via the Jikan API (unofficial MAL API), add titles to a
personalised reading list, track reading progress, score titles, and manage a
favourites collection — all behind a secure user account.

The name _Mangaka_ (漫画家) is the Japanese word for "manga artist", chosen to reflect
the Japanese cultural context of the content being tracked.

## Technology Stack

| Layer             | Choice                                    | Rationale                                                                         |
| ----------------- | ----------------------------------------- | --------------------------------------------------------------------------------- |
| Backend framework | FastAPI (Python)                          | Async support for Jikan proxy, auto docs, Pydantic integration                    |
| ORM               | SQLAlchemy 2.x                            | Clean declarative models, aligns with course examples                             |
| Database          | SQLite (dev)                              | Zero-config for lab environment; PostgreSQL-ready via DATABASE_URL                |
| Authentication    | JWT (python-jose) + passlib/pbkdf2_sha256 | Stateless, CSRF-resistant; pbkdf2_sha256 avoids bcrypt C-ext issues in the lab VM |
| Frontend          | Alpine.js 3.x + vanilla CSS               | Reactive without a build step; matches course stack                               |
| External API      | Jikan v4 (jikan.moe)                      | Free, unofficial MAL API; no API key required                                     |
| HTTP client       | httpx (async)                             | Non-blocking Jikan proxy calls inside FastAPI async routes                        |
| Testing           | pytest + FastAPI TestClient               | In-memory SQLite DB; isolated per-test via fixture teardown                       |

## Core Features

1. **User authentication** — Register, login, logout with JWT tokens stored in `localStorage`. Protected routes reject unauthenticated requests with `401 Unauthorized`.

2. **Manga search via Jikan API** — Users can search by title or browse top manga by popularity. Results are proxied through the FastAPI backend (`/api/jikan/*`) to avoid CORS issues.

3. **Personal reading list (CRUD)** — Add manga to your list with a status (Plan to Read, Reading, Completed, On Hold, Dropped), chapter progress, personal score (0–10), and notes. Update or remove entries at any time.

4. **Favourites** — Mark any entry as a favourite; view your curated favourites in a dedicated tab.

5. **Reading stats dashboard** — Aggregated counts (total, reading, completed, plan-to-read, on-hold, dropped, favourites) plus average personal score displayed at the top of the list view.

6. **Data scoping** — Every manga entry is linked to its owner via a `ForeignKey`. All queries filter by `owner_id = current_user.id`; users cannot access or modify other users' data.

## Data Model

### `users`

| Field           | Type        | Notes                        |
| --------------- | ----------- | ---------------------------- |
| id              | Integer PK  | Auto-increment               |
| username        | String(50)  | Unique, indexed              |
| email           | String(255) | Unique, indexed              |
| hashed_password | String(255) | pbkdf2_sha256 hash (passlib) |
| is_active       | Boolean     | Default true                 |
| created_at      | DateTime    | Server default               |

### `manga_entries`

| Field          | Type                  | Notes                                                            |
| -------------- | --------------------- | ---------------------------------------------------------------- |
| id             | Integer PK            | Auto-increment                                                   |
| mal_id         | Integer               | MyAnimeList ID from Jikan                                        |
| title          | String(500)           | Original title                                                   |
| title_english  | String(500)           | English title (nullable)                                         |
| cover_image    | String(1000)          | Jikan image URL                                                  |
| status         | String(50)            | `plan_to_read` / `reading` / `completed` / `on_hold` / `dropped` |
| chapters_read  | Integer               | Default 0                                                        |
| total_chapters | Integer               | From Jikan; nullable for ongoing series                          |
| user_score     | Float                 | 0.0–10.0; nullable                                               |
| is_favourite   | Boolean               | Default false                                                    |
| notes          | Text                  | Personal notes                                                   |
| manga_status   | String(50)            | Jikan status (Publishing, Finished, etc.)                        |
| genres         | String(500)           | Comma-separated genre names                                      |
| mal_score      | Float                 | Community score from Jikan                                       |
| synopsis       | Text                  | From Jikan                                                       |
| author         | String(255)           | Comma-separated author names                                     |
| added_at       | DateTime              | Server default                                                   |
| updated_at     | DateTime              | Auto-update on change                                            |
| owner_id       | Integer FK → users.id | Data scoping                                                     |

**Relationship:** `User` → `MangaEntry` (one-to-many, cascade delete)

## API Endpoints

### Auth

| Method | Path            | Auth | Description       |
| ------ | --------------- | ---- | ----------------- |
| POST   | `/api/register` | —    | Create account    |
| POST   | `/api/token`    | —    | Login → JWT       |
| GET    | `/api/me`       | ✓    | Current user info |

### Manga List (CRUD)

| Method | Path              | Auth | Description                   |
| ------ | ----------------- | ---- | ----------------------------- |
| POST   | `/api/manga`      | ✓    | Add manga to list             |
| GET    | `/api/manga`      | ✓    | List all entries (filterable) |
| GET    | `/api/manga/{id}` | ✓    | Single entry                  |
| PUT    | `/api/manga/{id}` | ✓    | Update entry                  |
| DELETE | `/api/manga/{id}` | ✓    | Remove entry                  |
| GET    | `/api/stats`      | ✓    | Aggregated stats              |

### Jikan Proxy

| Method | Path                        | Description             |
| ------ | --------------------------- | ----------------------- |
| GET    | `/api/jikan/search?q=...`   | Search manga            |
| GET    | `/api/jikan/top`            | Top manga by popularity |
| GET    | `/api/jikan/manga/{mal_id}` | Detail for one manga    |

## Testing

Tests live in `backend/test_main.py` and use FastAPI's `TestClient` with an
in-memory SQLite database. Each test class gets a fresh database via an
`autouse` fixture that creates and drops all tables around every test.

**Coverage areas:**

- Registration: success, duplicate email, duplicate username, short password, invalid email
- Login: success, wrong password, non-existent user, invalid token
- Protected route (`/api/me`): authenticated vs unauthenticated
- Add manga: success, unauthenticated, duplicate, cross-user isolation
- List manga: own data only, status filter, favourite filter
- Get manga: own entry, another user's entry (404), non-existent (404)
- Update manga: full update, partial update, cross-user (404), score out of range (422)
- Delete manga: success + confirms 404 after, cross-user (404), non-existent (404)
- Stats: empty list, counts + avg score, user scoping, unauthenticated
- Health check

Run tests:

```bash
cd backend
pip install pytest httpx
pytest test_main.py -v
```
