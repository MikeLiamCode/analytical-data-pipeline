from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def normalized_dir(self) -> Path:
        return self.root / "data" / "normalized"

    @property
    def analyses_dir(self) -> Path:
        return self.root / "data" / "analyses"


def default_paths() -> StoragePaths:
    # Repo root is assumed to be the current working directory when running via Docker Compose.
    return StoragePaths(root=Path.cwd())
