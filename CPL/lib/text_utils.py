from __future__ import annotations

from typing import Any

import pandas as pd

from .constants import ID_COLUMN_KEYS


class TextNorm:
    """Нормализация имён колонок и значений ключей."""

    @staticmethod
    def name(value: str) -> str:
        return str(value).strip().casefold()

    @staticmethod
    def key_value(val: Any) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, (int,)) or (isinstance(val, float) and val == int(val)):
            return str(int(val))
        return str(val).strip()

    @staticmethod
    def compact_key_part(val: Any) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        if isinstance(val, (int,)) or (isinstance(val, float) and val == int(val)):
            return str(int(val))
        text = str(val).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    @staticmethod
    def is_id_column(name: str) -> bool:
        n = TextNorm.name(name).rstrip(".")
        return n in ID_COLUMN_KEYS or n.startswith("customer")

    @staticmethod
    def split_aggregated(val: Any, *, separator: str = ", ") -> list[str]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return []
        text = str(val).strip()
        if not text:
            return []
        parts = text.split(separator) if separator else [text]
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def filled_count(series: pd.Series) -> int:
        return int(series.fillna("").astype(str).str.strip().ne("").sum())
