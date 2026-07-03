from __future__ import annotations

from typing import Any

import pandas as pd

from .text_utils import TextNorm


class ColumnSpecParser:
    """Разбор блока columns в config источника."""

    @staticmethod
    def parse(
        columns: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        plain_specs: list[dict[str, Any]] = []
        computed: list[dict[str, Any]] = []
        order: list[str] = []

        for item in columns:
            if isinstance(item, str):
                plain_specs.append({"name": item, "excel": item, "optional": False})
                order.append(item)
                continue
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or "").strip()
                if not name:
                    raise ValueError(f"В columns нужно поле name: {item!r}")

                parts = item.get("from") or item.get("concat")
                if parts is not None:
                    computed.append(
                        {
                            "name": name,
                            "from": list(parts),
                            "separator": item.get("separator", ""),
                        }
                    )
                    order.append(name)
                    continue

                excel = str(item.get("source") or item.get("excel") or name).strip()
                plain_specs.append(
                    {
                        "name": name,
                        "excel": excel,
                        "optional": bool(item.get("optional", False)),
                        "fallback": str(item.get("fallback", "")).strip() or None,
                    }
                )
                order.append(name)
                continue

            raise ValueError(
                "Элемент columns: строка, dict с name+source, или dict с name+from."
            )

        return plain_specs, computed, order

    @staticmethod
    def needed(
        plain_specs: list[dict[str, Any]],
        computed: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        out_names = [p["name"] for p in plain_specs]
        for spec in computed:
            name = str(spec["name"])
            if name not in out_names:
                out_names.append(name)
            for col in spec["from"]:
                if col not in out_names:
                    out_names.append(col)
        excel_unique = list(dict.fromkeys(p["excel"] for p in plain_specs))
        return out_names, excel_unique

    @staticmethod
    def output_names(spec: dict[str, Any]) -> list[str]:
        _, computed, order = ColumnSpecParser.parse(spec["columns"])
        names = list(order)
        for item in computed:
            n = str(item["name"])
            if n not in names:
                names.append(n)
        for out_name in spec.get("aggregate") or {}:
            if out_name not in names:
                names.append(str(out_name))
        return names


class ColumnResolver:
    """Сопоставление имён из config с заголовками Excel."""

    @staticmethod
    def lookup(df: pd.DataFrame) -> dict[str, str]:
        result: dict[str, str] = {}
        for col in df.columns:
            raw = str(col).strip()
            for variant in (raw, raw.rstrip("."), f"{raw}."):
                key = TextNorm.name(variant)
                if key and key not in result:
                    result[key] = col
        return result

    @classmethod
    def resolve(
        cls,
        df: pd.DataFrame,
        requested: list[str],
        *,
        source_file: str = "",
        optional_excel: set[str] | None = None,
    ) -> dict[str, str]:
        by_norm = cls.lookup(df)
        mapping: dict[str, str] = {}
        missing: list[str] = []
        opt = optional_excel or set()

        for col in requested:
            key = TextNorm.name(col)
            alt = TextNorm.name(str(col).strip().rstrip("."))
            if key in by_norm:
                mapping[col] = by_norm[key]
            elif alt in by_norm:
                mapping[col] = by_norm[alt]
            else:
                missing.append(col)

        if missing:
            missing = cls._fuzzy_match(df, missing, mapping, optional_excel=opt)

        missing_required = [c for c in missing if c not in opt]
        if missing_required:
            available = ", ".join(str(c) for c in df.columns)
            where = f" (файл: {source_file})" if source_file else ""
            raise KeyError(
                f"Колонки не найдены: {missing_required!r}{where}\n"
                f"Если колонка из другого Excel — вынесите её во второй блок sources.\n"
                f"Доступные заголовки: {available}"
            )
        return mapping

    @staticmethod
    def _fuzzy_match(
        df: pd.DataFrame,
        missing: list[str],
        mapping: dict[str, str],
        *,
        optional_excel: set[str] | None = None,
    ) -> list[str]:
        still_missing: list[str] = []
        used_excel = set(mapping.values())
        opt = optional_excel or set()
        for col in missing:
            col_norm = TextNorm.name(col)
            found: str | None = None
            for excel_col in df.columns:
                excel_name = str(excel_col)
                if excel_name in used_excel:
                    continue
                ex_norm = TextNorm.name(excel_col)
                if col_norm == ex_norm:
                    found = excel_name
                    break
                if col_norm in ex_norm or ex_norm in col_norm:
                    found = excel_name
                    break
                if "higher-level" in col_norm and "higher" in ex_norm and "customer" in ex_norm:
                    found = excel_name
                    break
                if col_norm in ("key", "ключ") and ex_norm in ("ключ", "key"):
                    found = excel_name
                    break
                if col_norm == "trade name" and "trade name" in ex_norm:
                    found = excel_name
                    break
                if col_norm == "so trade name" and ex_norm in ("so", "so trade name"):
                    found = excel_name
                    break
                if col_norm == "узел" and (
                    ex_norm == "узел"
                    or ex_norm == "иерархия"
                    or ex_norm.startswith("иерарх")
                ):
                    found = excel_name
                    break
                if col_norm == "orblk2" and (
                    ex_norm == "orblk2"
                    or ex_norm == "orblk.1"
                    or ("orblk" in ex_norm and "2" in ex_norm)
                ):
                    found = excel_name
                    break
                if col_norm in ("название узла",) and (
                    ex_norm == "название иерархии"
                    or ex_norm == "название узла"
                    or ("название" in ex_norm and "иерарх" in ex_norm)
                ):
                    found = excel_name
                    break
            if found:
                mapping[col] = found
                used_excel.add(found)
            elif col not in opt:
                still_missing.append(col)
        return still_missing

    @staticmethod
    def ensure_merge_keys(
        plain_specs: list[dict[str, str]],
        merge_right: list[str],
        key_excel: dict[str, str] | None,
    ) -> list[dict[str, str]]:
        have = {p["name"] for p in plain_specs}
        out = list(plain_specs)
        excel_taken = {p["excel"] for p in plain_specs}
        for key in merge_right:
            if key in have:
                continue
            excel = (key_excel or {}).get(key, key)
            if excel in excel_taken:
                continue
            out.append({"name": key, "excel": excel})
            have.add(key)
            excel_taken.add(excel)
        return out
