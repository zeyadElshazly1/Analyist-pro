"""
SQLAlchemy ORM models — persistent storage replacing the in-memory dicts.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, BigInteger, ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


_DEFAULT_NOTIFICATION_PREFS = {
    "analysis_complete": True,
    "weekly_digest": True,
    "product_updates": False,
    "marketing_emails": False,
}


class User(Base):
    __tablename__ = "users"

    # UUID string from Supabase auth.users — not auto-incremented
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    plan = Column(String(50), default="free")  # free | consultant | studio
    notification_prefs_json = Column(Text, nullable=True)  # JSON: notification preference flags
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    @property
    def notification_prefs(self) -> dict:
        if not self.notification_prefs_json:
            return dict(_DEFAULT_NOTIFICATION_PREFS)
        try:
            return json.loads(self.notification_prefs_json)
        except Exception:
            return dict(_DEFAULT_NOTIFICATION_PREFS)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "plan": self.plan,
            "notification_prefs": self.notification_prefs,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="created")  # created | uploading | ready | error
    column_annotations_json = Column(Text, nullable=True)   # JSON: {col: annotation_string}
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="projects")

    # Relationships
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    analyses = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")
    features = relationship("ProjectFeature", back_populates="project", cascade="all, delete-orphan")

    @property
    def column_annotations(self) -> dict:
        if not self.column_annotations_json:
            return {}
        try:
            return json.loads(self.column_annotations_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @column_annotations.setter
    def column_annotations(self, value: dict):
        self.column_annotations_json = json.dumps(value)

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


_RUN_STATUSES = {
    "created",           # stub written, processing not yet started
    "intake_complete",   # file parsed, structure detected
    "cleaning_complete", # cleaning pipeline done, PreparedDataset saved
    "profiling_complete",# column profiles and health score computed
    "insights_complete", # insights, narrative, executive panel generated
    "report_ready",      # full result_json committed — run is readable
    "export_ready",      # at least one export artifact stored
    "failed",            # pipeline stopped with an unhandled error
}


class AnalysisResult(Base):
    """
    Canonical run record — one execution of the analysis pipeline against one file version.

    V1 run fields (added): status, started_at, trigger_source, error_summary,
    file_id, user_id, ai_model_version, story_result_json.

    Deferred: prepared_dataset_id FK (after PreparedDataset loader is wired).
    """
    __tablename__ = "analysis_results"

    # ── Identity ──────────────────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Run status ────────────────────────────────────────────────────────────
    status = Column(String(32), nullable=False, server_default="report_ready")
    started_at = Column(DateTime(timezone=True), nullable=True)      # None for historical rows
    trigger_source = Column(String(32), nullable=True)               # "user" | "background_job" | "retry"
    error_summary = Column(Text, nullable=True)                      # set when status="failed"

    # ── Source file link ──────────────────────────────────────────────────────
    file_id = Column(Integer, ForeignKey("project_files.id"), nullable=True)  # resolved ProjectFile
    file_hash = Column(String(64), nullable=True)                    # SHA-256 of source file

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # denormalized from project

    # ── Result payloads ───────────────────────────────────────────────────────
    result_json = Column(Text, nullable=False)                       # full pipeline output (all stages)
    story_result_json = Column(Text, nullable=True)                  # AI data-story JSON (separate stage)
    ai_model_version = Column(String(64), nullable=True)             # model used for AI story/chat

    # ── Share link ────────────────────────────────────────────────────────────
    share_token = Column(String(64), nullable=True, unique=True, index=True)
    share_expires_at = Column(DateTime(timezone=True), nullable=True)
    share_revoked = Column(Boolean, default=False, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), default=_utcnow)    # completion time

    # ── Relationships ─────────────────────────────────────────────────────────
    project = relationship("Project", back_populates="analyses")
    source_file = relationship("ProjectFile", foreign_keys=[file_id])

    @property
    def result(self) -> dict:
        return json.loads(self.result_json)

    @result.setter
    def result(self, value: dict):
        self.result_json = json.dumps(value, default=str)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)   # e.g. "upload", "analysis", "login", "delete_account"
    resource_type = Column(String(64), nullable=True)         # e.g. "project", "analysis"
    resource_id = Column(String(64), nullable=True)           # e.g. project_id or analysis_id as string
    detail = Column(Text, nullable=True)                      # optional JSON with extra context
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    # Enriched event classification (additive — nullable so existing rows are unaffected)
    severity   = Column(String(16),  nullable=True, index=True)   # low/medium/high/critical
    category   = Column(String(32),  nullable=True, index=True)   # data_access/auth/export/…
    user_agent = Column(String(256), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "severity": self.severity,
            "category": self.category,
        }


class TeamInvite(Base):
    """Tracks team membership for Team-plan users.

    A pending record means an invite link was generated but not yet accepted.
    An active record means the member has joined the team.
    The owner_id is always the Team-plan subscriber; member_id is set on accept.
    """
    __tablename__ = "team_invites"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(255), nullable=True)          # optional hint: who was invited
    token = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(20), default="pending")       # pending | active | revoked
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "member_id": self.member_id,
            "email": self.email,
            "token": self.token,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }


class ReportDraft(Base):
    """Editable report draft assembled from an analysis result."""
    __tablename__ = "report_drafts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(512), nullable=False, default="")
    summary = Column(Text, nullable=True)
    selected_insight_ids_json = Column(Text, nullable=True)  # JSON list of insight indices
    selected_chart_ids_json = Column(Text, nullable=True)    # JSON list of chart identifiers
    template = Column(String(64), nullable=True)             # e.g. "monthly_performance"
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    project = relationship("Project")

    @property
    def selected_insights(self) -> list:
        return json.loads(self.selected_insight_ids_json) if self.selected_insight_ids_json else []

    @property
    def selected_charts(self) -> list:
        return json.loads(self.selected_chart_ids_json) if self.selected_chart_ids_json else []


class PreparedDataset(Base):
    """Durable artifact: cleaned Parquet file derived from a raw upload."""
    __tablename__ = "prepared_datasets"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_hash = Column(String(64), nullable=False, index=True)   # Hash of the source raw file
    stored_path = Column(String(512), nullable=False)            # Path to Parquet file on disk / S3
    rows = Column(Integer, nullable=True)
    columns = Column(Integer, nullable=True)
    cleaning_meta_json = Column(Text, nullable=True)             # JSON summary of cleaning steps
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project")


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
