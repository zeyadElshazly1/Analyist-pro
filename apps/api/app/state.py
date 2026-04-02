from collections.abc import MutableMapping
from typing import Any, Iterator

from app.services.persistence import get_project_file_info as get_project_file_info_from_db


class ProjectFilesProxy(MutableMapping[int, dict[str, Any]]):
    def __init__(self) -> None:
        self._extras: dict[int, dict[str, Any]] = {}

    def _load(self, project_id: int) -> dict[str, Any] | None:
        base = get_project_file_info_from_db(project_id)
        if base is None:
            return None
        extras = self._extras.get(project_id, {})
        merged = {**base, **extras}
        self._extras[project_id] = merged
        return merged

    def __getitem__(self, key: int) -> dict[str, Any]:
        value = self._load(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: int, value: dict[str, Any]) -> None:
        current = self._load(key) or {}
        current.update(value)
        self._extras[key] = current

    def __delitem__(self, key: int) -> None:
        self._extras.pop(key, None)

    def __iter__(self) -> Iterator[int]:
        return iter(self._extras)

    def __len__(self) -> int:
        return len(self._extras)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, int) and self._load(key) is not None

    def get(self, key: int, default: Any = None) -> Any:
        value = self._load(key)
        return value if value is not None else default


PROJECT_FILES: MutableMapping[int, dict[str, Any]] = ProjectFilesProxy()
PROJECTS: list[dict[str, Any]] = []


def get_project_file_info(project_id: int) -> dict[str, Any] | None:
    return PROJECT_FILES.get(project_id)
