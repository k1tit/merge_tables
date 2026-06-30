from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .constants import DEFAULT_SORG_DIRS, FILE_ALIASES, SORG_FILE_PREFIX_RE
from .text_utils import TextNorm

_SORG_FILE_REST_RE = re.compile(r"^380[1-6]\s+(.*)$", re.IGNORECASE)
_EXCEL_SUFFIXES = (".xlsx", ".xls", ".XLSX", ".XLS")


class PathResolver:
    """Выгрузки SOrg — в папке 3801–3806; справочники — в корне проекта."""

    def __init__(
        self,
        base_dir: Path,
        source_dir: str | None,
        reference_dir: str | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.source_dir = source_dir
        self.reference_dir = reference_dir

    @classmethod
    def from_config(cls, base_dir: Path, cfg: dict[str, Any]) -> PathResolver:
        def _opt(key: str) -> str | None:
            raw = cfg.get(key)
            if raw is None:
                return None
            text = str(raw).strip()
            return text or None

        return cls(base_dir, _opt("source_dir"), _opt("reference_dir"))

    @property
    def reference_root(self) -> Path:
        if self.reference_dir and self.reference_dir not in (".", ""):
            return self.base_dir / self.reference_dir
        return self.base_dir

    @property
    def data_root(self) -> Path:
        if self.source_dir:
            return self.base_dir / self.source_dir
        return self.base_dir

    @staticmethod
    def is_sorg_data_file(rel: str) -> bool:
        stem = Path(rel).stem.strip()
        return bool(SORG_FILE_PREFIX_RE.match(stem))

    def resolve(self, rel: str) -> Path:
        rel_stem = Path(rel).stem
        if rel_stem in FILE_ALIASES and not Path(rel).suffix:
            rel = FILE_ALIASES[rel_stem]

        path = Path(rel)
        if path.is_absolute():
            return self._first_existing([path]) or path

        for root in self._search_roots(rel):
            found = self._first_existing(self._candidates(root, path))
            if found is not None:
                return found

        if self.is_sorg_data_file(rel):
            alt = self._resolve_by_sorg_prefix(rel_stem)
            if alt is not None:
                return alt

        if rel_stem in ("Справочник Ключ-Иерархия",) or "Ключ-Иерархия" in rel_stem:
            found = self._find_by_headers(["Ключ", "Узел"], self.reference_root)
            if found:
                return found

        return self._candidates(self._search_roots(rel)[0], path)[0]

    def lookup_hint(self, rel: str) -> str:
        if self.is_sorg_data_file(rel):
            return f"папка SOrg: {self.data_root}"
        return f"справочники: {self.reference_root}"

    def _search_roots(self, rel: str) -> list[Path]:
        if self.is_sorg_data_file(rel):
            return [self.data_root]
        return [self.reference_root]

    @staticmethod
    def _candidates(root: Path, rel_path: Path) -> list[Path]:
        base = root / rel_path
        candidates = [base]
        if not rel_path.suffix:
            candidates.extend(base.with_suffix(ext) for ext in _EXCEL_SUFFIXES)
        else:
            candidates.append(base.with_suffix(rel_path.suffix.lower()))
            candidates.append(base.with_suffix(rel_path.suffix.upper()))
        return candidates

    @staticmethod
    def _first_existing(candidates: list[Path]) -> Path | None:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _find_by_headers(self, must_have: list[str], root: Path) -> Path | None:
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
