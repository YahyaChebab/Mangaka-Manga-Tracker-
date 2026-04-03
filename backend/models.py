"""
SQLAlchemy ORM models for Manga Tracker.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    manga_entries = relationship("MangaEntry", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class MangaEntry(Base):
    """Manga entry model for user's collection."""
    __tablename__ = "manga_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    mal_id = Column(Integer, nullable=False)  # MyAnimeList / Jikan ID
    title = Column(String(500), nullable=False)
    title_english = Column(String(500), nullable=True)
    cover_image = Column(String(1000), nullable=True)
    status = Column(String(50), default="plan_to_read")  # plan_to_read, reading, completed, on_hold, dropped
    chapters_read = Column(Integer, default=0)
    total_chapters = Column(Integer, nullable=True)
    user_score = Column(Float, nullable=True)  # 0.0-10.0
    is_favourite = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    manga_status = Column(String(50), nullable=True)  # Publishing, Finished, etc.
    genres = Column(String(500), nullable=True)  # Comma-separated
    mal_score = Column(Float, nullable=True)
    synopsis = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Foreign key to user
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="manga_entries")
    
    def __repr__(self):
        return f"<MangaEntry(id={self.id}, title='{self.title}', owner_id={self.owner_id})>"