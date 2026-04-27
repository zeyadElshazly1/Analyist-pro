"""
Apply a saved Report Builder draft to a raw analysis-result dict.

The Report Builder lets a consultant:
- pick which findings appear in the export (by index in the displayed list)
- edit the executive summary
- edit the report title

When the user exports HTML / Excel / PDF, the draft should drive what comes
out — not the raw analysis result.  This module provides a single helper,
``apply_draft_to_result``, that returns a copy of the analysis dict with:

  * ``insight_results`` (canonical) and ``insights`` (legacy) filtered down
    to the selected indices.
  * ``narrative`` overridden with the consultant's edited summary, so the
    existing template/Excel "Executive Summary" sections render the right
    text without any further plumbing.

The function never mutates its input.  Selected indices are clamped to the
length of the source list, so a stale draft that points past the end of a
shorter run can never raise.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Optional


def _is_nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def apply_draft_to_result(
    analysis_result: dict[str, Any],
    *,
    draft_summary: Optional[str] = None,
    draft_title: Optional[str] = None,
    selected_indices: Optional[Iterable[int]] = None,
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
        ``result["draft_title"]``.  Existing templates do not consume this
        field, but persisting it on the dict keeps preview/export consistent.
    selected_indices :
        ``ReportDraft.selected_insights`` (list of integer indices into the
        same insight list that the Report Builder UI displayed).  When
        ``None`` no filtering is applied — useful for legacy drafts that
        never recorded a selection, where we keep the run's full insight set.
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
        clean_idxs = [
            i for i in selected_indices
            if isinstance(i, int) and 0 <= i < len(source_list)
        ]
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

    return result
