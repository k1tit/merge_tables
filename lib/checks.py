from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from .text_utils import TextNorm


class CheckEngine:
    """Проверки качества данных (колонки Check *)."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[pd.DataFrame, dict[str, Any]], pd.Series]] = {
            "match_when_in_either": self._match_when_in_either,
            "ch6_customer_vs_zw_ch6": self._ch6_customer_vs_compare,
            "ch6_customer_vs_tn_ch6": self._ch6_customer_vs_compare,
            "ch6_customer_vs_key_ch6": self._ch6_customer_vs_compare,
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
                    f"Доступно: {', '.join(self._handlers)}"
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

        return bool(all_non_empty or column_in)

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
        ok_label = str(spec.get("ok", "true"))
        fail_label = str(spec.get("fail", "false"))

        a = df[left].fillna("").astype(str).str.strip().str.casefold()
        b = df[right].fillna("").astype(str).str.strip().str.casefold()
        applies = a.isin(trigger) | b.isin(trigger)
        result = pd.Series(ok_label, index=df.index, dtype=object)
        result.loc[applies & (a != b)] = fail_label
        return result

    def _ch6_customer_vs_compare(
        self, df: pd.DataFrame, spec: dict[str, Any]
    ) -> pd.Series:
        ch6_col = str(spec.get("ch6_customer_column", "CH6"))
        compare_col = str(
            spec.get("compare_column")
            or spec.get("zw_ch6_column")
            or spec.get("tn_ch6_column")
            or "ZW_CH6"
        )
        sep = str(spec.get("separator", ", "))
        ok_label = str(spec.get("ok", "true"))
        fail_label = str(spec.get("fail", "false"))
        skip_label = str(spec.get("skip", ok_label))

        for col in (ch6_col, compare_col):
            if col not in df.columns:
                raise KeyError(f"Проверка {spec.get('name')!r}: нет колонки {col!r}.")

        result = pd.Series(skip_label, index=df.index, dtype=object)
        for idx in df.index:
            if not self._row_in_scope(df, idx, spec):
                continue
            ch6_val = df.at[idx, ch6_col]
            compare_val = df.at[idx, compare_col]
            result.at[idx] = (
                ok_label
                if TextNorm.customer_node_in_list(ch6_val, compare_val, separator=sep)
                else fail_label
            )
        return result
