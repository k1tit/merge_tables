from __future__ import annotations

from typing import Any

import pandas as pd

from .aggregate import DataAggregator
from .column_resolver import ColumnSpecParser
from .context import BuildContext
from .log_sink import emit
from .merge_keys import MergeKeysParser
from .sources import ExcelSourceReader
from .text_utils import TextNorm


class DataMerger:
    """Последовательное объединение источников в одну таблицу."""

    def __init__(self, ctx: BuildContext) -> None:
        self.ctx = ctx
        self.reader = ExcelSourceReader(ctx)
        self.keys = MergeKeysParser()

    def merge_all(
        self,
        frames: list[pd.DataFrame],
        source_specs: list[dict[str, Any]],
    ) -> pd.DataFrame:
        if not frames:
            raise ValueError("Нет данных для merge.")
        result = frames[0]
        for spec, part in zip(source_specs[1:], frames[1:], strict=True):
            result = self._merge_source_into(result, spec, part, label="merge")
        return self._finalize_zw_rows(result)

    def merge_post(
        self,
        result: pd.DataFrame,
        post_specs: list[dict[str, Any]],
    ) -> pd.DataFrame:
        out = result
        for spec in post_specs:
            out = self._merge_source_into(out, spec, None, label="post-merge")
        return out

    def _merge_source_into(
        self,
        result: pd.DataFrame,
        spec: dict[str, Any],
        part: pd.DataFrame | None,
        *,
        label: str,
    ) -> pd.DataFrame:
        left, right, dedupe, aggregate = self.keys.parse_source(
            spec, self.ctx.default_merge
        )
        if spec.get("dedupe") is None and spec.get("lookup_dedupe") is None:
            dedupe = self.ctx.lookup_dedupe and not aggregate

        before = set(result.columns)
        if part is None:
            part = self.reader.read(
                spec,
                merge_right=right,
                key_excel=spec.get("key_excel"),
            )
        else:
            part = self._enrich_part(part, spec)

        part, filter_note = self._apply_reference_filter(part, spec)
        if filter_note and self.ctx.verbose:
            emit(self.ctx, filter_note)

        overlap = self.keys.overlap_count(
            self.keys.normalize_frame(result.copy(), left),
            self.keys.normalize_frame(part.copy(), right),
            left,
            right,
        )

        overwrite = spec.get("overwrite_columns")
        if overwrite is not None and not isinstance(overwrite, list):
            overwrite = [overwrite]

        expected = ColumnSpecParser.output_names(spec)

        result = self._merge_one(
            result,
            part,
            left,
            right,
            dedupe=dedupe,
            aggregate=aggregate,
            overwrite_columns=overwrite,
            preserve_columns=expected,
        )

        added = [c for c in expected if c not in before]
        missing = [c for c in expected if c not in result.columns]
        if missing:
            for col in missing:
                result[col] = pd.NA

        require_keys = spec.get("merge_require_non_empty")
        if require_keys:
            if isinstance(require_keys, str):
                require_keys = [require_keys]
            result = self._clear_when_keys_empty(result, list(require_keys), added)

        if self.ctx.verbose:
            msg = f"  {label} {spec.get('file')!r}: +{added}"
            if missing:
                msg += " (колонка создана, но merge не добавил — проверьте ключи)"
            msg += f", ключ совпал у {overlap} строк"
            emit(self.ctx, msg)
            if (
                overlap == 0
                and label == "merge"
                and set(left) == {"SOrg.", "Trade Name"}
            ):
                emit(
                    self.ctx,
                    "    ВНИМАНИЕ: TN merge — 0 совпадений по SOrg.+Trade Name. "
                    "Проверьте references/Справочник_CH6.xlsx (колонки SO, TRADE NAME #).",
                )
            if overlap == 0 and label == "post-merge" and "Key" in left:
                emit(
                    self.ctx,
                    "    Подсказка: Key отчёта должен совпадать с колонкой Key/Ключ "
                    "в справочнике (Grp4+CGrp+A7+ZW_A7+Indus.)",
                )
            for col in added:
                if col in result.columns:
                    filled = TextNorm.filled_count(result[col])
                    emit(self.ctx, f"    {col}: заполнено {filled} из {len(result)}")
                    if filled == 0 and label == "merge":
                        if col in ("TN_CH6", "TN_CH6_Name", "TN_CGrp"):
                            emit(
                                self.ctx,
                                f"    ВНИМАНИЕ: {col!r} пустая — в Справочник_CH6 "
                                f"нет пары SO+TRADE NAME # для SOrg.+Trade Name",
                            )
                        else:
                            emit(
                                self.ctx,
                                f"    ВНИМАНИЕ: {col!r} пустая — "
                                f"проверьте Customer/KUNNR в файле и в config merge_on",
                            )
        return result

    def _apply_reference_filter(
        self, part: pd.DataFrame, spec: dict[str, Any]
    ) -> tuple[pd.DataFrame, str | None]:
        filt = spec.get("reference_filter")
        if not filt:
            return part, None

        filtered = part
        applied: list[str] = []
        for col, raw_val in filt.items():
            col_name = str(col).strip()
            if col_name not in filtered.columns:
                continue
            val = str(raw_val).replace("{sorg}", self.ctx.sorg)
            series = filtered[col_name].map(TextNorm.key_value)
            filtered = filtered.loc[series == TextNorm.key_value(val)]
            applied.append(f"{col_name}={val}")

        if not applied:
            return part, None

        if not filtered.empty:
            return filtered, (
                f"  фильтр справочника {spec.get('file')!r}: "
                f"{', '.join(applied)}, строк {len(filtered)}"
            )

        fallback = str(spec.get("reference_filter_fallback", "")).strip()
        if fallback == "trade_name_only":
            return part, (
                f"  ВНИМАНИЕ: в справочнике {spec.get('file')!r} нет "
                f"{', '.join(applied)} — join TN только по Trade Name"
            )

        return filtered, (
            f"  ВНИМАНИЕ: в справочнике {spec.get('file')!r} нет строк для "
            f"{', '.join(applied)}"
        )

    def _enrich_part(
        self, part: pd.DataFrame, spec: dict[str, Any]
    ) -> pd.DataFrame:
        out = part
        for ef in spec.get("enrich_from") or []:
            ef_left, ef_right, ef_dedupe, ef_agg = self.keys.parse_source(ef, None)
            if ef.get("dedupe") is None and ef.get("lookup_dedupe") is None:
                ef_dedupe = self.ctx.lookup_dedupe and not ef_agg

            sub = self.reader.read(
                ef,
                merge_right=ef_right,
                key_excel=ef.get("key_excel"),
            )
            for key in ef_left:
                if key not in out.columns:
                    raise KeyError(
                        f"enrich_from {ef.get('file')!r}: в part нет ключа {key!r}."
                    )
            for key in ef_right:
                if key not in sub.columns:
                    raise KeyError(
                        f"enrich_from {ef.get('file')!r}: в файле нет ключа {key!r}."
                    )

            out = self.keys.normalize_frame(out, ef_left)
            sub = self.keys.normalize_frame(sub, ef_right)
            if ef_agg:
                sub = DataAggregator.apply(sub, ef_agg, ef_right)
            elif ef_dedupe:
                sub = sub.drop_duplicates(subset=ef_right, keep="first")

            add_cols = [
                c
                for c in ColumnSpecParser.output_names(ef)
                if c in sub.columns and c not in ef_right
            ]
            keep = list(dict.fromkeys(list(ef_right) + add_cols))
            sub = sub[[c for c in keep if c in sub.columns]]
            drop = [c for c in sub.columns if c in out.columns and c not in ef_right]
            sub = sub.drop(columns=drop, errors="ignore")

            before_cols = set(out.columns)
            out = out.merge(sub, left_on=ef_left, right_on=ef_right, how="left")
            drop_after = [c for c in ef_right if c not in ef_left]
            out = out.drop(columns=drop_after, errors="ignore")
            added = [c for c in add_cols if c in out.columns and c not in before_cols]
            if self.ctx.verbose:
                emit(
                    self.ctx,
                    f"  enrich {ef.get('file')!r} -> {spec.get('file')!r}: +{added}",
                )
        return out

    @staticmethod
    def _filled(series: pd.Series) -> pd.Series:
        return series.fillna("").astype(str).str.strip().ne("")

    def _finalize_zw_rows(self, result: pd.DataFrame) -> pd.DataFrame:
        """ZW по Customer (без SOrg.): заполнить пустые ячейки из других строк того же клиента."""
        out = result.copy()
        if "ZwPartner" in out.columns:
            if "ZW" in out.columns:
                need = self._filled(out["ZW_SO"]) & ~self._filled(out["ZW"])
                if need.any():
                    out.loc[need, "ZW"] = out.loc[need, "ZwPartner"]
            out = out.drop(columns=["ZwPartner"], errors="ignore")

        if "Customer" not in out.columns:
            return out

        zw_cols = [
            c
            for c in (
                "ZW",
                "ZW_SO",
                "ZW_A7",
                "ZW_CGrp",
                "ZW_CH6",
                "ZW_CH6_Name",
            )
            if c in out.columns
        ]
        for col in zw_cols:
            out[col] = self._fill_customer_column(out, col)

        if not {"ZW", "ZW_SO"}.issubset(out.columns):
            return out

        row_has = self._filled(out["ZW"]) | self._filled(out["ZW_SO"])
        customer_has = out.assign(_zw=row_has).groupby("Customer", dropna=False)[
            "_zw"
        ].transform("any")
        orphan = customer_has & ~self._filled(out["ZW"]) & ~self._filled(out["ZW_SO"])
        if orphan.any() and self.ctx.verbose:
            emit(
                self.ctx,
                f"  удалено {int(orphan.sum())} строк-дубликатов без ZW/ZW_SO "
                f"(у Customer уже есть данные ZW)",
            )
        return out.loc[~orphan].copy()

    def _fill_customer_column(self, df: pd.DataFrame, col: str) -> pd.Series:
        series = df[col].copy()
        filled = self._filled(series)
        if not filled.any():
            return series
        refs = (
            df.loc[filled, ["Customer", col]]
            .drop_duplicates("Customer", keep="first")
            .set_index("Customer")[col]
        )
        has = df["Customer"].map(filled.groupby(df["Customer"], dropna=False).any())
        fill_mask = ~filled & has.fillna(False)
        if fill_mask.any():
            series.loc[fill_mask] = df.loc[fill_mask, "Customer"].map(refs)
        return series

    @staticmethod
    def _rename_colliding_right_keys(
        result: pd.DataFrame,
        part: pd.DataFrame,
        left: list[str],
        right: list[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        """Ключи справа с тем же именем, что колонки Base (Customer, SOrg.), — во временные."""
        rename_map: dict[str, str] = {}
        new_right: list[str] = []
        for key in right:
            if key in result.columns and key not in left:
                alias = f"__merge_key__{key}"
                rename_map[key] = alias
                new_right.append(alias)
            else:
                new_right.append(key)
        if rename_map:
            part = part.rename(columns=rename_map)
        return part, new_right

    @staticmethod
    def _merge_one(
        result: pd.DataFrame,
        part: pd.DataFrame,
        left: list[str],
        right: list[str],
        *,
        dedupe: bool,
        aggregate: dict[str, Any] | None,
        overwrite_columns: list[str] | None = None,
        preserve_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        for key in left:
            if key not in result.columns:
                raise KeyError(
                    f"В таблице нет ключа merge {key!r}. Есть: {list(result.columns)}"
                )
        for key in right:
            if key not in part.columns:
                raise KeyError(
                    f"В источнике нет ключа merge {key!r}. Есть: {list(part.columns)}"
                )

        result = MergeKeysParser.normalize_frame(result, left)
        part, right = DataMerger._rename_colliding_right_keys(result, part, left, right)
        part = MergeKeysParser.normalize_frame(part, right)

        if aggregate:
            part = DataAggregator.apply(part, aggregate, right)
        elif dedupe:
            part = part.drop_duplicates(subset=right, keep="first")

        for key in right:
            if key in part.columns:
                part = part[
                    part[key].fillna("").astype(str).str.strip().ne("")
                ]

        overwrite = {str(c).strip() for c in (overwrite_columns or []) if str(c).strip()}
        drop_from_part = [
            c
            for c in part.columns
            if c in result.columns and c not in right and c not in overwrite
        ]
        part = part.drop(columns=drop_from_part, errors="ignore")

        merged = result.merge(
            part, left_on=left, right_on=right, how="left", suffixes=("_was", "")
        )
        for col in overwrite:
            was = f"{col}_was"
            if was not in merged.columns:
                continue
            if col in merged.columns:
                new_vals = merged[col]
                old_vals = merged[was]
                use_new = new_vals.notna() & (new_vals.astype(str).str.strip() != "")
                merged[col] = new_vals.where(use_new, old_vals)
                merged = merged.drop(columns=[was], errors="ignore")
            else:
                merged = merged.rename(columns={was: col})
        keep = set(preserve_columns or [])
        drop_after = [c for c in right if c not in left and c not in keep]
        return merged.drop(columns=drop_after, errors="ignore")

    @staticmethod
    def _clear_when_keys_empty(
        df: pd.DataFrame,
        keys: list[str],
        columns: list[str],
    ) -> pd.DataFrame:
        if not keys or not columns:
            return df
        out = df.copy()
        empty = pd.Series(False, index=out.index)
        for key in keys:
            if key not in out.columns:
                continue
            empty = empty | out[key].fillna("").astype(str).str.strip().eq("")
        for col in columns:
            if col in out.columns:
                out.loc[empty, col] = pd.NA
        return out
