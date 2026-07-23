"""TN_CH6 / TN_CH6_Name / TN_CGrp — join Base по Trade Name → Nodes_CH6."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .context import BuildContext
from .excel_io import excel_read_engine, excel_write_engine
from .log_sink import emit
from .merger import DataMerger
from .sources import ExcelSourceReader
from .tn_fallback import finalize_tn_columns, tn_filled_count
from .text_utils import TextNorm

TN_REF_SPEC: dict[str, Any] = {
    "file": "References_CH6.xlsx",
    "sheet": "Nodes_CH6",
    "merge_on": {
        "left": ["Trade Name"],
        "right": ["Trade Name"],
    },
    "key_excel": {
        "Trade Name": "TRADE NAME",
    },
    "aggregate": {
        "TN_CH6": {
            "source": "6th level",
            "separator": ", ",
            "unique": True,
        },
        "TN_CH6_Name": {
            "source": "6th level_name",
            "separator": ", ",
            "unique": True,
        },
        "TN_CGrp": {
            "source": "6th level_CGrp",
            "separator": ", ",
            "unique": True,
        },
    },
    "columns": [
        {"name": "6th level", "source": "6th level"},
        {"name": "6th level_name", "source": "6th level_name"},
        {"name": "6th level_CGrp", "source": "6th level_CGrp"},
    ],
}

TN_OUTPUT_COLUMNS = ("TN_CH6", "TN_CH6_Name", "TN_CGrp")
TN_KEY_COLUMNS = ("SOrg.", "Customer", "Trade Name")


def make_context(
    base_dir: Path,
    config_path: Path,
    cfg: dict[str, Any],
    *,
    verbose: bool = True,
    log=None,
) -> BuildContext:
    return BuildContext(
        base_dir=base_dir,
        config_path=config_path,
        config=cfg,
        read_engine=excel_read_engine(cfg.get("excel_read_engine")),
        write_engine=excel_write_engine(cfg.get("excel_write_engine")),
        lookup_dedupe=True,
        verbose=verbose,
        log=log,
    )


def _base_spec(ctx: BuildContext, *, full: bool) -> dict[str, Any]:
    if full:
        sources = ctx.config.get("sources") or []
        if sources:
            first = dict(sources[0])
            first.pop("read_dedupe", None)
            return first
    return {
        "file": f"{ctx.sorg_template} Base.xlsx",
        "sheet": 0,
        "columns": [
            "SOrg.",
            "Customer",
            {"name": "Trade Name", "source": "Search Term 2"},
        ],
    }


def build_tn_columns(ctx: BuildContext, *, full: bool = False) -> pd.DataFrame:
    """Base + TN_* из Nodes_CH6 (ключ: Trade Name)."""
    reader = ExcelSourceReader(ctx)
    merger = DataMerger(ctx)

    base = reader.read(_base_spec(ctx, full=full))
    ref = reader.read(
        TN_REF_SPEC,
        merge_right=["Trade Name"],
        key_excel=TN_REF_SPEC.get("key_excel"),
    )

    result = merger._merge_source_into(
        base,
        TN_REF_SPEC,
        ref,
        label="tn",
    )
    if full or "CH6" in result.columns:
        result = finalize_tn_columns(result)

    if ctx.verbose:
        filled = sum(TextNorm.filled_count(result[c]) for c in TN_OUTPUT_COLUMNS) // 3
        trade_filled = TextNorm.filled_count(result["Trade Name"]) if "Trade Name" in result.columns else 0
        emit(
            ctx,
            f"  TN lookup: Trade Name заполнен у {trade_filled} строк, "
            f"TN_CH6 у {filled} строк из {len(result)}",
        )
    return result


def resolve_output_path(
    ctx: BuildContext,
    out: Path | None = None,
) -> Path:
    if out is not None:
        return out.resolve()
    sorg = ctx.sorg
    return ctx.base_dir / f"merge_{sorg}" / f"tn_columns_{sorg}.xlsx"


def compact_tn_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Только ключи и TN_* (без дублей по SOrg.+Customer+Trade Name)."""
    cols = [c for c in TN_KEY_COLUMNS if c in df.columns]
    cols.extend(c for c in TN_OUTPUT_COLUMNS if c in df.columns)
    out = df[cols].copy()
    key_cols = [c for c in ("SOrg.", "Trade Name") if c in out.columns]
    if key_cols:
        out = out.drop_duplicates(subset=key_cols, keep="first")
    return out


def write_tn_columns(
    ctx: BuildContext,
    df: pd.DataFrame,
    out: Path | None = None,
    *,
    compact: bool = True,
) -> Path:
    out_path = resolve_output_path(ctx, out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = compact_tn_frame(df) if compact else df
    to_write.to_excel(out_path, index=False, engine=ctx.write_engine)
    if ctx.verbose:
        emit(ctx, f"  записано: {out_path}")
    return out_path
