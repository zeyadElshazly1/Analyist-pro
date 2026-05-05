"""
Apply a saved Report Builder draft to a raw analysis-result dict.

The Report Builder lets a consultant:
- pick which findings appear in the export (by stable ``insight_id`` —
  legacy drafts may still hold integer indices)
- edit the executive summary
- edit the report title

When the user exports HTML / Excel / PDF, the draft should drive what comes
out — not the raw analysis result.  This module provides a single helper,
``apply_draft_to_result``, that returns a copy of the analysis dict with:

  * ``insight_results`` (canonical) and ``insights`` (legacy) filtered down
    to the selected findings.
  * ``narrative`` overridden with the consultant's edited summary, so the
    existing template/Excel "Executive Summary" sections render the right
    text without any further plumbing.

Selection identity
------------------
The Report Builder used to save numeric *indices* into the displayed insight
list.  That was fragile: re-running analysis can re-order findings, so a
draft that recorded ``[2, 5]`` may end up selecting completely different
insights on the next run.

This module now selects by **stable insight_id** (``InsightResult.insight_id``,
a deterministic hex digest of category + sorted columns).  When the draft
holds string IDs, only insights whose ``insight_id`` matches one of those
strings are kept.

Legacy drafts that recorded integer indices keep working: the helper falls
back to index-based selection for any numeric entries.  Mixed lists are
also tolerated — string entries match by ID, numeric entries match by index.

The function never mutates its input.  Selected entries are clamped to the
length of the source list (for indices) or matched case-sensitively (for
IDs), so a stale draft pointing past the end of a shorter run — or at an
ID that no longer exists — never raises and never silently selects the
wrong finding.  Missing IDs are dropped, not coerced into a fallback row.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Optional


def _is_nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _select_indices(
    source_list: list[Any],
    selected: Iterable[Any],
) -> list[int]:
    """Resolve a draft's ``selected`` list to indices into ``source_list``.

    Each entry may be:
      * a ``str`` — matched against ``insight["insight_id"]`` on the source
        items.  Misses are silently dropped (we'd rather show fewer findings
        than the wrong finding).
      * an ``int`` — treated as a legacy positional index, clamped to
        ``[0, len(source_list))``.
      * anything else — ignored.

    Returns the indices in the order they appear in the draft, with
    duplicates de-duplicated while preserving first-seen order.
    """
    id_to_index: dict[str, int] = {}
    for idx, ins in enumerate(source_list):
        if isinstance(ins, dict):
            iid = ins.get("insight_id")
            if isinstance(iid, str) and iid and iid not in id_to_index:
                id_to_index[iid] = idx

    resolved: list[int] = []
    seen: set[int] = set()

    # Booleans are a subclass of int in Python — exclude them explicitly so
    # ``True``/``False`` cannot accidentally select index 1 or 0.
    for entry in selected:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, str):
            idx = id_to_index.get(entry)
            if idx is None:
                continue
            if idx not in seen:
                resolved.append(idx)
                seen.add(idx)
        elif isinstance(entry, int):
            if 0 <= entry < len(source_list) and entry not in seen:
                resolved.append(entry)
                seen.add(entry)

    return resolved


def apply_draft_to_result(
    analysis_result: dict[str, Any],
    *,
    draft_summary: Optional[str] = None,
    draft_title: Optional[str] = None,
    selected_indices: Optional[Iterable[Any]] = None,
    selected_chart_ids: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Return a copy of ``analysis_result`` with the saved draft applied.

    Parameters
    ----------
    analysis_result :
        Decoded ``AnalysisResult.result_json`` dict.  Must not be mutated.
    draft_summary :
        ``ReportDraft.summary`` — the edited executive summary.  When non-empty,
        it replaces ``analysis_result["narrative"]`` so the existing
        HTML/Excel templates render the consultant's edit.
    draft_title :
        ``ReportDraft.title`` — used by callers that want to read it back via
        ``result["draft_title"]``.
    selected_indices :
        ``ReportDraft.selected_insights`` — a list whose entries are either
        stable ``insight_id`` strings (preferred) or legacy integer indices.
        ``None`` means "no selection recorded" and the run's full insight
        set is preserved (used for freshly created drafts that have not
        been edited yet).
    """
    result = deepcopy(analysis_result)

    insight_results = result.get("insight_results")
    legacy_insights = result.get("insights")

    if _is_nonempty_list(insight_results):
        source_list, source_key = insight_results, "insight_results"
    elif _is_nonempty_list(legacy_insights):
        source_list, source_key = legacy_insights, "insights"
    else:
        source_list, source_key = None, None

    if selected_indices is not None and source_list is not None and source_key is not None:
        clean_idxs = _select_indices(source_list, selected_indices)
        filtered = [source_list[i] for i in clean_idxs]

        result[source_key] = filtered

        # Mirror the same selection onto the other key (when present) so a
        # consumer that reads from the other list never sees the unfiltered
        # data — this keeps preview/HTML/Excel/PDF strictly consistent.
        if source_key == "insight_results" and isinstance(legacy_insights, list):
            result["insights"] = [
                legacy_insights[i] for i in clean_idxs if i < len(legacy_insights)
            ]
        if source_key == "insights" and isinstance(insight_results, list):
            result["insight_results"] = [
                insight_results[i] for i in clean_idxs if i < len(insight_results)
            ]

    if draft_summary is not None:
        cleaned = draft_summary.strip()
        if cleaned:
            result["narrative"] = cleaned
            result["draft_summary"] = cleaned

    if draft_title is not None:
        cleaned_title = draft_title.strip()
        if cleaned_title:
            result["draft_title"] = cleaned_title

    if selected_chart_ids is not None:
        result["selected_chart_ids"] = list(selected_chart_ids)

    return result
