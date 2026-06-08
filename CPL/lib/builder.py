from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .checks import CheckEngine
from .computed import ComputedColumnsApplier
from .constants import REQUIRED_CH6_COLUMNS, SCRIPT_VERSION
from .context import BuildContext
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

    def run(self) -> Path:
        ctx = BuildContext(
            base_dir=self.base_dir,
            config_path=self.config_path,
            config=self.raw_cfg,
            read_engine=excel_read_engine(self.raw_cfg.get("excel_read_engine")),
            write_engine=str(self.raw_cfg.get("excel_write_engine", "openpyxl")),
            lookup_dedupe=bool(self.raw_cfg.get("lookup_dedupe", True)),
            verbose=bool(self.raw_cfg.get("verbose", True)),
            default_merge=self.raw_cfg.get("merge_on"),
        )
        return self._build(ctx)

    def _build(self, ctx: BuildContext) -> Path:
        t0 = time.perf_counter()
        cfg = ctx.config
        sources: list[dict[str, Any]] = cfg.get("sources") or []
        if not sources:
            raise ValueError("В config.yaml не задан ни один источник (sources).")

        out_path = ctx.base_dir / cfg.get("output_file", "merge_columns.xlsx")
        reader = ExcelSourceReader(ctx)
        merger = DataMerger(ctx)
        keys = MergeKeysParser()

        self._print_header(ctx, out_path, sources)

        frames: list[pd.DataFrame] = []
        for i, src in enumerate(sources):
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
            print(f"  чтение ({ctx.read_engine}): {time.perf_counter() - t0:.1f} с")

        t1 = time.perf_counter()
        if ctx.verbose:
            print(
                f"  merge_columns {SCRIPT_VERSION}, источников: {len(sources)}"
            )
            if any(s.get("enrich_from") for s in sources):
                print(
                    f"  config: enrich_from ({ctx.zw_ch6_file}: HgLvCust., ZW_CH6_Name)"
                )

        result = merger.merge_all(frames, sources)
        result = ComputedColumnsApplier.apply(result, cfg.get("computed_columns"))

        post_sources = cfg.get("post_sources") or []
        if post_sources:
            result = merger.merge_post(result, post_sources)

        checks = cfg.get("checks")
        result = CheckEngine().apply(result, checks)
        result = self._order_columns(result, cfg, ctx)

        if ctx.verbose:
            print(
                f"  merge+проверки: {time.perf_counter() - t1:.1f} с, "
                f"строк: {len(result)}"
            )

        self._require_columns(result)
        t2 = time.perf_counter()
        self._write(result, out_path, ctx.write_engine)
        if ctx.verbose:
            print(f"  запись ({ctx.write_engine}): {time.perf_counter() - t2:.1f} с")
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
        print(f"=== merge_columns {SCRIPT_VERSION} ===")
        print(f"  config: {ctx.config_path}")
        print(f"  SOrg / source_dir: {ctx.sorg}  (шаблон: {ctx.sorg_template})")
        print(f"  output: {out_path.resolve()}")
        if not has_enrich:
            print(
                f"  ОШИБКА КОНФИГА: нет enrich_from для {ctx.zw_ch6_file!r}"
            )
        elif ctx.verbose:
            print(f"  enrich_from: OK ({ctx.zw_ch6_file} -> {ctx.zw_file})")
        if not has_ch6 and ctx.verbose:
            print(f"  запасной источник {ctx.zw_ch6_file}: нет")
        if ctx.default_merge is not None and ctx.verbose:
            print("  ВНИМАНИЕ: удалите merge_on из корня config.")

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
                print(
                    f"  ОШИБКА: колонок нет в данных: {absent!r}. "
                    f"Добавляем пустые колонки."
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
    def _write(df: pd.DataFrame, out_path: Path, write_engine: str) -> None:
        suffix = out_path.suffix.lower()
        if suffix == ".csv":
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            return
        engine = "xlsxwriter" if write_engine == "xlsxwriter" else "openpyxl"
        df.to_excel(out_path, index=False, engine=engine)

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
                    print(f"  {name}: {fails} строк с {fail_label!r} из {len(result)}")

        if not ctx.verbose:
            return

        print(f"  колонки: {', '.join(str(c) for c in result.columns)}")
        for track_col in (
            "ZW_CH6_Name",
            "ZW_CH6",
            "HgLvCust.",
            "ZW",
            "ZW_SO",
            "ZW_A7",
            f"{ctx.sorg} ZW",
        ):
            if track_col in result.columns:
                filled = int(
                    result[track_col].fillna("").astype(str).str.strip().ne("").sum()
                )
                print(f"  {track_col}: заполнено {filled} из {len(result)} строк")

        zw_col = f"{ctx.sorg} ZW"
        if (
            "ZW" not in result.columns
            and "ZW_SO" not in result.columns
            and zw_col not in result.columns
        ):
            print(
                f"  ВНИМАНИЕ: нет колонки ZW — в config нужен «{ctx.zw_file}» с aggregate"
            )
        print(f"  всего: {time.perf_counter() - t0:.1f} с")


def build_merge(
    config_path: Path,
    *,
    cfg: dict[str, Any] | None = None,
) -> Path:
    return ReportBuilder(config_path, cfg=cfg).run()
