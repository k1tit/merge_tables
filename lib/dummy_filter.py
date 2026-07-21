"""Исключить dummy-клиентов из базы."""

from __future__ import annotations

import pandas as pd

from .text_utils import TextNorm

_DUMMY_MARKERS = ("dumm", "дамми")


def is_dummy_name(name: object) -> bool:
    text = TextNorm.name(str(name or ""))
    return any(m in text for m in _DUMMY_MARKERS)


def filter_dummy_clients(df: pd.DataFrame, *, name_column: str = "Name") -> pd.DataFrame:
    if name_column not in df.columns or df.empty:
        return df
    mask = df[name_column].map(is_dummy_name)
    return df.loc[~mask].copy()
