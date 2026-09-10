from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import TimetableProject, default_periods


class StorageError(RuntimeError):
    pass


class ProjectStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> TimetableProject:
        if not self.path.exists():
            return TimetableProject(periods=default_periods())
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
            return TimetableProject.from_dict(data)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StorageError(f"无法读取项目文件：{exc}") from exc

    def save(self, project: TimetableProject) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # 同目录原子替换，避免程序中断留下半个 JSON 文件。
            with NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False, suffix=".tmp"
            ) as stream:
                json.dump(project.to_dict(), stream, ensure_ascii=False, indent=2)
                temporary = Path(stream.name)
            os.replace(temporary, self.path)
        except OSError as exc:
            raise StorageError(f"无法保存项目：{exc}") from exc
