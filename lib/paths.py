from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .constants import DEFAULT_SORG_DIRS, FILE_ALIASES
from .text_utils import TextNorm

_SORG_FILE_REST_RE = re.compile(r"^380[1-6]\s+(.*)$", re.IGNORECASE)


class PathResolver:
    """Поиск Excel-файлов в папке SOrg."""

    def __init__(self, base_dir: Path, source_dir: str | None) -> None:
        self.base_dir = base_dir
        self.source_dir = source_dir

    @property
    def data_root(self) -> Path:
        if self.source_dir:
            return self.base_dir / self.source_dir
        return self.base_dir

    def resolve(self, rel: str) -> Path:
        aliases = FILE_ALIASES
        rel_stem = Path(rel).stem
        if rel_stem in aliases and not Path(rel).suffix:
            rel = aliases[rel_stem]

        path = Path(rel)
        if path.is_absolute():
            candidates = [path]
        else:
            candidates = [self.data_root / path]

        if not path.suffix:
            candidates.extend(
                [candidates[0].with_suffix(ext) for ext in (".xlsx", ".xls")]
            )

        for candidate in candidates:
            if candidate.exists():
                return candidate

        alt = self._resolve_by_sorg_prefix(rel_stem)
        if alt is not None:
            return alt

        if rel_stem in ("Справочник Ключ-Иерархия",) or "Ключ-Иерархия" in rel_stem:
            found = self._find_by_headers(["Ключ", "Узел"])
            if found:
                return found

        return candidates[0]

    def _find_by_headers(self, must_have: list[str]) -> Path | None:
        root = self.data_root
        if not root.is_dir():
            return None
        need = {TextNorm.name(h) for h in must_have}
        for path in sorted(root.glob("*.xlsx")) + sorted(root.glob("*.xls")):
            try:
                header = pd.read_excel(path, nrows=0, engine="calamine")
            except Exception:
                try:
                    header = pd.read_excel(path, nrows=0)
                except Exception:
                    continue
            found = {TextNorm.name(str(c)) for c in header.columns}
            if need.issubset(found):
                return path
            if need == {TextNorm.name("Ключ"), TextNorm.name("Узел")}:
                if TextNorm.name("Ключ") in found and (
                    TextNorm.name("Иерархия") in found
                    or TextNorm.name("Узел") in found
                ):
                    return path
        return None

    def _resolve_by_sorg_prefix(self, rel_stem: str) -> Path | None:
        """«3805 Base» → файл «380* Base» в папке данных (если префикс в имени другой)."""
        match = _SORG_FILE_REST_RE.match(rel_stem.strip())
        if not match or not self.data_root.is_dir():
            return None
        rest = match.group(1).strip()
        if not rest:
            return None
        for code in DEFAULT_SORG_DIRS:
            for ext in (".xlsx", ".xls"):
                candidate = self.data_root / f"{code} {rest}{ext}"
                if candidate.exists():
                    return candidate
            candidate = self.data_root / f"{code} {rest}"
            if candidate.exists():
                return candidate
        return None
