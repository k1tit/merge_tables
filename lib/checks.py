from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from .text_utils import TextNorm

_DASH_PLACEHOLDERS = frozenset({"--", "---"})


class CheckEngine:
    """Проверки качества данных (колонки Check *)."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[pd.DataFrame, dict[str, Any]], pd.Series]] = {
            "match_when_in_either": self._match_when_in_either,
            "compare_match_empty": self._compare_match_empty,
            "ch6_customer_vs_zw_ch6": self._compare_match_empty,
            "ch6_customer_vs_tn_ch6": self._compare_match_empty,
            "ch6_customer_vs_key_ch6": self._compare_match_empty,
        }

    def apply(self, df: pd.DataFrame, specs: list[dict[str, Any]] | None) -> pd.DataFrame:
        if not specs:
            return df

        out = df.copy()
        for spec in specs:
            name = str(spec["name"])
            check_type = str(spec.get("type", "match_when_in_either"))
            handler = self._handlers.get(check_type)
            if handler is None:
                raise ValueError(
                    f"Неизвестный тип проверки {check_type!r}. "
                    f"Доступно: {', '.join(sorted(self._handlers))}"
                )
            out[name] = handler(out, spec)
        return out

    @staticmethod
    def _row_in_scope(df: pd.DataFrame, idx: Any, spec: dict[str, Any]) -> bool:
        apply_when = spec.get("apply_when") or {}
        all_non_empty = [str(c) for c in apply_when.get("all_non_empty") or []]
        for col in all_non_empty:
            if col not in df.columns:
                raise KeyError(
                    f"Проверка {spec.get('name')!r}: для apply_when нет колонки {col!r}. "
                    f"Есть: {list(df.columns)}"
                )
            if not TextNorm.key_value(df.at[idx, col]):
                return False

        column_in = apply_when.get("column_in") or {}
        for col, allowed in column_in.items():
            col_name = str(col)
            if col_name not in df.columns:
                raise KeyError(
                    f"Проверка {spec.get('name')!r}: для column_in нет колонки {col_name!r}. "
                    f"Есть: {list(df.columns)}"
                )
            val = TextNorm.key_value(df.at[idx, col_name]).upper()
            allowed_norm = {
                TextNorm.key_value(str(v)).upper() for v in (allowed or [])
            }
            if val not in allowed_norm:
                return False

        if not all_non_empty and not column_in:
            return True
        return True

    @staticmethod
    def _norm_compare(val: Any) -> str:
        return TextNorm.norm_customer_node(val)

    @staticmethod
    def _empty_result(empty_label: str):
        return empty_label if empty_label else pd.NA

    def _compare_outcome(
        self,
        left_val: Any,
        right_val: Any,
        spec: dict[str, Any],
    ) -> str:
        empty_label = str(spec.get("empty", ""))
        ok_label = str(spec.get("ok", "true"))
        fail_label = str(spec.get("fail", "false"))
        dash_match = bool(spec.get("dash_match", False))
        list_compare = bool(spec.get("list_compare", False))
        sep = str(spec.get("separator", ", "))

        left = self._norm_compare(left_val)
        right_norm = self._norm_compare(right_val)

        if list_compare:
            right_parts = {
                self._norm_compare(v)
                for v in TextNorm.split_aggregated(right_val, separator=sep)
            }
            right_parts.discard("")
            if not left and not right_parts:
                return self._empty_result(empty_label)
            if not left or not right_parts:
                return self._empty_result(empty_label)
            matched = left in right_parts
        else:
            if not left and not right_norm:
                return self._empty_result(empty_label)
            if not left or not right_norm:
                return self._empty_result(empty_label)
            if left == right_norm:
                matched = True
            elif dash_match and left in _DASH_PLACEHOLDERS and right_norm in _DASH_PLACEHOLDERS:
                matched = True
            else:
                matched = False

        return ok_label if matched else fail_label

    def _compare_match_empty(
        self, df: pd.DataFrame, spec: dict[str, Any]
    ) -> pd.Series:
        left_col = str(
            spec.get("left_column")
            or spec.get("ch6_customer_column")
            or spec.get("columns", [None])[0]
            or "CH6"
        )
        right_col = str(
            spec.get("right_column")
            or spec.get("compare_column")
            or spec.get("zw_ch6_column")
            or spec.get("tn_ch6_column")
            or spec.get("columns", [None, None])[1]
            or "ZW_CH6"
        )
        skip_label = spec.get("skip", pd.NA)

        if spec.get("type") == "ch6_customer_vs_key_ch6":
            spec = {**spec, "dash_match": spec.get("dash_match", True)}
        if spec.get("type") == "ch6_customer_vs_tn_ch6" or right_col == "TN_CH6":
            spec = {**spec, "list_compare": spec.get("list_compare", True)}

        for col in (left_col, right_col):
            if col not in df.columns:
                raise KeyError(f"Проверка {spec.get('name')!r}: нет колонки {col!r}.")

        result = pd.Series(skip_label, index=df.index, dtype=object)
        for idx in df.index:
            if not self._row_in_scope(df, idx, spec):
                continue
            result.at[idx] = self._compare_outcome(
                df.at[idx, left_col],
                df.at[idx, right_col],
                spec,
            )
        return result

    def _match_when_in_either(
        self, df: pd.DataFrame, spec: dict[str, Any]
    ) -> pd.Series:
        cols = list(spec["columns"])
        if len(cols) != 2:
            raise ValueError(
                f"Проверка {spec.get('name')!r}: в columns нужно ровно 2 поля."
            )
        left, right = cols[0], cols[1]
        for col in cols:
            if col not in df.columns:
                raise KeyError(f"Проверка {spec.get('name')!r}: нет колонки {col!r}.")

        trigger = {TextNorm.name(v) for v in spec.get("values", [])}
        empty_label = str(spec.get("empty", ""))
        ok_label = str(spec.get("ok", "Ok"))
        fail_label = str(spec.get("fail", "False"))
        ka_guardrail = bool(spec.get("ka_guardrail", False))

        a = df[left].fillna("").astype(str).str.strip().str.casefold()
        b = df[right].fillna("").astype(str).str.strip().str.casefold()
        a_empty = a.eq("")
        b_empty = b.eq("")
        one_empty = a_empty ^ b_empty
        both_empty = a_empty & b_empty

        applies = a.isin(trigger) | b.isin(trigger)
        result = pd.Series(ok_label, index=df.index, dtype=object)
        empty_out = self._empty_result(empty_label)
        result.loc[one_empty | both_empty] = empty_out
        filled = ~a_empty & ~b_empty
        result.loc[applies & filled & (a != b)] = fail_label

        if ka_guardrail:
            non_ka = ~a.isin(trigger) & b.isin(trigger) & ~b_empty
            result.loc[non_ka] = fail_label

        return result
