#!/usr/bin/env python3
"""
TN_CH6 / TN_CH6_Name / TN_CGrp из Справочник_CH6 по ключу SOrg. + Trade Name.

  python tn_columns.py -s 3805           одна папка SOrg
  python tn_columns.py -s 3805 --full    все колонки Base + TN_*
  python tn_columns.py --all             все папки 3801–3806
  python tn_columns.py -s 3805 -o out.xlsx свой путь
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from lib.log_sink import make_console_log
from lib.sorg import ALL_SORG_LABEL, SorgSelector
from lib.tn_columns import build_tn_columns, make_context, write_tn_columns


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TN_CH6 / TN_CH6_Name / TN_CGrp из Справочник_CH6",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "config.yaml",
    )
    parser.add_argument("-s", "--sorg", metavar="3805", help="Папка SOrg")
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Все папки SOrg (3801–3806)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Путь к xlsx (по умолчанию merge_{sorg}/tn_columns_{sorg}.xlsx)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Все колонки Base, не только SOrg./Customer/Trade Name + TN_*",
    )
    parser.add_argument(
        "--no-compact",
        action="store_true",
        help="Не схлопывать дубли по SOrg.+Trade Name (только с --full)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Минимум вывода")
    return parser.parse_args(argv)


def _run_one(
    cfg: dict,
    folder: str,
    config_path: Path,
    base_dir: Path,
    *,
    output: Path | None,
    full: bool,
    compact: bool,
    log,
    quiet: bool,
) -> Path:
    cfg = dict(cfg)
    cfg["source_dir"] = folder
    cfg["verbose"] = not quiet
    ctx = make_context(base_dir, config_path, cfg, verbose=not quiet, log=log)
    df = build_tn_columns(ctx, full=full)
    out = output
    if output and not quiet:
        print(f"SOrg {folder} → {out or f'merge_{folder}/tn_columns_{folder}.xlsx'}")
    return write_tn_columns(ctx, df, out, compact=compact and not full)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config_path = args.config.resolve()
    base_dir = config_path.parent

    with config_path.open(encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f)

    selector = SorgSelector(base_dir, raw_cfg)
    cfg, selected, all_runs = selector.resolve(
        cli_sorg=args.sorg,
        no_menu=bool(args.sorg),
        cli_all=args.all,
    )

    log = None if args.quiet else make_console_log(base_dir / "tn_columns.log")
    compact = not args.no_compact

    try:
        if all_runs:
            paths: list[Path] = []
            for run_cfg, folder in all_runs:
                paths.append(
                    _run_one(
                        run_cfg,
                        folder,
                        config_path,
                        base_dir,
                        output=None,
                        full=args.full,
                        compact=compact,
                        log=log,
                        quiet=args.quiet,
                    )
                )
            if not args.quiet:
                print(f"Готово: {len(paths)} файлов")
                for p in paths:
                    print(f"  {p}")
            return 0

        if not cfg:
            raise RuntimeError("Не выбрана папка SOrg (укажите -s 3805 или --all)")
        folder = selected
        if not args.quiet and selected != ALL_SORG_LABEL:
            print(f"SOrg: {folder}")

        path = _run_one(
            cfg,
            folder,
            config_path,
            base_dir,
            output=args.output,
            full=args.full,
            compact=compact,
            log=log,
            quiet=args.quiet,
        )
        if not args.quiet:
            print(f"Готово: {path}")
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
