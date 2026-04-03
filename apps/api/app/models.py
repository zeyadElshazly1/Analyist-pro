"""
SQLAlchemy ORM models — persistent storage replacing the in-memory dicts.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, BigInteger, JSON, ForeignKey, Boolean,
)
from sqlalchemy.orm import relationship

from app.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="created")  # created | uploading | ready | error
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    analyses = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")
    features = relationship("ProjectFeature", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)       # Original filename
    stored_path = Column(String(1024), nullable=False)   # Path on disk (or S3 key in future)
    size_bytes = Column(BigInteger, default=0)
    file_hash = Column(String(64), nullable=True)        # SHA256 for cache invalidation
    uploaded_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "filename": self.filename,
            "stored_path": self.stored_path,
            "size_bytes": self.size_bytes,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_hash = Column(String(64), nullable=True)        # Hash of the file at analysis time
    result_json = Column(Text, nullable=False)           # Full analysis JSON (compressed if needed)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="analyses")

    @property
    def result(self) -> dict:
        return json.loads(self.result_json)

    @result.setter
    def result(self, value: dict):
        self.result_json = json.dumps(value, default=str)


class ProjectFeature(Base):
    __tablename__ = "project_features"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    formula = Column(Text, nullable=False)
    dtype = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="features")

    def to_dict(self):
        return {
            "name": self.name,
            "formula": self.formula,
            "dtype": self.dtype,
        }
