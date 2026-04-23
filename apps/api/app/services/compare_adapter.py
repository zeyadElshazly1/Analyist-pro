"""
Adapter: raw compare_files() output → canonical CompareResult.

Single mapping layer between the multifile compare service and the V1 schema.
Derives all fields not produced by compare_files():
  - compare_id      : deterministic string from project IDs
  - diff_pct        : row volume percentage change
  - change_flag     : per-metric significance classification
  - health delta/direction : derived from score difference
  - summary_draft   : template-built consultant-facing paragraph
  - caution_flags   : risk signals ordered by severity
"""
from __future__ import annotations

import hashlib

from app.schemas.compare import (
    CautionFlag,
    CompareResult,
    FileRef,
    HealthChange,
    MetricDelta,
    RowVolumeChange,
    SchemaChanges,
)


# ── Public API ────────────────────────────────────────────────────────────────

def build_compare_result(
    raw: dict,
    project_id_a: int | None = None,
    project_id_b: int | None = None,
) -> CompareResult:
    """
    Convert compare_files() raw output into a canonical CompareResult.

    Args:
        raw:          Dict returned by compare_files().
        project_id_a: ProjectFile.project_id for file A (available from the route payload).
        project_id_b: ProjectFile.project_id for file B.

    Returns:
        Fully-populated CompareResult ready for serialisation.
    """
    compare_id    = _make_compare_id(project_id_a, project_id_b, raw)
    file_a        = _build_file_ref(raw, "a", project_id_a)
    file_b        = _build_file_ref(raw, "b", project_id_b)
    schema_chg    = _build_schema_changes(raw)
    row_vol       = _build_row_volume(raw)
    metric_deltas = _build_metric_deltas(raw)
    health_chg    = _build_health_change(raw)
    caution_flags = _build_caution_flags(schema_chg, row_vol, metric_deltas, health_chg)
    summary_draft = _build_summary_draft(file_a, file_b, row_vol, schema_chg, metric_deltas, health_chg)

    return CompareResult(
        compare_id=compare_id,
        file_a=file_a,
        file_b=file_b,
        schema_changes=schema_chg,
        row_volume_changes=row_vol,
        metric_deltas=metric_deltas,
        health_changes=health_chg,
        summary_draft=summary_draft,
        caution_flags=caution_flags,
    )


# ── Sub-builders ──────────────────────────────────────────────────────────────

def _make_compare_id(pid_a: int | None, pid_b: int | None, raw: dict) -> str:
    if pid_a is not None and pid_b is not None:
        return f"{pid_a}:{pid_b}"
    # Fallback: hash label names
    key = f"{raw.get('label_a', '')}|{raw.get('label_b', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _build_file_ref(raw: dict, side: str, project_id: int | None) -> FileRef:
    label_key   = "label_a" if side == "a" else "label_b"
    row_count   = raw["rows"][side]
    col_count   = raw["columns"][side]
    return FileRef(
        file_name=raw.get(label_key, f"File {side.upper()}"),
        project_id=project_id,
        row_count=row_count,
        column_count=col_count,
    )


def _build_schema_changes(raw: dict) -> SchemaChanges:
    schema = raw.get("schema", {})
    return SchemaChanges(
        added_columns=list(schema.get("only_b", [])),    # cols in B absent from A
        removed_columns=list(schema.get("only_a", [])),  # cols in A absent from B
        shared_columns=list(schema.get("shared", [])),
    )


def _build_row_volume(raw: dict) -> RowVolumeChange:
    count_a = raw["rows"]["a"]
    count_b = raw["rows"]["b"]
    diff    = raw["rows"]["diff"]           # count_b − count_a

    diff_pct: float | None = None
    if count_a > 0:
        diff_pct = round((count_b - count_a) / count_a * 100, 2)

    overlap      = raw.get("row_overlap", {})
    overlap_count = int(overlap.get("count", 0))
    overlap_pct   = overlap.get("pct_of_a")   # already float | None

    return RowVolumeChange(
        count_a=count_a,
        count_b=count_b,
        diff=diff,
        diff_pct=diff_pct,
        overlap_count=overlap_count,
        overlap_pct_of_a=float(overlap_pct) if overlap_pct is not None else None,
    )


