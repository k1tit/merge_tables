"""Проверки по категории файла → Check Status, Comment."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .nodes_ref import (
    ch6_key_category,
    ch6_keys_match,
    load_ch6_key_map,
    load_trade_name_set,
)
from .text_utils import TextNorm

STATUS_OK = "Ok"
STATUS_FALSE = "False"
STATUS_NEED_DATA = "Need_Data"
STATUS_KEY_NOT_FOUND = "Key_not_found"
STATUS_NEED_REVIEW = "Need_review"

TN_MISSING_REF_COMMENT = "TN отсутствует в справочнике"

KA_CGRP = frozenset({"S", "F", "K", "Q"})


def _val(row: pd.Series, col: str) -> str:
    if col not in row.index:
        return ""
    return TextNorm.key_value(row[col])


def _split_list(val: object, sep: str = ", ") -> list[str]:
    return [
        TextNorm.norm_customer_node(v)
        for v in TextNorm.split_aggregated(val, separator=sep)
        if TextNorm.norm_customer_node(v)
    ]


def _compare_ch6_with_expected(
    ch6: str,
    expected: str | list[str],
) -> tuple[str, str]:
    if not ch6:
        return STATUS_NEED_DATA, "CH6 пустой"
    if isinstance(expected, str):
        expected_list = [TextNorm.norm_customer_node(expected)] if expected else []
    else:
        expected_list = [TextNorm.norm_customer_node(e) for e in expected if e]
    expected_list = [e for e in expected_list if e]
    if not expected_list:
        return STATUS_KEY_NOT_FOUND, "Ожидаемый CH6 не найден"
    if ch6 in expected_list:
        return STATUS_OK, f"CH6 {ch6} совпал"
    return STATUS_FALSE, f"CH6 {ch6} != expected {', '.join(expected_list)}"


def _check_trade_name(row: pd.Series) -> tuple[str, str]:
    ch6 = TextNorm.norm_customer_node(_val(row, "CH6"))
    tn_list = _split_list(_val(row, "TN_CH6"))
    cgrp = _val(row, "CGrp").upper()
    tn_cgrp_raw = _val(row, "TN_CGrp")
    if not ch6:
        return STATUS_NEED_DATA, "CH6 пустой"
    if not tn_list:
        return STATUS_NEED_DATA, "TN_CH6 пустой"
    if ch6 in tn_list:
        if tn_cgrp_raw:
            if TextNorm.cgrp_in_tn_cgrp(cgrp, tn_cgrp_raw):
                return STATUS_OK, f"CH6 {ch6} в TN_CH6, CGrp={cgrp}"
            if cgrp:
                return STATUS_FALSE, f"CH6 in TN, CGrp {cgrp} != TN_CGrp {tn_cgrp_raw}"
        return STATUS_OK, f"CH6 {ch6} в TN_CH6"
    return STATUS_FALSE, f"CH6 {ch6} != TN_CH6 ({', '.join(tn_list)})"


def _check_key_ch6(row: pd.Series) -> tuple[str, str]:
    ch6 = TextNorm.norm_customer_node(_val(row, "CH6"))
    key = _val(row, "Key")
    key_ch6 = TextNorm.norm_customer_node(_val(row, "Key_CH6"))
    if not ch6:
        return STATUS_NEED_DATA, "CH6 пустой"
    if not key:
        return STATUS_NEED_DATA, "Key не собран"
    if not key_ch6:
        return STATUS_KEY_NOT_FOUND, f"Key {key} не найден в Key_CH6"
    status, msg = _compare_ch6_with_expected(ch6, key_ch6)
    return status, msg


def _check_q_vend(row: pd.Series) -> tuple[str, str]:
    cgrp = _val(row, "CGrp").upper()
    a7 = _val(row, "A7")
    if cgrp == "Q":
        return _check_key_ch6(row)
    if a7 == "246":
        return _check_key_ch6(row)
    return STATUS_NEED_REVIEW, f"Q+Vend: CGrp={cgrp}, A7={a7}"


def _check_in_partner(row: pd.Series, key_map: dict[str, str]) -> tuple[str, str]:
    ch6 = TextNorm.norm_customer_node(_val(row, "CH6"))
    zw_list = _split_list(_val(row, "ZW_CH6"))
    sorg = _val(row, "SOrg.")
    zw_so_list = _split_list(_val(row, "ZW_SO"))
    if not ch6:
        return STATUS_NEED_DATA, "CH6 пустой"
    if not zw_list:
        return STATUS_NEED_DATA, "ZW_CH6 пустой"
    cross_so = bool(sorg and zw_so_list and sorg not in zw_so_list)
    if cross_so:
        for zw in zw_list:
            if ch6_keys_match(ch6, zw, key_map):
                lk = ch6_key_category(ch6, key_map)
                return STATUS_OK, f"Cross-SO: KEY={lk or 'same CH6'}"
        return STATUS_FALSE, "Cross-SO: CH6 KEY != ZW_CH6 KEY"
    status, msg = _compare_ch6_with_expected(ch6, zw_list)
    return status, msg


def _check_direct_rest(row: pd.Series) -> tuple[str, str]:
    grp4 = _val(row, "Grp4").upper()
    cgrp = _val(row, "CGrp").upper()
    if grp4 == "IN" or cgrp in KA_CGRP:
        return STATUS_NEED_REVIEW, f"Direct_Rest: Grp4={grp4}, CGrp={cgrp}"
    return _check_key_ch6(row)


def apply_category_checks(
    df: pd.DataFrame,
    *,
    base_dir: str,
    reference_file: str = "References_CH6.xlsx",
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    key_map = load_ch6_key_map(base_dir, reference_file)
    trade_names = load_trade_name_set(base_dir, reference_file)
    statuses: list[str] = []
    comments: list[str] = []
    for _, row in out.iterrows():
        cat = _val(row, "Category") or "Direct_Rest"
        if cat == "Trade Name":
            st, cm = _check_trade_name(row)
        elif cat == "Q+Vend.":
            st, cm = _check_q_vend(row)
        elif cat in ("IN_ZW_235&249", "A DI", "B DI"):
            st, cm = _check_key_ch6(row)
        elif cat == "IN_Partner_CH6":
            st, cm = _check_in_partner(row, key_map)
        elif cat == "Direct_Rest":
            st, cm = _check_direct_rest(row)
        else:
            st, cm = STATUS_NEED_REVIEW, f"Неизвестная категория {cat}"
        trade = TextNorm.trade_name_key(_val(row, "Trade Name"))
        if trade and trade not in trade_names:
            cm = TN_MISSING_REF_COMMENT
        statuses.append(st)
        comments.append(cm)
    out["Check Status"] = statuses
    out["Comment"] = comments
    out["Comment_Check_CH6"] = ""
    return out
