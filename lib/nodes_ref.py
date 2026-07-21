"""Lookup KEY категории CH6 из References_CH6 / Nodes_CH6."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from .excel_io import excel_read_engine
from .text_utils import TextNorm


@lru_cache(maxsize=4)
def load_ch6_key_map(base_dir: str, reference_file: str) -> dict[str, str]:
    path = Path(base_dir) / reference_file
    if not path.exists():
        return {}
    engine = excel_read_engine()
    try:
        df = pd.read_excel(path, sheet_name="Nodes_CH6", engine=engine)
    except Exception:
        df = pd.read_excel(path, sheet_name="Nodes_CH6")
    if "6th level" not in df.columns or "KEY" not in df.columns:
        return {}
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        ch6 = TextNorm.norm_customer_node(row["6th level"])
        key = TextNorm.key_value(row["KEY"])
        if ch6 and key:
            out[ch6] = key
    return out


def ch6_key_category(ch6_val: object, key_map: dict[str, str]) -> str:
    ch6 = TextNorm.norm_customer_node(ch6_val)
    if not ch6:
        return ""
    return key_map.get(ch6, "")


def ch6_keys_match(
    left_ch6: object,
    right_ch6: object,
    key_map: dict[str, str],
) -> bool:
    left = TextNorm.norm_customer_node(left_ch6)
    right = TextNorm.norm_customer_node(right_ch6)
    if not left or not right:
        return False
    if left == right:
        return True
    lk = key_map.get(left, "")
    rk = key_map.get(right, "")
    return bool(lk) and lk == rk