def _build_metric_deltas(raw: dict) -> list[MetricDelta]:
    deltas: list[MetricDelta] = []
    for item in raw.get("stats_comparison", []):
        pct = item.get("mean_diff_pct")
        change_flag = _classify_metric_change(pct)
        deltas.append(MetricDelta(
            column=item["column"],
            mean_a=item.get("a_mean"),
            mean_b=item.get("b_mean"),
            mean_delta_pct=pct,
            median_a=item.get("a_median"),
            median_b=item.get("b_median"),
            std_a=item.get("a_std"),
            std_b=item.get("b_std"),
            change_flag=change_flag,          # type: ignore[arg-type]
        ))
    return deltas


def _classify_metric_change(pct: float | None) -> str:
    if pct is None:
        return "no_data"
    abs_pct = abs(pct)
    if abs_pct > 20:
        return "significant"
    if abs_pct >= 5:
        return "notable"
    return "stable"


def _build_health_change(raw: dict) -> HealthChange:
    hs = raw.get("health_scores", {})
    score_a = float(hs.get("a", {}).get("total", 0.0))
    score_b = float(hs.get("b", {}).get("total", 0.0))
    delta   = round(score_b - score_a, 2)

    if delta > 2:
        direction = "improved"
    elif delta < -2:
        direction = "declined"
    else:
        direction = "unchanged"

    return HealthChange(
        score_a=score_a,
        score_b=score_b,
        grade_a=hs.get("a", {}).get("grade", "F"),
        grade_b=hs.get("b", {}).get("grade", "F"),
        delta=delta,
        direction=direction,               # type: ignore[arg-type]
    )


# ── Caution flags ─────────────────────────────────────────────────────────────

def _build_caution_flags(
    schema_chg: SchemaChanges,
    row_vol: RowVolumeChange,
    metric_deltas: list[MetricDelta],
    health_chg: HealthChange,
) -> list[CautionFlag]:
    flags: list[CautionFlag] = []

    # Columns removed from file_a → high severity (data loss risk)
    if schema_chg.removed_columns:
        cols_str = ", ".join(schema_chg.removed_columns[:5])
        flags.append(CautionFlag(
            kind="columns_removed",
            severity="high",
            message=(
                f"{len(schema_chg.removed_columns)} column(s) from the reference file are absent "
                f"in the new file: {cols_str}. Verify this is intentional before sharing with a client."
            ),
        ))

    # Columns added in file_b → low severity (new data)
    if schema_chg.added_columns:
        cols_str = ", ".join(schema_chg.added_columns[:5])
        flags.append(CautionFlag(
            kind="columns_added",
            severity="low",
            message=(
                f"{len(schema_chg.added_columns)} new column(s) appear in the new file: {cols_str}. "
                f"Confirm these are expected additions."
            ),
        ))

    # Large volume drop (>20% fewer rows)
    if row_vol.diff_pct is not None and row_vol.diff_pct < -20:
        flags.append(CautionFlag(
            kind="large_volume_drop",
            severity="high",
            message=(
                f"Row count dropped by {abs(row_vol.diff_pct):.1f}% "
                f"({row_vol.diff:+,} rows). Investigate before client delivery — "
                f"missing data may indicate a pipeline or export issue."
            ),
        ))

    # Large volume spike (>50% more rows)
    if row_vol.diff_pct is not None and row_vol.diff_pct > 50:
        flags.append(CautionFlag(
            kind="large_volume_spike",
            severity="medium",
            message=(
                f"Row count increased by {row_vol.diff_pct:.1f}% "
                f"({row_vol.diff:+,} rows). Confirm this growth is expected "
                f"and not caused by duplicate ingestion."
            ),
        ))

    # Significant metric shifts — one flag per column
    for delta in metric_deltas:
        if delta.change_flag == "significant":
            pct_str = f"{delta.mean_delta_pct:+.1f}%" if delta.mean_delta_pct is not None else "N/A"
            flags.append(CautionFlag(
                kind="significant_metric_shift",
                severity="medium",
                column=delta.column,
                message=(
                    f"Average '{delta.column}' shifted by {pct_str} — "
                    f"a change of this magnitude should be explained in the client summary."
                ),
            ))

    # Health declined significantly (>5 pts)
    if health_chg.delta < -5:
        flags.append(CautionFlag(
            kind="health_declined",
            severity="high",
            message=(
                f"Data quality declined from grade {health_chg.grade_a} "
                f"(score {health_chg.score_a:.0f}) to grade {health_chg.grade_b} "
                f"(score {health_chg.score_b:.0f}). Review cleaning and source data before sharing."
            ),
        ))

    # High row overlap — may not be a new period's data
    if row_vol.overlap_pct_of_a is not None and row_vol.overlap_pct_of_a > 90:
        flags.append(CautionFlag(
            kind="high_row_overlap",
            severity="medium",
            message=(
                f"{row_vol.overlap_pct_of_a:.0f}% of rows in the reference file also appear "
                f"in the new file. These files may represent the same time period rather than "
                f"distinct periods — confirm before treating as a period comparison."
            ),
        ))

    # Low row overlap — may be unrelated datasets
    if row_vol.overlap_pct_of_a is not None and row_vol.overlap_pct_of_a < 10:
        flags.append(CautionFlag(
            kind="low_row_overlap",
            severity="medium",
            message=(
                f"Only {row_vol.overlap_pct_of_a:.0f}% of rows overlap between files. "
                f"Confirm both files represent the same entity/dataset before drawing conclusions."
            ),
        ))

    # Sort: high → medium → low
    _SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: _SEV_ORDER.get(f.severity, 3))
    return flags


