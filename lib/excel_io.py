"""Выбор движка pandas для чтения/записи Excel с fallback."""

from __future__ import annotations


def _engine_ok(engine: str) -> bool:
    if engine == "calamine":
        try:
            import python_calamine  # noqa: F401
        except ImportError:
            return False
    try:
        from pandas.io.excel._base import get_engine

        get_engine(engine)
        return True
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def excel_read_engine(preferred: str | None = None) -> str:
    """calamine если установлен и поддерживается pandas, иначе openpyxl."""
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(["calamine", "openpyxl"])
    seen: set[str] = set()
    for engine in candidates:
        if engine in seen:
            continue
        seen.add(engine)
        if _engine_ok(engine):
            return engine
    return "openpyxl"


def excel_write_engine(preferred: str | None = None) -> str:
    """xlsxwriter или openpyxl."""
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(["xlsxwriter", "openpyxl"])
    seen: set[str] = set()
    for engine in candidates:
        if engine in seen:
            continue
        seen.add(engine)
        if _engine_ok(engine):
            return engine
    return "openpyxl"
