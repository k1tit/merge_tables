from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from .builder import ReportBuilder, build_merge
from .constants import REQUIRED_CH6_COLUMNS, SCRIPT_VERSION
from .sorg import SorgSelector


class Application:
    """Точка входа: argparse, меню SOrg, запуск сборки."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self.args = self._parse_args(argv)

    @staticmethod
    def _parse_args(argv: list[str] | None) -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description="Сборка merge_columns.xlsx из config.yaml"
        )
        parser.add_argument(
            "-c",
            "--config",
            type=Path,
            default=Path(__file__).resolve().parent.parent / "config.yaml",
            help="Путь к config.yaml",
        )
        parser.add_argument(
            "-s",
            "--sorg",
            metavar="3801",
            help="Папка SOrg (3801–3806), без интерактивного меню",
        )
        parser.add_argument(
            "--no-menu",
            action="store_true",
            help="Не показывать меню: взять sorg из config.yaml",
        )
        return parser.parse_args(argv)

    def run(self) -> int:
        config_path = self.args.config.resolve()
        base_dir = config_path.parent
        try:
            with config_path.open(encoding="utf-8") as f:
                raw_cfg = yaml.safe_load(f)
            selector = SorgSelector(base_dir, raw_cfg)
            cfg, selected = selector.resolve(
                cli_sorg=self.args.sorg,
                no_menu=self.args.no_menu or bool(self.args.sorg),
            )
            if self.args.sorg or self.args.no_menu:
                print(f"  SOrg (без меню): {selected}")
            out = build_merge(config_path, cfg=cfg)
        except (FileNotFoundError, KeyError, ValueError, PermissionError) as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1

        print(f"Готово: {out.resolve()} ({out.stat().st_size} байт)")
        return self._verify_output(out)

    @staticmethod
    def _verify_output(out: Path) -> int:
        exit_code = 0
        try:
            hdr = pd.read_excel(out, nrows=0)
            cols = list(hdr.columns)
            print(f"Колонок в файле: {len(cols)}")
            for c in REQUIRED_CH6_COLUMNS:
                if c in cols:
                    print(f"  {c} — колонка №{cols.index(c) + 1} (есть в файле)")
                else:
                    print(
                        f"  {c} — НЕТ в файле! Нужен скрипт {SCRIPT_VERSION} и config с enrich_from"
                    )
                    exit_code = 1
        except Exception as e:
            print(f"  (не удалось проверить заголовки: {e})")
            exit_code = 1
        return exit_code


def main() -> int:
    return Application().run()