# ── Summary draft ─────────────────────────────────────────────────────────────

def _build_summary_draft(
    file_a: FileRef,
    file_b: FileRef,
    row_vol: RowVolumeChange,
    schema_chg: SchemaChanges,
    metric_deltas: list[MetricDelta],
    health_chg: HealthChange,
) -> str:
    """
    Build a 2–4 sentence consultant-facing summary of the most important changes.
    Intended as an editable starting point for the report builder.
    """
    sentences: list[str] = []

    # Sentence 1: row volume
    if row_vol.diff_pct is not None and abs(row_vol.diff_pct) >= 1:
        direction_word = "more" if row_vol.diff > 0 else "fewer"
        sentences.append(
            f"{file_b.file_name} contains {abs(row_vol.diff):,} {direction_word} rows "
            f"than {file_a.file_name} ({row_vol.diff_pct:+.1f}%)."
        )
    else:
        sentences.append(
            f"{file_b.file_name} and {file_a.file_name} have a similar row count "
            f"({row_vol.count_b:,} vs {row_vol.count_a:,} rows)."
        )

    # Sentence 2: schema changes (if any)
    if schema_chg.removed_columns or schema_chg.added_columns:
        parts: list[str] = []
        if schema_chg.removed_columns:
            parts.append(f"{len(schema_chg.removed_columns)} column(s) removed")
        if schema_chg.added_columns:
            parts.append(f"{len(schema_chg.added_columns)} column(s) added")
        sentences.append("Structure changed: " + " and ".join(parts) + ".")

    # Sentence 3: largest significant metric shift
    sig_deltas = [d for d in metric_deltas if d.change_flag == "significant" and d.mean_delta_pct is not None]
    if sig_deltas:
        top = max(sig_deltas, key=lambda d: abs(d.mean_delta_pct))  # type: ignore[arg-type]
        sentences.append(
            f"The largest shift is in '{top.column}', which moved by {top.mean_delta_pct:+.1f}% on average."
        )
    elif any(d.change_flag == "notable" for d in metric_deltas):
        notable = [d for d in metric_deltas if d.change_flag == "notable" and d.mean_delta_pct is not None]
        top = max(notable, key=lambda d: abs(d.mean_delta_pct))  # type: ignore[arg-type]
        sentences.append(
            f"Notable shift in '{top.column}': {top.mean_delta_pct:+.1f}% change in average value."
        )

    # Sentence 4: health direction
    if health_chg.direction != "unchanged":
        verb = "improved" if health_chg.direction == "improved" else "declined"
        sentences.append(
            f"Overall data quality {verb} from grade {health_chg.grade_a} "
            f"(score {health_chg.score_a:.0f}) to grade {health_chg.grade_b} "
            f"(score {health_chg.score_b:.0f})."
        )
    else:
        sentences.append(
            f"Overall data quality remained stable (grade {health_chg.grade_b}, "
            f"score {health_chg.score_b:.0f})."
        )

    return " ".join(sentences)
