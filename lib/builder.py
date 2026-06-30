# -*- coding: utf-8 -*-
from __future__ import annotations

from . import win_utf8  # noqa: F401

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .at_work_ref import (
    at_work_output_sheet_name,
    ensure_at_work_reference_file,
    load_at_work_a8_values,
    load_at_work_reference_df,
)
from .checks import CheckEngine
from .computed import ComputedColumnsApplier
from .constants import REQUIRED_CH6_COLUMNS, SCRIPT_VERSION
from .context import BuildContext
from .log_sink import emit, open_build_log
from .text_utils import TextNorm
from .merger import DataMerger
from .merge_keys import MergeKeysParser
from .sources import ExcelSourceReader


def excel_read_engine(preferred: str | None) -> str:
    if preferred:
        return preferred
    try:
        import python_calamine  # noqa: F401

        return "calamine"
    except ImportError:
        return "openpyxl"


def resolve_output_path(ctx: BuildContext) -> Path:
    """Имя отчёта: output_file из config, плейсхолдер {sorg} → 3801–3806."""
    template = str(ctx.config.get("output_file", "merge_columns_{sorg}.xlsx"))
    return ctx.base_dir / template.format(sorg=ctx.sorg)


class ReportBuilder:
    """Оркестрация сборки merge_columns.xlsx."""

    def __init__(
        self,
        config_path: Path,
        *,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        self.config_path = config_path.resolve()
        self.base_dir = self.config_path.parent
        if cfg is None:
            with self.config_path.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        self.raw_cfg = cfg

    def run(self, log: Callable[[str], None] | None = None) -> Path:
        ctx = BuildContext(
            base_dir=self.base_dir,
            config_path=self.config_path,
            config=self.raw_cfg,
            read_engine=excel_read_engine(self.raw_cfg.get("excel_read_engine")),
            write_engine=str(self.raw_cfg.get("excel_write_engine", "openpyxl")),
            lookup_dedupe=bool(self.raw_cfg.get("lookup_dedupe", True)),
            verbose=bool(self.raw_cfg.get("verbose", True)),
            default_merge=self.raw_cfg.get("merge_on"),
            log=log,
        )
        return self._build(ctx)

    def _build(self, ctx: BuildContext) -> Path:
        ctx.log_file = ctx.base_dir / "merge_build.log"
        if not ctx.log:
            ctx.log_file = open_build_log(ctx.base_dir)
            emit(ctx, f"  журнал: {ctx.log_file}")
        elif ctx.log:
            ctx.log(f"  журнал: {ctx.log_file.resolve()}\n")

        t0 = time.perf_counter()
        cfg = ctx.config
        sources: list[dict[str, Any]] = cfg.get("sources") or []
        if not sources:
            raise ValueError("В config.yaml не задан ни один источник (sources).")

        out_path = resolve_output_path(ctx)
        reader = ExcelSourceReader(ctx)
        merger = DataMerger(ctx)
        keys = MergeKeysParser()

        self._print_header(ctx, out_path, sources)

        frames: list[pd.DataFrame] = []
        n_src = len(sources)
        for i, src in enumerate(sources):
            if ctx.verbose:
                emit(
                    ctx,
                    f"  [{i + 1}/{n_src}] чтение: {src.get('file')!r}...",
                )
            merge_right: list[str] | None = None
            if i > 0:
                _, merge_right, _, _ = keys.parse_source(src, ctx.default_merge)
            frames.append(
                reader.read(
                    src,
                    merge_right=merge_right,
                    key_excel=src.get("key_excel"),
                )
            )
        if ctx.verbose:
            emit(ctx, f"  чтение ({ctx.read_engine}): {time.perf_counter() - t0:.1f} с")

        t1 = time.perf_counter()
        if ctx.verbose:
            emit(ctx, f"  merge_columns {SCRIPT_VERSION}, источников: {n_src}")
            if any(s.get("enrich_from") for s in sources):
                emit(
                    ctx,
                    f"  enrich_from ({ctx.zw_ch6_file}: ZW_CH6, ZW_CH6_Name)",
                )

        emit(ctx, "  объединение источников (merge)...")
        result = merger.merge_all(frames, sources)
        ref_path = ensure_at_work_reference_file(ctx.base_dir, cfg)
        if ref_path and ctx.verbose:
            emit(ctx, f"  справочник At Work&Education: {ref_path.name}")
        a8_ref_values = load_at_work_a8_values(ctx.base_dir, cfg)
        if ctx.verbose:
            emit(ctx, f"  поводы A8 в справочнике At Work: {len(a8_ref_values)}")
        emit(ctx, "  вычисляемые колонки (Key, Customer Key)...")
        result = ComputedColumnsApplier.apply(
            result,
            cfg.get("computed_columns"),
            a8_ref_values=a8_ref_values,
        )

        post_sources = cfg.get("post_sources") or []
        if post_sources:
            emit(ctx, "  справочники после Key (post-merge)...")
            result = merger.merge_post(result, post_sources)

        emit(ctx, "  проверки (Check ...)...")
        checks = cfg.get("checks")
        result = CheckEngine().apply(result, checks)
        result = self._order_columns(result, cfg, ctx)

        if ctx.verbose:
            emit(
                ctx,
                f"  merge+проверки: {time.perf_counter() - t1:.1f} с, "
                f"строк: {len(result)}",
            )

        self._require_columns(result)
        t2 = time.perf_counter()
        text_columns = [str(c) for c in (cfg.get("text_columns") or [])]
        ref_df = load_at_work_reference_df(ctx.base_dir, cfg)
        extra_sheets: list[tuple[str, pd.DataFrame]] = []
        if ref_df is not None and not ref_df.empty:
            ref_sheet = at_work_output_sheet_name(cfg)
            extra_sheets.append((ref_sheet, ref_df))
            ref_col = str((cfg.get("at_work_a8_reference") or {}).get("column", "A8"))
            if ref_col in ref_df.columns and ref_col not in text_columns:
                text_columns = list(text_columns) + [ref_col]
            emit(ctx, f"  запись Excel ({ctx.write_engine}) + лист {ref_sheet!r}...")
        else:
            emit(ctx, f"  запись Excel ({ctx.write_engine})...")
        self._write(
            result,
            out_path,
            ctx.write_engine,
            text_columns=text_columns,
            extra_sheets=extra_sheets or None,
        )
        if ctx.verbose:
            emit(ctx, f"  запись: {time.perf_counter() - t2:.1f} с")
        self._print_summary(result, checks, ctx, t0)
        return out_path

    def _print_header(
        self,
        ctx: BuildContext,
        out_path: Path,
        sources: list[dict[str, Any]],
    ) -> None:
        has_enrich = any(s.get("enrich_from") for s in sources)
        has_ch6 = any(
            "CH6" in str(s.get("file", "")) and s.get("file") != ctx.zw_file
            for s in sources
        )
        emit(ctx, f"=== merge_columns {SCRIPT_VERSION} ===")
        emit(ctx, f"  config: {ctx.config_path}")
        emit(ctx, f"  Папка данных: {ctx.source_dir}, префикс файлов: {ctx.sorg}")
        emit(ctx, f"  output: {out_path.resolve()}")
        if not has_enrich:
            emit(ctx, f"  ОШИБКА КОНФИГА: нет enrich_from для {ctx.zw_ch6_file!r}")
        elif ctx.verbose:
            emit(ctx, f"  enrich_from: OK ({ctx.zw_ch6_file} -> {ctx.zw_file})")
        if not has_ch6 and ctx.verbose:
            emit(ctx, f"  запасной источник {ctx.zw_ch6_file}: нет")
        if ctx.default_merge is not None and ctx.verbose:
            emit(ctx, "  ВНИМАНИЕ: удалите merge_on из корня config.")

    def _order_columns(
        self,
        result: pd.DataFrame,
        cfg: dict[str, Any],
        ctx: BuildContext,
    ) -> pd.DataFrame:
        col_order = cfg.get("column_order")
        if col_order:
            if isinstance(col_order, str):
                col_order = [col_order]
            col_order = [str(c) for c in col_order]
            absent = [c for c in col_order if c not in result.columns]
            if absent:
                emit(
                    ctx,
                    f"  ОШИБКА: колонок нет в данных: {absent!r}. "
                    f"Добавляем пустые колонки.",
                )
                for col in absent:
                    result[col] = pd.NA
            ordered = [c for c in col_order if c in result.columns]
            return result[ordered]

        last_columns = cfg.get("last_columns")
        if last_columns:
            if isinstance(last_columns, str):
                last_columns = [last_columns]
            order = [c for c in result.columns if c not in last_columns]
            for col in last_columns:
                if col in result.columns:
                    order.append(col)
            return result[order]
        return result

    @staticmethod
    def _require_columns(df: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_CH6_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"В отчёте нет обязательных колонок: {missing!r}. "
                f"Есть: {list(df.columns)}"
            )

    @staticmethod
    def _write(
        df: pd.DataFrame,
        out_path: Path,
        write_engine: str,
        *,
        text_columns: list[str] | None = None,
        extra_sheets: list[tuple[str, pd.DataFrame]] | None = None,
    ) -> None:
        text_cols = [c for c in (text_columns or []) if c in df.columns]
        out = df.copy()
        for col in text_cols:
            out[col] = out[col].map(TextNorm.excel_text)

        suffix = out_path.suffix.lower()
        if suffix == ".csv":
            out.to_csv(out_path, index=False, encoding="utf-8-sig")
            return

        engine = "xlsxwriter" if write_engine == "xlsxwriter" else "openpyxl"
        try:
            with pd.ExcelWriter(out_path, engine=engine) as writer:
                main_sheet = "Sheet1"
                out.to_excel(writer, index=False, sheet_name=main_sheet)
                ReportBuilder._apply_text_columns(
                    writer, engine, main_sheet, out, text_cols
                )

                for sheet_name, ref_raw in extra_sheets or []:
                    ref_out = ref_raw.copy()
                    ref_text = [
                        c
                        for c in (text_columns or [])
                        if c in ref_out.columns
                    ]
                    for col in ref_text:
                        ref_out[col] = ref_out[col].map(TextNorm.excel_text)
                    ref_out.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                    ReportBuilder._apply_text_columns(
                        writer, engine, sheet_name[:31], ref_out, ref_text
                    )
        except PermissionError as e:
            raise PermissionError(
                f"Не удалось записать {out_path}: файл открыт в Excel или заблокирован. "
                f"Закройте файл и запустите скрипт снова."
            ) from e

    @staticmethod
    def _apply_text_columns(
        writer: pd.ExcelWriter,
        engine: str,
        sheet: str,
        df: pd.DataFrame,
        text_cols: list[str],
    ) -> None:
        if not text_cols:
            return
        if engine == "openpyxl":
            ws = writer.sheets[sheet]
            for col_name in text_cols:
                col_idx = df.columns.get_loc(col_name) + 1
                for row in range(2, len(df) + 2):
                    ws.cell(row=row, column=col_idx).number_format = "@"
        else:
            ws = writer.sheets[sheet]
            text_fmt = writer.book.add_format({"num_format": "@"})
            for col_name in text_cols:
                col_idx = df.columns.get_loc(col_name)
                ws.set_column(col_idx, col_idx, None, text_fmt)

    def _print_summary(
        self,
        result: pd.DataFrame,
        checks: list[dict[str, Any]] | None,
        ctx: BuildContext,
        t0: float,
    ) -> None:
        if checks:
            for spec in checks:
                name = str(spec["name"])
                fail_label = str(spec.get("fail", "false"))
                if name in result.columns:
                    fails = int((result[name] == fail_label).sum())
                    emit(ctx, f"  {name}: {fails} строк с {fail_label!r} из {len(result)}")

        if not ctx.verbose:
            return

        emit(ctx, f"  колонки: {', '.join(str(c) for c in result.columns)}")
        for track_col in (
            "ZW_CH6_Name",
            "ZW_CH6",
            "ZW",
            "ZW_SO",
            "ZW_A7",
            f"{ctx.sorg} ZW",
        ):
            if track_col in result.columns:
                filled = int(
                    result[track_col].fillna("").astype(str).str.strip().ne("").sum()
                )
                emit(ctx, f"  {track_col}: заполнено {filled} из {len(result)} строк")

        zw_col = f"{ctx.sorg} ZW"
        if (
            "ZW" not in result.columns
            and "ZW_SO" not in result.columns
            and zw_col not in result.columns
        ):
            emit(
                ctx,
                f"  ВНИМАНИЕ: нет колонки ZW — в config нужен «{ctx.zw_file}» с aggregate",
            )
        emit(ctx, f"  всего: {time.perf_counter() - t0:.1f} с")


def build_merge(
    config_path: Path,
    *,
    cfg: dict[str, Any] | None = None,
    log: Callable[[str], None] | None = None,
) -> Path:
    return ReportBuilder(config_path, cfg=cfg).run(log=log)
