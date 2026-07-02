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
    def excel_text(val: Any) -> str:
        """Строка для Excel-колонок с форматом «текст» (ИНН, SDst и т.п.)."""
        if val is None or pd.isna(val):
            return ""
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float) and val == int(val):
            return str(int(val))
        text = str(val).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    @staticmethod
    def format_text_column(
        val: Any,
        column: str,
        leading_zero: dict[str, int] | None = None,
    ) -> str:
        """Текст для Excel; для A8 и др. — ведущие нули (8 → 08, 030 без изменений)."""
        text = TextNorm.excel_text(val)
        if not text:
            return ""
        width = (leading_zero or {}).get(column)
        if width and text.isdigit() and len(text) < width:
            return text.zfill(width)
        return text

    @staticmethod
    def key_part(val: Any) -> str:
        """Фрагмент для Key: строки как есть (036), числа без .0."""
        if val is None or pd.isna(val):
            return ""
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float) and val == int(val):
            return str(int(val))
        text = str(val).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    @staticmethod
    def key_value(val: Any) -> str:
        if val is None or pd.isna(val):
            return ""
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, (int,)) or (isinstance(val, float) and val == int(val)):
            return str(int(val))
        return str(val).strip()

    @staticmethod
    def trade_name_key(val: Any) -> str:
        """Ключ Trade Name / Search Term 2: 3651.0 и 03651 → 3651."""
        v = TextNorm.key_value(val)
        if v.isdigit():
            return str(int(v))
        return v

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
    def norm_customer_node(val: Any) -> str:
        """Нормализация номера узла CH6 для сравнения в Check (38110501 = 38110501.0)."""
        v = TextNorm.key_value(val)
        if not v:
            return ""
        if v.isdigit():
            return str(int(v))
        return v.upper()

    @staticmethod
    def customer_node_in_list(ch6_val: Any, compare_val: Any, *, separator: str = ", ") -> bool:
        ch6 = TextNorm.norm_customer_node(ch6_val)
        if not ch6:
            return False
        candidates = {
            TextNorm.norm_customer_node(v)
            for v in TextNorm.split_aggregated(compare_val, separator=separator)
        }
        candidates.discard("")
        return ch6 in candidates

    @staticmethod
    def split_aggregated(val: Any, *, separator: str = ", ") -> list[str]:
        if val is None or pd.isna(val):
            return []
        text = str(val).strip()
        if not text:
            return []
        parts = text.split(separator) if separator else [text]
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def filled_count(series: pd.Series) -> int:
        return int(series.fillna("").astype(str).str.strip().ne("").sum())
