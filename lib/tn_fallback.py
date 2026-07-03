"""TN_* для строк без Trade Name — из CH6 sold-to."""

from __future__ import annotations

import pandas as pd

from .text_utils import TextNorm

_TN_COLS = ("TN_CH6", "TN_CH6_Name", "TN_CGrp")
_CH6_COLS = ("CH6", "CH6_Name", "CH6_CGrp")


def fill_tn_from_ch6(df: pd.DataFrame) -> pd.DataFrame:
    """Если TN_CH6 пустой, а CH6 есть — заполнить TN_* из CH6/CH6_Name/CH6_CGrp."""
    if "CH6" not in df.columns:
        return df

    out = df.copy()
    for col in _TN_COLS:
        if col not in out.columns:
            out[col] = pd.NA

    tn_empty = ~out["TN_CH6"].map(TextNorm.key_value).astype(bool)
    ch6_filled = out["CH6"].map(TextNorm.key_value).astype(bool)
    mask = tn_empty & ch6_filled
    if not mask.any():
        return out

    for tn, ch6 in zip(_TN_COLS, _CH6_COLS, strict=True):
        if ch6 in out.columns:
            out.loc[mask, tn] = out.loc[mask, ch6]
    return out


def tn_filled_count(df: pd.DataFrame) -> int:
    if "TN_CH6" not in df.columns:
        return 0
    return TextNorm.filled_count(df["TN_CH6"])
