from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .text_utils import TextNorm


class ComputedColumnsApplier:
    """Вычисляемые колонки: concat, key, customer_key."""

    _FORMULA_SPLIT = re.compile(r"\s*&\s*")

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

    @classmethod
    def _parse_column_formula(cls, formula: str) -> list[str]:
        """«Grp4 & CGrp & A7» → список имён колонок (как в макете Excel)."""
        parts = [p.strip() for p in cls._FORMULA_SPLIT.split(str(formula).strip()) if p.strip()]
        if not parts:
            raise ValueError(f"Пустая формула склейки: {formula!r}")
        return parts

    @classmethod
    def _resolve_key_parts(cls, spec: dict[str, Any], *, at_work: bool) -> list[str]:
        if at_work:
            formula = spec.get("at_work_formula")
            fallback = spec.get("at_work_parts") or [
                "Grp4",
                "CGrp",
                "A7",
                "A8",
                "ZW_A7",
                "Indus.",
            ]
        else:
            formula = spec.get("formula")
            fallback = spec.get("standard_parts") or [
                "Grp4",
                "CGrp",
                "A7",
                "ZW_A7",
                "Indus.",
            ]
        if formula:
            return cls._parse_column_formula(str(formula))
        return list(fallback)

    @classmethod
    def _norm_upper_set(cls, values: Any, default: list[str]) -> set[str]:
        raw = values if values is not None else default
        return {TextNorm.key_value(v).upper() for v in raw}

    @classmethod
    def _is_business_pq(cls, row: pd.Series, spec: dict[str, Any]) -> bool:
        bt = spec.get("business_type") or {}
        col = str(bt.get("column", "CGrp"))
        if col not in row.index:
            return False
        pq_vals = cls._norm_upper_set(bt.get("values"), ["P", "Q"])
        return TextNorm.key_value(row[col]).upper() in pq_vals

    @classmethod
    def _is_at_work_edu(cls, row: pd.Series, spec: dict[str, Any]) -> bool:
        """Признак «повод At work или Education» (CH6_CGrp=P)."""
        aw = spec.get("at_work_education") or {}
        reason_col = str(aw.get("reason_column", "CH6_CGrp"))
        if reason_col not in row.index:
            return False
        reason_vals = cls._norm_upper_set(aw.get("reason_values"), ["P"])
        reason = TextNorm.key_value(row[reason_col]).upper()
        return bool(reason) and reason in reason_vals

    @classmethod
    def _is_at_work_reason(cls, row: pd.Series, spec: dict[str, Any]) -> bool:
        return cls._is_at_work_edu(row, spec)

    @classmethod
    def _key_mode(cls, row: pd.Series, spec: dict[str, Any]) -> str:
        """
        standard | at_work | invalid

        - at_work (с A8): is_at_work_edu и business_type ∈ {P, Q}
        - invalid: is_at_work_edu, но business_type ∉ {P, Q}
        - standard: всё остальное (без A8), в т.ч. P/Q без повода At w/Ed
        """
        if not cls._is_at_work_edu(row, spec):
            return "standard"
        if cls._is_business_pq(row, spec):
            return "at_work"
        return "invalid"

    @classmethod
    def _invalid_key_value(cls, spec: dict[str, Any]) -> str:
        return str(spec.get("invalid_key", ""))

    @classmethod
    def _glue_parts(
        cls,
        row: pd.Series,
        parts: list[str],
        sep: str,
        *,
        skip_empty: bool = False,
    ) -> str:
        """Склеить значения колонок: sep='' → Grp4+CGrp+A7+… как в pandas astype(str)+."""
        values = [cls._key_part(row[p]) for p in parts]
        if skip_empty:
            values = [v for v in values if v]
        if not sep:
            return "".join(values)
        return sep.join(values)

    @staticmethod
    def _key_part(val: Any) -> str:
        return TextNorm.key_part(val)

    @classmethod
    def _key_series(cls, df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        """Key = Grp4+CGrp+A7(+A8)+ZW_A7+Indus. (CONCAT без разделителя)."""
        sep = str(spec.get("separator", ""))
        standard = cls._resolve_key_parts(spec, at_work=False)
        at_work = cls._resolve_key_parts(spec, at_work=True)
        for parts in (standard, at_work):
            missing = [p for p in parts if p not in df.columns]
            if missing:
                raise KeyError(f"Key: не найдены поля {missing!r}. Есть: {list(df.columns)}")

        invalid_val = cls._invalid_key_value(spec)
        skip_empty = bool(spec.get("skip_empty", False))
        result: list[str] = []
        for idx in df.index:
            row = df.loc[idx]
            mode = cls._key_mode(row, spec)
            if mode == "invalid":
                result.append(invalid_val)
                continue
            parts = at_work if mode == "at_work" else standard
            result.append(cls._glue_parts(row, parts, sep, skip_empty=skip_empty))
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
            mode = cls._key_mode(row, spec)
            if mode == "invalid":
                result.append("")
                continue
            parts = at_work if mode == "at_work" else standard
            body = "".join(TextNorm.compact_key_part(row[p]) for p in parts)
            result.append(f"{body}{suffix}" if body else "")
        return pd.Series(result, index=df.index, dtype=object)
