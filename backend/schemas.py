"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional
from datetime import datetime


# ── User Schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Schema for login request."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user responses (excludes password)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime


# ── Token Schemas ─────────────────────────────────────────────────────────────

class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


# ── Manga Entry Schemas ───────────────────────────────────────────────────────

class MangaEntryCreate(BaseModel):
    """Schema for adding manga to collection."""
    mal_id: int
    title: str
    title_english: Optional[str] = None
    cover_image: Optional[str] = None
    status: str = Field(default="plan_to_read")
    chapters_read: int = Field(default=0, ge=0)
    total_chapters: Optional[int] = None
    user_score: Optional[float] = Field(default=None, ge=0, le=10)
    is_favourite: bool = False
    notes: Optional[str] = None
    manga_status: Optional[str] = None
    genres: Optional[str] = None
    mal_score: Optional[float] = None
    synopsis: Optional[str] = None
    author: Optional[str] = None


class MangaEntryUpdate(BaseModel):
    """Schema for updating manga entry."""
    status: Optional[str] = None
    chapters_read: Optional[int] = Field(default=None, ge=0)
    user_score: Optional[float] = Field(default=None, ge=0, le=10)
    is_favourite: Optional[bool] = None
    notes: Optional[str] = None


class MangaEntryResponse(BaseModel):
    """Schema for manga entry responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    mal_id: int
    title: str
    title_english: Optional[str]
    cover_image: Optional[str]
    status: str
    chapters_read: int
    total_chapters: Optional[int]
    user_score: Optional[float]
    is_favourite: bool
    notes: Optional[str]
    manga_status: Optional[str]
    genres: Optional[str]
    mal_score: Optional[float]
    synopsis: Optional[str]
    author: Optional[str]
    added_at: datetime
    updated_at: datetime
    owner_id: int


# ── Stats Schema ──────────────────────────────────────────────────────────────

class UserStats(BaseModel):
    """Schema for user statistics."""
    total: int
    reading: int
    completed: int
    plan_to_read: int
    on_hold: int
    dropped: int
    favourites: int
    avg_score: Optional[float]