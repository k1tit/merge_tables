from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .column_resolver import ColumnResolver, ColumnSpecParser
from .computed import ComputedColumnsApplier
from .constants import DEFAULT_SORG_DIRS
from .context import BuildContext
from .log_sink import emit
from .paths import PathResolver
from .text_utils import TextNorm
from .zw_link import load_zw_partner_map, sold_to_key

_ZW_FILE_REST_RE = re.compile(r"^380[1-6]\s+(zw(?:\s+base|\s+ch6)?)$", re.IGNORECASE)


class ExcelSourceReader:
    """Чтение одного источника из config (sources / post_sources / enrich_from)."""

    def __init__(self, ctx: BuildContext) -> None:
        self.ctx = ctx
        self.paths = PathResolver.from_config(ctx.base_dir, ctx.config)
        self._zw_kunnr: set[str] | None = None
        self._zw_ktonr_map: dict[str, str] | None = None

    def _zw_partner_lookup(self) -> tuple[set[str], dict[str, str]]:
        if self._zw_kunnr is None:
            frames: list[pd.DataFrame] = []
            for code in DEFAULT_SORG_DIRS:
                path = self.ctx.base_dir / code / f"{code} ZW.xlsx"
                if not path.exists():
                    continue
                frames.append(
                    pd.read_excel(
                        path, usecols=["KUNNR", "KTONR"], engine=self.ctx.read_engine
                    )
                )
            if not frames:
                path = self.paths.resolve(f"{self.ctx.sorg_template} ZW")
                if path.exists():
                    self._zw_kunnr, self._zw_ktonr_map = load_zw_partner_map(
                        path, engine=self.ctx.read_engine
                    )
                else:
                    self._zw_kunnr = set()
                    self._zw_ktonr_map = {}
            else:
                zw = pd.concat(frames, ignore_index=True)
                zw["KUNNR"] = zw["KUNNR"].map(TextNorm.key_value)
                zw["KTONR"] = zw["KTONR"].map(TextNorm.key_value)
                self._zw_kunnr = {k for k in zw["KUNNR"] if k}
                self._zw_ktonr_map = {}
                for ktonr, kunnr in zip(zw["KTONR"], zw["KUNNR"], strict=False):
                    if ktonr and ktonr not in self._zw_ktonr_map:
                        self._zw_ktonr_map[ktonr] = kunnr
        return self._zw_kunnr, self._zw_ktonr_map

    @staticmethod
    def _zw_kind(rel: str) -> str | None:
        match = _ZW_FILE_REST_RE.match(Path(rel).stem.strip())
        return match.group(1).casefold() if match else None

    def _all_sorg_paths(self, rel: str) -> list[Path]:
        kind = self._zw_kind(rel)
        if not kind:
            return [self.paths.resolve(rel)]
        paths: list[Path] = []
        for code in DEFAULT_SORG_DIRS:
            for ext in (".xlsx", ".xls"):
                candidate = self.ctx.base_dir / code / f"{code} {kind}{ext}"
                if candidate.exists():
                    paths.append(candidate)
                    break
        return paths or [self.paths.resolve(rel)]

    @staticmethod
    def _is_zw_base_file(rel: str) -> bool:
        return "zw base" in Path(rel).stem.casefold()

    @staticmethod
    def _is_zw_ch6_file(rel: str) -> bool:
        stem = Path(rel).stem.casefold()
        return "zw ch6" in stem

    def _needs_sold_to(self, rel: str, merge_right: list[str] | None) -> bool:
        if not merge_right or "SoldTo" not in merge_right:
            return False
        return self._is_zw_base_file(rel) or self._is_zw_ch6_file(rel)

    def _add_sold_to_key(self, df: pd.DataFrame, rel: str) -> pd.DataFrame:
        source_col = (
            "Customer"
            if "Customer" in df.columns
            else "ZwPartner"
            if "ZwPartner" in df.columns
            else None
        )
        if source_col is None:
            raise KeyError(
                f"Для SoldTo в {rel!r} нужна колонка Customer или ZwPartner."
            )
        kunnr_set, ktonr_map = self._zw_partner_lookup()
        out = df.copy()
        out["SoldTo"] = out[source_col].map(
            lambda v, ks=kunnr_set, km=ktonr_map: sold_to_key(
                v, kunnr_set=ks, ktonr_map=km
            )
        )
        return out

    def read(
        self,
        spec: dict[str, Any],
        *,
        merge_right: list[str] | None = None,
        key_excel: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        rel = spec["file"]
        paths = self._all_sorg_paths(rel)
        if len(paths) > 1 and self.ctx.verbose:
            emit(
                self.ctx,
                f"  {rel!r}: объединение ZW из {len(paths)} папок SOrg "
                f"(без фильтра по SOrg.)",
            )
        sheet = spec.get("sheet", 0)
        plain_specs, inline_computed, column_order = ColumnSpecParser.parse(
            spec["columns"]
        )
        if merge_right:
            excel_keys = [k for k in merge_right if k != "SoldTo"]
            if excel_keys:
                plain_specs = ColumnResolver.ensure_merge_keys(
                    plain_specs, excel_keys, key_excel
                )
            if "SoldTo" in merge_right and not any(
                p["name"] in ("Customer", "ZwPartner") for p in plain_specs
            ):
                plain_specs.append(
                    {"name": "Customer", "excel": "Customer", "optional": False}
                )
        out_names, excel_unique = ColumnSpecParser.needed(plain_specs, inline_computed)

        header = pd.read_excel(
            paths[0], sheet_name=sheet, nrows=0, engine=self.ctx.read_engine
        )
        optional_excel = {p["excel"] for p in plain_specs if p.get("optional")}
        rename_for_usecols = ColumnResolver.resolve(
            header,
            excel_unique,
            source_file=rel,
            optional_excel=optional_excel,
        )
        usecols = [
            rename_for_usecols[c]
            for c in excel_unique
            if c in rename_for_usecols
        ]

        text_cols = set(self.ctx.config.get("text_columns") or [])
        leading_zero = self.ctx.config.get("leading_zero_columns") or {}
        dtype = {
            rename_for_usecols[p["excel"]]: str
            for p in plain_specs
            if p["name"] in text_cols and p["excel"] in rename_for_usecols
        }

        frames: list[pd.DataFrame] = []
        for path in paths:
            frames.append(
                self._read_subset(path, sheet, usecols, dtype=dtype or None)
            )
        df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        if len(frames) > 1:
            dedupe_cols = [
                c
                for c in ("KUNNR", "KTONR", "Customer", "SOrg.")
                if c in df.columns
            ]
            if len(dedupe_cols) >= 2:
                df = df.drop_duplicates(subset=dedupe_cols, keep="first")
        for col in list(df.columns):
            if TextNorm.is_id_column(col):
                df[col] = df[col].map(TextNorm.key_value)

        rename_map = {}
        for p in plain_specs:
            if p["name"] == p["excel"]:
                continue
            actual = rename_for_usecols.get(p["excel"], p["excel"])
            rename_map[actual] = p["name"]
        if rename_map:
            df = df.rename(columns=rename_map)

        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].map(
                    lambda v, c=col: TextNorm.format_text_column(
                        v, c, leading_zero
                    )
                )

        for p in plain_specs:
            if p["name"] in df.columns:
                continue
            fallback = p.get("fallback")
            if fallback and fallback in df.columns:
                df[p["name"]] = df[fallback]
                if self.ctx.verbose:
                    emit(
                        self.ctx,
                        f"  {rel!r}: колонка {p['name']!r} нет в файле — "
                        f"взято из {fallback!r}",
                    )
                continue
            if p.get("optional"):
                df[p["name"]] = pd.NA
                if self.ctx.verbose:
                    emit(
                        self.ctx,
                        f"  {rel!r}: колонка {p['name']!r} нет в файле — "
                        f"добавлена пустая (optional)",
                    )

        agg_only = set(spec.get("aggregate") or {}) - {p["name"] for p in plain_specs}
        required = [c for c in out_names if c not in agg_only]
        if merge_right and "SoldTo" in merge_right and self._is_zw_base_file(rel):
            required = [c for c in required if c != "Customer"]
        computed = inline_computed + list(spec.get("computed_columns") or [])
        computed_names = {str(c["name"]) for c in computed}
        missing_out = [
            c for c in required if c not in df.columns and c not in computed_names
        ]
        if missing_out:
            raise KeyError(
                f"После чтения нет колонок {missing_out!r} (файл: {rel}). "
                f"Получено: {list(df.columns)}"
            )
        df = df[[c for c in required if c in df.columns]]

        out = df.copy()
        out = ComputedColumnsApplier.apply(out, computed or None)
        missing_after = [c for c in required if c not in out.columns]
        if missing_after:
            raise KeyError(
                f"После вычисления нет колонок {missing_after!r} (файл: {rel}). "
                f"Получено: {list(out.columns)}"
            )
        if merge_right and "SoldTo" in merge_right and self._needs_sold_to(rel, merge_right):
            out = self._add_sold_to_key(out, rel)
        if merge_right:
            for key in merge_right:
                if key not in out_names and key in out.columns:
                    out_names.append(key)
        keep = [c for c in out_names if c in out.columns]
        if merge_right and "SoldTo" in merge_right:
            for key in merge_right:
                if key in out.columns and key not in keep:
                    keep.append(key)
        if self._is_zw_ch6_file(rel):
            keep = [c for c in keep if c != "Customer"]
        out = out[keep]
        if column_order:
            cols = [c for c in column_order if c in out.columns]
            rest = [c for c in out.columns if c not in cols]
            out = out[cols + rest]
        return out

    def _read_subset(
        self,
        path: Path,
        sheet: Any,
        usecols: list[str] | None,
        *,
        dtype: dict[str, type] | None = None,
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {
            "sheet_name": sheet,
            "engine": self.ctx.read_engine,
        }
        if usecols:
            kwargs["usecols"] = usecols
        if dtype:
            kwargs["dtype"] = dtype
        return pd.read_excel(path, **kwargs)
