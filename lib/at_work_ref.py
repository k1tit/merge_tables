from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .paths import PathResolver
from .text_utils import TextNorm


def norm_a8_lookup(val: Any) -> str:
    """Каноническое значение A8 для сравнения со справочником (030 и 30 → одно)."""
    part = TextNorm.key_part(val)
    if not part:
        return ""
    if part.isdigit():
        return str(int(part))
    return part.upper()


def load_at_work_reference_df(base_dir: Path, cfg: dict[str, Any]) -> pd.DataFrame | None:
    """Таблица справочника At Work&Education для листа в merge_columns.xlsx."""
    ref = cfg.get("at_work_a8_reference") or {}
    column = str(ref.get("column", "A8"))

    rel_file = ref.get("file")
    if rel_file:
        resolver = PathResolver.from_config(base_dir, cfg)
        path = resolver.resolve(str(rel_file))
        if path.exists():
            sheet = ref.get("sheet", "At Work")
            try:
                df = pd.read_excel(path, sheet_name=sheet, engine="calamine")
            except Exception:
                df = pd.read_excel(path, sheet_name=sheet)
            if not df.empty:
                return df

    raw_values = ref.get("values") or []
    if not raw_values:
        return None
    return pd.DataFrame({column: [TextNorm.excel_text(v) for v in raw_values]})


def at_work_output_sheet_name(cfg: dict[str, Any]) -> str:
    ref = cfg.get("at_work_a8_reference") or {}
    return str(ref.get("output_sheet", "Справочник At Work&Education")).strip()


def load_at_work_a8_values(base_dir: Path, cfg: dict[str, Any]) -> frozenset[str]:
    """Поводы потребления (A8) из справочника At Work & Education."""
    ref = cfg.get("at_work_a8_reference") or {}
    values: set[str] = set()

    for raw in ref.get("values") or []:
        norm = norm_a8_lookup(raw)
        if norm:
            values.add(norm)

    rel_file = ref.get("file")
    if rel_file:
        resolver = PathResolver.from_config(base_dir, cfg)
        path = resolver.resolve(str(rel_file))
        if path.exists():
            sheet = ref.get("sheet", 0)
            column = str(ref.get("column", "A8"))
            try:
                df = pd.read_excel(path, sheet_name=sheet, engine="calamine")
            except Exception:
                df = pd.read_excel(path, sheet_name=sheet)
            col = _resolve_column(df, column)
            for raw in df[col].dropna():
                norm = norm_a8_lookup(raw)
                if norm:
                    values.add(norm)

    return frozenset(values)


def ensure_at_work_reference_file(base_dir: Path, cfg: dict[str, Any]) -> Path | None:
    """Создать Excel-справочник из values в config, если файла ещё нет."""
    ref = cfg.get("at_work_a8_reference") or {}
    rel_file = ref.get("file")
    raw_values = ref.get("values")
    if not rel_file or not raw_values:
        return None
    path = PathResolver.from_config(base_dir, cfg).resolve(str(rel_file))
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet = str(ref.get("sheet", "At Work"))
    column = str(ref.get("column", "A8"))
    df = pd.DataFrame({column: [TextNorm.excel_text(v) for v in raw_values]})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)
    return path


def _resolve_column(df: pd.DataFrame, wanted: str) -> str:
    if wanted in df.columns:
        return wanted
    target = TextNorm.name(wanted)
    for col in df.columns:
        if TextNorm.name(str(col)) == target:
            return str(col)
    raise KeyError(
        f"В справочнике At Work&Education нет колонки {wanted!r}. "
        f"Есть: {list(df.columns)}"
    )
