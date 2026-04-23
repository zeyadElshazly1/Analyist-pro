"""
Canonical ReportResult schema — V1.

Represents the state of one report draft and its export outputs.
This is a composite record — it links draft content (what the consultant
chose to include and edited), AI-generated sections, and export artifacts.

The distinction between draft and export is kept clean:
  - Draft state  → which sections / insights / charts are selected, what was edited
  - Export state → which formats were requested, status, and any stored artifacts

Consumers:
  - Report builder UI (section picker, insight selector, summary editor)
  - Export UI (format buttons, export status, download links)
  - Run model (ReportResult linked to AnalysisResult.id via run_id)
  - Reopening an old report (full state recoverable from this record)

Main producer:
  - routes/reports.py  → upsert_report_draft() + export_report()
  - DB model: models.ReportDraft (partially maps to this schema)

See ADAPTER_NOTES at the bottom for the field-by-field mapping.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Sub-types ─────────────────────────────────────────────────────────────────

ExportFormat = Literal["html", "pdf", "xlsx"]

ExportStatus = Literal[
    "completed",    # successfully generated and delivered
    "failed",       # generation failed
    "pending",      # queued / in progress (future async use)
]

SectionId = Literal[
    "executive_summary",    # narrative + key headline
    "data_quality",         # health score, dimension breakdown
    "cleaning_steps",       # what the cleaning pipeline changed
    "top_insights",         # ranked insight cards
    "column_profiles",      # per-column stats table
    "chart_gallery",        # visual charts
    "compare_summary",      # file comparison findings (optional)
]

ReportTemplate = Literal[
    "monthly_performance",  # trend-led, period comparison
    "ops_kpi_review",       # health score, KPI table, variance
    "finance_summary",      # totals, outliers, category breakdown
    "blank",                # no pre-selection
]


# ── Sub-models ────────────────────────────────────────────────────────────────

class ReportSection(BaseModel):
    """One logical section in the report — included or excluded by the consultant."""
    section_id: SectionId
    title: str = Field(description="Display title for the section heading.")
    included: bool = Field(
        description="True if this section is selected for export.",
    )
    is_ai_generated: bool = Field(
        description=(
            "True when the section content was produced by the AI pipeline "
            "(narrative, insight text). False for data tables and charts."
        ),
    )
    custom_text: str | None = Field(
        default=None,
        description=(
            "User-overridden text for this section. None means use the "
            "AI-generated or pipeline-generated content."
        ),
    )


class IncludedInsight(BaseModel):
    """A reference to one insight selected for report inclusion."""
    insight_id: str = Field(
        description="Matches InsightResult.insight_id — stable across re-runs.",
    )
    title: str = Field(
        description="Snapshot of InsightResult.title at selection time.",
    )
    severity: str  = Field(description="'high', 'medium', or 'low'.")
    index_in_run: int | None = Field(
        default=None,
        description=(
            "Position of this insight in the ranked list at the time it was selected. "
            "Used for fallback resolution when insight_id is not yet stable."
        ),
    )


class IncludedChart(BaseModel):
    """A reference to one chart selected for report inclusion."""
    chart_id: str = Field(
        description="Unique identifier for the chart within the analysis run.",
    )
    chart_type: str = Field(
        description="E.g. 'scatter', 'line', 'bar', 'histogram', 'heatmap'.",
    )
    title: str = Field(
        description="Snapshot of the chart title at selection time.",
    )


class UserEdit(BaseModel):
    """One field the consultant manually edited in the report builder."""
    field: str = Field(
        description=(
            "Dot-path to the edited field, e.g. 'title', 'summary', "
            "'section.executive_summary.custom_text'."
        ),
    )
    edited_at: datetime


class ExportRecord(BaseModel):
    """One export attempt for this report."""
    format: ExportFormat
    status: ExportStatus
    exported_at: datetime | None = None
    error_message: str | None = Field(
        default=None,
        description="Populated when status is 'failed'.",
    )


class ExportArtifactRef(BaseModel):
    """
    Reference to a stored export file.

    In V1, exports are streamed to the browser and not stored server-side —
    stored_path and download_url will be None. This model is forward-ready
    for when S3 storage of export artifacts is implemented.
    """
    format: ExportFormat
    stored_path: str | None = Field(
        default=None,
        description="Server-side path (local disk or S3 key). None until artifact storage is wired.",
    )
    file_size_bytes: int | None = None
    exported_at: datetime | None = None
    download_url: str | None = Field(
        default=None,
        description="Pre-signed URL or download endpoint. None until artifact storage is wired.",
    )


# ── Canonical schema ──────────────────────────────────────────────────────────

class ReportResult(BaseModel):
    """
    V1 report result — full state of one report draft and its export history.

    Draft state and export state are separate but linked:
      - included_sections / included_insights / included_charts → what's in the draft
      - user_edits → what the consultant changed manually
      - ai_generated_sections → which section_ids have AI-authored content
      - export_statuses → export attempts and outcomes
      - export_artifact_refs → stored file references (V1: always empty)
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    report_id: int = Field(
        description="ReportDraft.id from the database.",
    )
    run_id: int | None = Field(
        default=None,
        description=(
            "AnalysisResult.id that this report is based on. "
            "None when a draft is created before an analysis has run."
        ),
    )
    project_id: int

    # ── Draft content ─────────────────────────────────────────────────────────
    title: str
    summary: str | None = Field(
        default=None,
        description=(
            "Executive summary shown at the top of the report. "
            "AI-generated initially; consultant-editable."
        ),
    )
    template: ReportTemplate | None = Field(
        default=None,
        description="Report template used for auto-populating section and insight selection.",
    )
    included_sections: list[ReportSection] = Field(
        default_factory=list,
        description="All possible sections with their included/excluded state.",
    )
    included_insights: list[IncludedInsight] = Field(
        default_factory=list,
        description="Insights the consultant has selected for this report.",
    )
    included_charts: list[IncludedChart] = Field(
        default_factory=list,
        description="Charts the consultant has selected for this report.",
    )

    # ── Edit history ──────────────────────────────────────────────────────────
    user_edits: list[UserEdit] = Field(
        default_factory=list,
        description=(
            "Fields the consultant edited manually. "
            "Used to preserve edits if the report is regenerated."
        ),
    )
    ai_generated_sections: list[SectionId] = Field(
        default_factory=list,
        description=(
            "Section IDs whose content was produced by the AI pipeline. "
            "These must carry an 'AI-generated' badge in the export."
        ),
    )

    # ── Export state ──────────────────────────────────────────────────────────
    export_statuses: list[ExportRecord] = Field(
        default_factory=list,
        description="History of export attempts for this report draft.",
    )
    export_artifact_refs: list[ExportArtifactRef] = Field(
        default_factory=list,
        description=(
            "References to stored export files. "
            "Empty in V1 — exports are streamed, not stored."
        ),
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: datetime
    updated_at: datetime


# ── Adapter notes ─────────────────────────────────────────────────────────────
#
# CURRENT PRODUCER
#   routes/reports.py  upsert_report_draft() + export_report()
#   DB model:          models.ReportDraft
#   Export generators: services/reporting/{html,pdf,excel}_report.py
#
# CLEAN MAPPINGS — direct or rename-only from ReportDraft:
#
#   report_id        ← draft.id
#   run_id           ← draft.analysis_result_id           (rename)
#   project_id       ← draft.project_id
#   title            ← draft.title
#   summary          ← draft.summary
#   template         ← draft.template
#   created_at       ← draft.created_at
#   updated_at       ← draft.updated_at
#
#   included_insights (partial):
#     draft.selected_insights → list of raw indices (int).
#     The full IncludedInsight needs insight_id, title, severity — none of which
#     are stored. Adapter: resolve indices against the InsightResult list from
#     AnalysisResult.result_json at the time of draft fetch.
#
#   included_charts (partial):
#     draft.selected_charts → list of raw IDs (str).
#     chart_type and title are not stored. Adapter: resolve against the chart
#     list in AnalysisResult.result_json.
#
# FIELDS NEEDING ADAPTERS — data partially exists:
#
#   export_statuses:
#     Not stored in ReportDraft — the audit log has action="export_completed"
#     entries but these are not linked back to a specific draft ID.
#     Adapter: query AuditLog for action="export_completed" WHERE
#     resource_id = str(project_id), reconstruct ExportRecord from detail["format"]
#     and created_at. For now, the route should write an ExportRecord to the
#     draft on each successful export.
#
# FIELDS MISSING ENTIRELY — not produced at all, can wait:
#
#   included_sections:
#     The template system (services/reporting/templates.py) knows which sections
#     apply to each template, but this is never persisted — it's recomputed at
#     render time. Missing field: add a `selected_section_ids_json` column to
#     ReportDraft, or derive from template + context at draft fetch.
#
#   user_edits:
#     No edit history is tracked. In V1, only title and summary are user-editable
#     and any change overwrites the previous value. Adapter (future): store a
#     JSON array of UserEdit records in a new `edits_json` column on ReportDraft.
#
#   ai_generated_sections:
#     Never tracked. The narrative (executive_summary) is always AI-generated;
#     all other sections are data-derived. Adapter: hardcode for V1:
#       ai_generated_sections = ["executive_summary"]
#     (extend when more AI-generated content is added).
#
#   export_artifact_refs:
#     Exports are streamed directly to the browser — no server-side file is saved.
#     This field remains empty in V1. Populate when S3 artifact storage is added.