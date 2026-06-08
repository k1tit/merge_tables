from __future__ import annotations

from typing import Any

import pandas as pd

from .text_utils import TextNorm


class ComputedColumnsApplier:
    """Вычисляемые колонки: concat, key, customer_key."""

    @classmethod
    def apply(cls, df: pd.DataFrame, specs: list[dict[str, Any]] | None) -> pd.DataFrame:
        if not specs:
            return df

        out = df.copy()
        for spec in specs:
            name = str(spec["name"])
            col_type = str(spec.get("type", "concat")).strip().lower()

            if col_type == "key":
                out[name] = cls._key_series(out, spec)
                continue
            if col_type == "customer_key":
                out[name] = cls._customer_key_series(out, spec)
                continue

            parts: list[str] = list(spec["from"])
            sep = spec.get("separator", "")
            missing = [c for c in parts if c not in out.columns]
            if missing:
                raise KeyError(
                    f"Для колонки {name!r} не найдены поля {missing!r}. "
                    f"Есть: {list(out.columns)}"
                )
            combined = out[parts[0]].fillna("").astype(str)
            for col in parts[1:]:
                combined = combined + sep + out[col].fillna("").astype(str)
            out[name] = combined

        return out

    @staticmethod
    def _is_at_work(row: pd.Series, spec: dict[str, Any]) -> bool:
        aw = spec.get("at_work_education") or {}
        grp4_col = str(aw.get("grp4_column", "Grp4"))
        grp4_vals = {
            TextNorm.key_value(v).upper() for v in (aw.get("grp4_values") or ["AWM"])
        }
        if grp4_col not in row.index:
            return False
        return TextNorm.key_value(row[grp4_col]).upper() in grp4_vals

    @classmethod
    def _key_series(cls, df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        sep = str(spec.get("separator", ""))
        standard = list(
            spec.get("standard_parts") or ["Grp4", "CGrp", "A7", "ZW_A7", "Indus."]
        )
        at_work = list(
            spec.get("at_work_parts") or ["Grp4", "CGrp", "A7", "A8", "ZW_A7", "Indus."]
        )
        for parts in (standard, at_work):
            missing = [p for p in parts if p not in df.columns]
            if missing:
                raise KeyError(f"Key: не найдены поля {missing!r}. Есть: {list(df.columns)}")

        result: list[str] = []
        for idx in df.index:
            row = df.loc[idx]
            use = at_work if cls._is_at_work(row, spec) else standard
            values = [TextNorm.key_value(row[p]) for p in use]
            if spec.get("skip_empty", True):
                values = [v for v in values if v]
            result.append(sep.join(values))
        return pd.Series(result, index=df.index, dtype=object)

    @classmethod
    def _customer_key_series(cls, df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        suffix = str(spec.get("suffix", "380N"))
        standard = list(spec.get("standard_parts") or ["Grp4", "CGrp", "A7"])
        at_work = list(spec.get("at_work_parts") or ["Grp4", "CGrp", "A7", "A8"])
        for parts in (standard, at_work):
            missing = [p for p in parts if p not in df.columns]
            if missing:
                raise KeyError(
                    f"Customer Key: не найдены поля {missing!r}. Есть: {list(df.columns)}"
                )

        result: list[str] = []
        for idx in df.index:
            row = df.loc[idx]
            parts = at_work if cls._is_at_work(row, spec) else standard
            body = "".join(TextNorm.compact_key_part(row[p]) for p in parts)
            result.append(f"{body}{suffix}" if body else "")
        return pd.Series(result, index=df.index, dtype=object)
