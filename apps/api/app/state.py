# Shared in-memory state
# Both PROJECT_FILES and PROJECTS live here to avoid circular imports

PROJECT_FILES: dict = {}
# { project_id: { "filename": str, "path": str } }

PROJECTS: list = []
# [ { "id": int, "name": str, "status": str, ... } ]
