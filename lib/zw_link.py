from __future__ import annotations

from pathlib import Path

import pandas as pd

from .text_utils import TextNorm


def load_zw_partner_map(
    zw_path: Path,
    *,
    engine: str,
) -> tuple[set[str], dict[str, str]]:
    """KUNNR (sold-to) и KTONR (партнёр ZW) из файла 380N ZW."""
    zw = pd.read_excel(zw_path, usecols=["KUNNR", "KTONR"], engine=engine)
    zw["KUNNR"] = zw["KUNNR"].map(TextNorm.key_value)
    zw["KTONR"] = zw["KTONR"].map(TextNorm.key_value)
    kunnr_set = {k for k in zw["KUNNR"] if k}
    ktonr_map: dict[str, str] = {}
    for ktonr, kunnr in zip(zw["KTONR"], zw["KUNNR"], strict=False):
        if ktonr and ktonr not in ktonr_map:
            ktonr_map[ktonr] = kunnr
    return kunnr_set, ktonr_map


def sold_to_key(
    customer: object,
    *,
    kunnr_set: set[str],
    ktonr_map: dict[str, str],
) -> str:
    """Customer в ZW base/CH6: sold-to или партнёр → ключ sold-to для merge с Base."""
    c = TextNorm.key_value(customer)
    if not c:
        return ""
    if c in kunnr_set:
        return c
    return ktonr_map.get(c, c)
