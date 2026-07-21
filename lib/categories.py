"""Взаимоисключающие категории клиентов (7 файлов)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .text_utils import TextNorm

KA_CGRP = frozenset({"S", "F", "K", "Q"})
IN_CGRP_ABH = frozenset({"A", "B", "H"})
ZW_A7_IN = frozenset({"235", "249"})

CATEGORY_ORDER: list[tuple[str, str]] = [
    ("Trade Name", "Trade Name.xlsx"),
    ("Q+Vend.", "Q+Vend.xlsx"),
    ("IN_ZW_235&249", "IN_ZW_235&249.xlsx"),
    ("IN_Partner_CH6", "IN_Partner_CH6.xlsx"),
    ("A DI", "A DI.xlsx"),
    ("B DI", "B DI.xlsx"),
    ("Direct_Rest", "Direct_Rest.xlsx"),
]


def _filled(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def _norm_upper(series: pd.Series) -> pd.Series:
    return series.map(lambda v: TextNorm.key_value(v).upper())


def assign_categories(df: pd.DataFrame) -> pd.Series:
    """Присвоить категорию каждой строке (первое совпадение по порядку)."""
    n = len(df)
    result = pd.Series(["Direct_Rest"] * n, index=df.index, dtype=object)
    assigned = pd.Series(False, index=df.index)

    trade_col = "Trade Name"
    if trade_col in df.columns:
        m = _filled(df[trade_col])
        result.loc[m & ~assigned] = "Trade Name"
        assigned |= m

    cgrp = _norm_upper(df["CGrp"]) if "CGrp" in df.columns else pd.Series("", index=df.index)
    a7 = df["A7"].map(TextNorm.key_value) if "A7" in df.columns else pd.Series("", index=df.index)
    grp4 = _norm_upper(df["Grp4"]) if "Grp4" in df.columns else pd.Series("", index=df.index)
    zw_a7 = (
        df["ZW_A7"].map(TextNorm.key_value) if "ZW_A7" in df.columns else pd.Series("", index=df.index)
    )

    m = (~assigned) & ((cgrp == "Q") | (a7 == "246"))
    result.loc[m] = "Q+Vend."
    assigned |= m

    m = (
        (~assigned)
        & (grp4 == "IN")
        & cgrp.isin(IN_CGRP_ABH)
        & zw_a7.isin(ZW_A7_IN)
    )
    result.loc[m] = "IN_ZW_235&249"
    assigned |= m

    m = (~assigned) & (grp4 == "IN")
    result.loc[m] = "IN_Partner_CH6"
    assigned |= m

    m = (~assigned) & (cgrp == "A") & (grp4 == "DI")
    result.loc[m] = "A DI"
    assigned |= m

    m = (~assigned) & (cgrp == "B") & (grp4 == "DI")
    result.loc[m] = "B DI"
    assigned |= m

    return result


def split_by_category(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if "Category" not in df.columns:
        out = df.copy()
        out["Category"] = assign_categories(out)
        df = out
    parts: dict[str, pd.DataFrame] = {}
    for cat, _fname in CATEGORY_ORDER:
        parts[cat] = df.loc[df["Category"] == cat].copy()
    return parts


def category_filenames(cfg: dict[str, Any] | None = None) -> dict[str, str]:
    spec = (cfg or {}).get("category_splits") or {}
    files = spec.get("files") or []
    mapping = {cat: fname for cat, fname in CATEGORY_ORDER}
    for item in files:
        if isinstance(item, dict):
            cat = str(item.get("category", "")).strip()
            fname = str(item.get("file", "")).strip()
            if cat and fname:
                mapping[cat] = fname
    return mapping
