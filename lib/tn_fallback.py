"""TN_* только из справочника по Trade Name (без подстановки из CH6)."""

from __future__ import annotations

import pandas as pd

from .text_utils import TextNorm

_TN_COLS = ("TN_CH6", "TN_CH6_Name", "TN_CGrp")


def finalize_tn_columns(
    df: pd.DataFrame,
    *,
    trade_name_column: str = "Trade Name",
) -> pd.DataFrame:
    """Если Trade Name пустой — очистить TN_* (не копировать из CH6)."""
    if trade_name_column not in df.columns:
        return df

    out = df.copy()
    for col in _TN_COLS:
        if col not in out.columns:
            out[col] = pd.NA

    trade_empty = ~out[trade_name_column].map(TextNorm.key_value).astype(bool)
    if not trade_empty.any():
        return out

    for col in _TN_COLS:
        if col in out.columns:
            out.loc[trade_empty, col] = pd.NA
    return out


def tn_filled_count(df: pd.DataFrame) -> int:
    if "TN_CH6" not in df.columns:
        return 0
    return TextNorm.filled_count(df["TN_CH6"])
