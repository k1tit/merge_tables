"""Key_IN_SO / ZW_Key_IN_SO — только при cross-SO (SOrg. ≠ ZW_SO)."""

from __future__ import annotations

import pandas as pd

from .text_utils import TextNorm

_KEY_IN_SO_COLS = ("Key_IN_SO", "ZW_Key_IN_SO")


def clear_key_in_so_unless_cross_so(df: pd.DataFrame) -> pd.DataFrame:
    """Очистить Key_IN_SO* если SOrg.=ZW_SO или одно из SO пустое."""
    if not any(c in df.columns for c in _KEY_IN_SO_COLS):
        return df

    out = df.copy()
    for col in _KEY_IN_SO_COLS:
        if col not in out.columns:
            out[col] = pd.NA

    if "SOrg." not in out.columns or "ZW_SO" not in out.columns:
        for col in _KEY_IN_SO_COLS:
            out[col] = pd.NA
        return out

    sorg = out["SOrg."].map(TextNorm.key_value)
    zw_so = out["ZW_SO"].map(TextNorm.key_value)
    clear = ~sorg.astype(bool) | ~zw_so.astype(bool) | (sorg == zw_so)
    if clear.any():
        for col in _KEY_IN_SO_COLS:
            out.loc[clear, col] = pd.NA
    return out
