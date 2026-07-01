from __future__ import annotations

from typing import Any

import pandas as pd

from .text_utils import TextNorm


class DataAggregator:
    """Несколько строк на один ключ → склейка значений через separator."""

    @staticmethod
    def apply(
        df: pd.DataFrame,
        agg_spec: dict[str, Any],
        group_keys: list[str],
    ) -> pd.DataFrame:
        pieces: list[pd.DataFrame] = []
        for out_name, rule in agg_spec.items():
            if isinstance(rule, str):
                rule = {"source": rule}
            src = str(rule.get("source") or rule.get("column") or out_name)
            sep = str(rule.get("separator", ", "))
            unique = bool(rule.get("unique", True))

            if src not in df.columns:
                if out_name in df.columns:
                    src = out_name
                else:
                    raise KeyError(
                        f"aggregate {out_name!r}: нет колонки {src!r}. "
                        f"Есть: {list(df.columns)}"
                    )

            def _join_vals(series: pd.Series, _sep=sep, _unique=unique) -> str:
                vals: list[str] = []
                seen: set[str] = set()
                for raw in series:
                    v = TextNorm.key_part(raw)
                    if not v:
                        continue
                    if _unique:
                        if v in seen:
                            continue
                        seen.add(v)
                    vals.append(v)
                return _sep.join(vals)

            grouped = (
                df.groupby(group_keys, dropna=False)[src]
                .apply(_join_vals)
                .rename(out_name)
                .reset_index()
            )
            pieces.append(grouped)

        out = pieces[0]
        for extra in pieces[1:]:
            out = out.merge(extra, on=group_keys, how="outer")
        return out
