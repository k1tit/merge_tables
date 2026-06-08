from __future__ import annotations

from typing import Any

import pandas as pd

from .text_utils import TextNorm


class MergeKeysParser:
    """Разбор merge_on и нормализация ключей в DataFrame."""

    @staticmethod
    def parse_merge_on(merge_on: Any) -> list[str] | None:
        if merge_on is None:
            return None
        if isinstance(merge_on, str):
            key = merge_on.strip()
            return [key] if key else None
        if isinstance(merge_on, list):
            keys = [str(k).strip() for k in merge_on if str(k).strip()]
            return keys or None
        raise ValueError("merge_on должен быть null, строкой или списком колонок.")

    @classmethod
    def parse_source(
        cls,
        spec: dict[str, Any],
        default_merge: Any,
    ) -> tuple[list[str], list[str], bool, dict[str, Any] | None]:
        mo = spec.get("merge_on")
        if mo is None:
            if default_merge is not None:
                raise ValueError(
                    f"Источник {spec.get('file')!r}: глобальный merge_on в корне config "
                    f"больше не используется. Добавьте merge_on в блок этого файла."
                )
            raise ValueError(
                f"Для источника {spec.get('file')!r} задайте merge_on "
                f"(left/right — ключи в Base и в этом файле)."
            )

        if isinstance(mo, dict):
            left = [str(x).strip() for x in mo["left"]]
            right = [str(x).strip() for x in mo.get("right", mo["left"])]
        elif isinstance(mo, str):
            left = right = [mo.strip()]
        elif isinstance(mo, list):
            left = right = [str(x).strip() for x in mo if str(x).strip()]
        else:
            raise ValueError(
                f"merge_on: строка, список или dict left/right — {spec.get('file')!r}"
            )

        if len(left) != len(right):
            raise ValueError(
                f"merge_on left/right разной длины для {spec.get('file')!r}: "
                f"{left!r} vs {right!r}"
            )

        aggregate = spec.get("aggregate")
        dedupe = bool(spec.get("dedupe", spec.get("lookup_dedupe", True)))
        if aggregate:
            dedupe = False

        return left, right, dedupe, aggregate

    @staticmethod
    def normalize_frame(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        out = df.copy()
        for key in keys:
            if key in out.columns:
                out[key] = out[key].map(TextNorm.key_value)
        return out

    @staticmethod
    def overlap_count(
        result: pd.DataFrame,
        part: pd.DataFrame,
        left: list[str],
        right: list[str],
    ) -> int:
        if not len(result):
            return 0
        left_tuples = list(zip(*(result[k] for k in left)))
        right_set = set(zip(*(part[k] for k in right)))
        return sum(1 for t in left_tuples if t in right_set)
