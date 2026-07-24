from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .at_work_ref import norm_a8_lookup
from .text_utils import TextNorm


class ComputedColumnsApplier:
    """Вычисляемые колонки: concat, key, customer_key."""

    _FORMULA_SPLIT = re.compile(r"\s*&\s*")

    @classmethod
    def apply(
        cls,
        df: pd.DataFrame,
        specs: list[dict[str, Any]] | None,
        *,
        a8_ref_values: frozenset[str] | None = None,
        trade_names_in_ref: frozenset[str] | None = None,
    ) -> pd.DataFrame:
        if not specs:
            return df

        out = df.copy()
        for spec in specs:
            name = str(spec["name"])
            col_type = str(spec.get("type", "concat")).strip().lower()

            if col_type == "key":
                if spec.get("key_rules"):
                    keys, rules = cls._key_priority_series(
                        out,
                        spec,
                        a8_ref_values=a8_ref_values,
                        trade_names_in_ref=trade_names_in_ref,
                    )
                    out[name] = keys
                    rule_col = str(spec.get("rule_column") or "Key_Rule").strip()
                    if rule_col:
                        out[rule_col] = rules
                else:
                    out[name] = cls._key_series(
                        out, spec, a8_ref_values=a8_ref_values
                    )
                continue
            if col_type == "customer_key":
                out[name] = cls._customer_key_series(out, spec, a8_ref_values=a8_ref_values)
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
    def _a8_column(cls, spec: dict[str, Any]) -> str:
        aw = spec.get("at_work_education") or {}
        return str(aw.get("a8_column", "A8"))

    @classmethod
    def _a8_in_reference(
        cls,
        row: pd.Series,
        spec: dict[str, Any],
        a8_ref_values: frozenset[str] | None,
    ) -> bool:
        if not a8_ref_values:
            return False
        col = cls._a8_column(spec)
        if col not in row.index:
            return False
        a8 = norm_a8_lookup(row[col])
        return bool(a8) and a8 in a8_ref_values

    @classmethod
    def _key_mode(
        cls,
        row: pd.Series,
        spec: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None = None,
    ) -> str:
        """
        standard | at_work | invalid

        - at_work (с A8): CH6_CGrp=P, CGrp∈{P,Q}, A8 в справочнике At Work&Education
        - standard: CH6_CGrp≠P, или CGrp∉{P,Q} при CH6_CGrp=P (обычный Key без A8)
        """
        if not cls._is_at_work_edu(row, spec):
            return "standard"
        if not cls._is_business_pq(row, spec):
            return "standard"
        if cls._a8_in_reference(row, spec, a8_ref_values):
            return "at_work"
        return "standard"

    @classmethod
    def _omit_parts_for_row(
        cls,
        row: pd.Series,
        parts: list[str],
        spec: dict[str, Any],
    ) -> list[str]:
        rules = spec.get("omit_parts_when") or []
        if isinstance(rules, dict):
            rules = [rules]
        result = list(parts)
        for rule in rules:
            col = str(rule.get("column", "Grp4"))
            vals = cls._norm_upper_set(rule.get("values"), [])
            omit = {str(p) for p in (rule.get("parts") or [])}
            if col not in row.index or not vals or not omit:
                continue
            if TextNorm.key_value(row[col]).upper() in vals:
                result = [p for p in result if p not in omit]
        return result

    @classmethod
    def _include_parts_for_row(
        cls,
        row: pd.Series,
        parts: list[str],
        spec: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None = None,
    ) -> list[str]:
        rules = spec.get("include_parts_when") or []
        if isinstance(rules, dict):
            rules = [rules]
        result = list(parts)
        for rule in rules:
            col = str(rule.get("column", "Grp4"))
            vals = cls._norm_upper_set(rule.get("values"), [])
            to_add = [str(p) for p in (rule.get("parts") or []) if str(p).strip()]
            after = str(rule.get("insert_after", "")).strip()
            require_ref = bool(rule.get("require_a8_in_reference", False))
            if col not in row.index or not vals or not to_add:
                continue
            if TextNorm.key_value(row[col]).upper() not in vals:
                continue
            for part in to_add:
                if part in result:
                    continue
                if require_ref and part == cls._a8_column(spec):
                    if not cls._a8_in_reference(row, spec, a8_ref_values):
                        continue
                if after and after in result:
                    result.insert(result.index(after) + 1, part)
                else:
                    result.append(part)
        return result

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
    def _row_cell(cls, row: pd.Series, column: str) -> str:
        if column not in row.index:
            return ""
        return TextNorm.key_value(row[column])

    @classmethod
    def _norm_rule_values(cls, values: Any) -> set[str]:
        out: set[str] = set()
        for raw in values or []:
            text = TextNorm.key_value(raw).upper()
            if text:
                out.add(text)
        return out

    @classmethod
    def _norm_a8_rule_values(cls, values: Any) -> set[str]:
        out: set[str] = set()
        for raw in values or []:
            norm = norm_a8_lookup(raw)
            if norm:
                out.add(norm)
        return out

    @classmethod
    def _match_key_condition(
        cls,
        row: pd.Series,
        cond: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None,
        trade_names_in_ref: frozenset[str] | None = None,
    ) -> bool:
        col = str(cond.get("column", "")).strip()
        val = cls._row_cell(row, col) if col else ""
        val_upper = val.upper()

        if cond.get("empty_or_not_in_reference"):
            if not col:
                return False
            if not val:
                return True
            if trade_names_in_ref is None:
                return False
            return TextNorm.trade_name_key(val) not in trade_names_in_ref

        if cond.get("empty"):
            return not val
        if cond.get("not_empty"):
            return bool(val)

        if "equals" in cond:
            expected = TextNorm.key_value(cond["equals"]).upper()
            if val_upper != expected:
                return False

        if "in" in cond:
            allowed = cls._norm_rule_values(cond["in"])
            if val_upper not in allowed:
                return False

        if "not_in" in cond:
            blocked = cls._norm_rule_values(cond["not_in"])
            if val_upper in blocked:
                return False

        if cond.get("a8_in_reference"):
            a8_col = col or cls._a8_column({"at_work_education": cond.get("at_work_education") or {}})
            if a8_col not in row.index:
                return False
            a8 = norm_a8_lookup(row[a8_col])
            if not a8 or not a8_ref_values or a8 not in a8_ref_values:
                return False

        if "a8_in" in cond:
            a8_col = col or "A8"
            if a8_col not in row.index:
                return False
            a8 = norm_a8_lookup(row[a8_col])
            allowed = cls._norm_a8_rule_values(cond["a8_in"])
            if not a8 or a8 not in allowed:
                return False

        return True

    @classmethod
    def _match_key_rule(
        cls,
        row: pd.Series,
        rule: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None,
        trade_names_in_ref: frozenset[str] | None = None,
    ) -> bool:
        if rule.get("default"):
            return True
        when = rule.get("when") or {}
        for cond in when.get("all") or []:
            if not cls._match_key_condition(
                row,
                cond,
                a8_ref_values=a8_ref_values,
                trade_names_in_ref=trade_names_in_ref,
            ):
                return False
        for cond in when.get("any") or []:
            if cls._match_key_condition(
                row,
                cond,
                a8_ref_values=a8_ref_values,
                trade_names_in_ref=trade_names_in_ref,
            ):
                return True
        if when.get("any"):
            return False
        return bool(when.get("all") or rule.get("default"))

    @classmethod
    def _key_from_rule_formula(
        cls,
        row: pd.Series,
        rule: dict[str, Any],
        *,
        sep: str,
    ) -> str:
        formula = str(rule.get("formula") or "").strip()
        if not formula:
            return cls._invalid_key_value(rule) if "invalid_key" in rule else ""
        parts = cls._parse_column_formula(formula)
        return cls._glue_parts(row, parts, sep)

    @classmethod
    def _rule_label(cls, rule: dict[str, Any]) -> str:
        return str(rule.get("name") or rule.get("rule") or "").strip()

    @classmethod
    def _key_priority_series(
        cls,
        df: pd.DataFrame,
        spec: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None = None,
        trade_names_in_ref: frozenset[str] | None = None,
    ) -> tuple[pd.Series, pd.Series]:
        rules = list(spec.get("key_rules") or [])
        if not rules:
            raise ValueError("Key: задайте key_rules (приоритет 1..N) или старые formula/at_work_formula.")

        sep = str(spec.get("separator", ""))
        needed: set[str] = set()
        for rule in rules:
            formula = str(rule.get("formula") or "").strip()
            if formula:
                needed.update(cls._parse_column_formula(formula))
            for block in (rule.get("when") or {}).values():
                if not isinstance(block, list):
                    continue
                for cond in block:
                    col = str(cond.get("column", "")).strip()
                    if col:
                        needed.add(col)
        missing = [c for c in sorted(needed) if c not in df.columns]
        if missing:
            raise KeyError(f"Key: не найдены поля {missing!r}. Есть: {list(df.columns)}")

        invalid_val = cls._invalid_key_value(spec)
        keys: list[str] = []
        rule_names: list[str] = []
        for idx in df.index:
            row = df.loc[idx]
            matched = False
            for rule in rules:
                if not cls._match_key_rule(
                    row,
                    rule,
                    a8_ref_values=a8_ref_values,
                    trade_names_in_ref=trade_names_in_ref,
                ):
                    continue
                formula = str(rule.get("formula") or "").strip()
                if formula:
                    keys.append(cls._key_from_rule_formula(row, rule, sep=sep))
                else:
                    keys.append(invalid_val)
                rule_names.append(cls._rule_label(rule))
                matched = True
                break
            if not matched:
                keys.append(invalid_val)
                rule_names.append("")
        index = df.index
        return (
            pd.Series(keys, index=index, dtype=object),
            pd.Series(rule_names, index=index, dtype=object),
        )

    @classmethod
    def _key_series(
        cls,
        df: pd.DataFrame,
        spec: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None = None,
    ) -> pd.Series:
        """Key по key_rules (приоритет 1..N) или legacy formula/at_work."""
        if spec.get("key_rules"):
            keys, _rules = cls._key_priority_series(df, spec, a8_ref_values=a8_ref_values)
            return keys

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
            mode = cls._key_mode(row, spec, a8_ref_values=a8_ref_values)
            if mode == "invalid":
                result.append(invalid_val)
                continue
            parts = at_work if mode == "at_work" else standard
            parts = cls._omit_parts_for_row(row, parts, spec)
            parts = cls._include_parts_for_row(
                row, parts, spec, a8_ref_values=a8_ref_values
            )
            result.append(cls._glue_parts(row, parts, sep, skip_empty=skip_empty))
        return pd.Series(result, index=df.index, dtype=object)

    @classmethod
    def _customer_key_series(
        cls,
        df: pd.DataFrame,
        spec: dict[str, Any],
        *,
        a8_ref_values: frozenset[str] | None = None,
    ) -> pd.Series:
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
            mode = cls._key_mode(row, spec, a8_ref_values=a8_ref_values)
            if mode == "invalid":
                result.append("")
                continue
            parts = at_work if mode == "at_work" else standard
            parts = cls._omit_parts_for_row(row, parts, spec)
            parts = cls._include_parts_for_row(
                row, parts, spec, a8_ref_values=a8_ref_values
            )
            body = "".join(TextNorm.compact_key_part(row[p]) for p in parts)
            result.append(f"{body}{suffix}" if body else "")
        return pd.Series(result, index=df.index, dtype=object)
