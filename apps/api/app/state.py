from pathlib import Path
from typing import Any

# Shared in-memory state
# Both PROJECT_FILES and PROJECTS live here to avoid circular imports

PROJECT_FILES: dict[int, dict[str, Any]] = {}
# { project_id: { "filename": str, "path": str } }

PROJECTS: list = []
# [ { "id": int, "name": str, "status": str, ... } ]


def get_project_file_info(project_id: int) -> dict[str, Any] | None:
    """
    Return file info for a project.
    - First, tries in-memory state.
    - If missing (e.g. after API restart), falls back to uploads on disk and
      repopulates PROJECT_FILES.
    """
    existing = PROJECT_FILES.get(project_id)
    if existing and existing.get("path") and Path(existing["path"]).exists():
        return existing

    api_root = Path(__file__).resolve().parents[1]  # apps/api
    uploads_dir = api_root / "uploads"
    if not uploads_dir.exists():
        return None

    matches = sorted(
        uploads_dir.glob(f"project_{project_id}_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return None

    chosen = matches[0]
    prefix = f"project_{project_id}_"
    original_name = chosen.name[len(prefix):] if chosen.name.startswith(prefix) else chosen.name
    info = {"filename": original_name, "path": str(chosen)}
    PROJECT_FILES[project_id] = info
    return info
