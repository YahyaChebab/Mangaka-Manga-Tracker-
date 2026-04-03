"""
Manga Tracker API - Main FastAPI Application
"""

import os
from datetime import timedelta
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
import models
import schemas
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title="Manga Tracker API",
    description="Track your manga reading list with Jikan/MyAnimeList data",
    version="1.0.0"
)

# CORS configuration - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JIKAN_BASE = "https://api.jikan.moe/v4"


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/register", response_model=schemas.UserResponse, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if email already exists
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@app.post("/api/token", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login and get JWT token."""
    # Find user by email
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    
    # Verify user exists and password is correct
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


# ── Jikan API Proxy Endpoints ─────────────────────────────────────────────────

@app.get("/api/jikan/search")
async def search_manga(q: str = Query(..., min_length=1), page: int = 1):
    """Proxy Jikan manga search endpoint."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{JIKAN_BASE}/manga",
                params={"q": q, "page": page, "limit": 20, "order_by": "popularity"}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Jikan API error: {str(e)}")


@app.get("/api/jikan/manga/{mal_id}")
async def get_manga_detail(mal_id: int):
    """Proxy Jikan manga detail endpoint."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{JIKAN_BASE}/manga/{mal_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Jikan API error: {str(e)}")


@app.get("/api/jikan/top")
async def top_manga(page: int = 1, filter: str = "bypopularity"):
    """Proxy Jikan top manga endpoint."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{JIKAN_BASE}/top/manga",
                params={"page": page, "limit": 24, "filter": filter}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Jikan API error: {str(e)}")


# ── Manga Collection CRUD Endpoints ───────────────────────────────────────────

@app.post("/api/manga", response_model=schemas.MangaEntryResponse, status_code=201)
def add_manga(
    entry: schemas.MangaEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Add manga to user's collection."""
    # Check if manga already in user's list
    existing = db.query(models.MangaEntry).filter(
        models.MangaEntry.mal_id == entry.mal_id,
        models.MangaEntry.owner_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="Manga already in your list")
    
    # Create new entry
    db_entry = models.MangaEntry(**entry.model_dump(), owner_id=current_user.id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return db_entry


@app.get("/api/manga", response_model=List[schemas.MangaEntryResponse])
def list_manga(
    status: Optional[str] = None,
    is_favourite: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user's manga collection with optional filters."""
    query = db.query(models.MangaEntry).filter(
        models.MangaEntry.owner_id == current_user.id
    )
    
    if status:
        query = query.filter(models.MangaEntry.status == status)
    
    if is_favourite is not None:
        query = query.filter(models.MangaEntry.is_favourite == is_favourite)
    
    return query.order_by(models.MangaEntry.updated_at.desc()).all()


@app.get("/api/manga/{entry_id}", response_model=schemas.MangaEntryResponse)
def get_manga(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific manga entry from user's collection."""
    entry = db.query(models.MangaEntry).filter(
        models.MangaEntry.id == entry_id,
        models.MangaEntry.owner_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return entry


@app.put("/api/manga/{entry_id}", response_model=schemas.MangaEntryResponse)
def update_manga(
    entry_id: int,
    update: schemas.MangaEntryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a manga entry in user's collection."""
    entry = db.query(models.MangaEntry).filter(
        models.MangaEntry.id == entry_id,
        models.MangaEntry.owner_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)
    
    db.commit()
    db.refresh(entry)
    
    return entry


@app.delete("/api/manga/{entry_id}", status_code=204)
def delete_manga(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove manga from user's collection."""
    entry = db.query(models.MangaEntry).filter(
        models.MangaEntry.id == entry_id,
        models.MangaEntry.owner_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    db.delete(entry)
    db.commit()
    
    return None


# ── Statistics Endpoint ───────────────────────────────────────────────────────

@app.get("/api/stats", response_model=schemas.UserStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user's reading statistics."""
    entries = db.query(models.MangaEntry).filter(
        models.MangaEntry.owner_id == current_user.id
    ).all()
    
    # Calculate statistics
    scores = [e.user_score for e in entries if e.user_score is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    
    return schemas.UserStats(
        total=len(entries),
        reading=sum(1 for e in entries if e.status == "reading"),
        completed=sum(1 for e in entries if e.status == "completed"),
        plan_to_read=sum(1 for e in entries if e.status == "plan_to_read"),
        on_hold=sum(1 for e in entries if e.status == "on_hold"),
        dropped=sum(1 for e in entries if e.status == "dropped"),
        favourites=sum(1 for e in entries if e.is_favourite),
        avg_score=avg_score
    )


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}