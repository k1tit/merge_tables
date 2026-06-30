from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from .builder import build_merge
from .constants import REQUIRED_CH6_COLUMNS
from .log_sink import make_console_log
from .sorg import SorgSelector


class Application:
    def __init__(self, argv: list[str] | None = None) -> None:
        self.args = self._parse_args(argv)

    @staticmethod
    def _parse_args(argv: list[str] | None) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Сборка merge_columns.xlsx")
        parser.add_argument(
            "-c",
            "--config",
            type=Path,
            default=Path(__file__).resolve().parent.parent / "config.yaml",
        )
        parser.add_argument("-s", "--sorg", metavar="3805", help="Папка SOrg без меню")
        parser.add_argument("--no-menu", action="store_true", help="Без меню SOrg")
        parser.add_argument("-q", "--quiet", action="store_true", help="Минимум вывода")
        return parser.parse_args(argv)

    def run(self) -> int:
        config_path = self.args.config.resolve()
        base_dir = config_path.parent
        log_file = base_dir / "merge_build.log"

        try:
            with config_path.open(encoding="utf-8") as f:
                raw_cfg = yaml.safe_load(f)

            selector = SorgSelector(base_dir, raw_cfg)
            cfg, selected = selector.resolve(
                cli_sorg=self.args.sorg,
                no_menu=self.args.no_menu or bool(self.args.sorg),
            )

            cfg_run = dict(cfg)
            if self.args.quiet:
                cfg_run["verbose"] = False
            elif self.args.sorg or self.args.no_menu:
                print(f"SOrg: {selected}")

            log = None if self.args.quiet else make_console_log(log_file)
            out = build_merge(config_path, cfg=cfg_run, log=log)
            return self._verify_output(out, quiet=self.args.quiet)
        except (FileNotFoundError, KeyError, ValueError, PermissionError) as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1

    @staticmethod
    def _verify_output(out: Path, *, quiet: bool) -> int:
        if quiet:
            return 0
        try:
            cols = list(pd.read_excel(out, nrows=0).columns)
            missing = [c for c in REQUIRED_CH6_COLUMNS if c not in cols]
            if missing:
                print(f"В отчёте нет колонок: {missing}", file=sys.stderr)
                return 1
            print(f"Готово: {out.resolve()}")
            return 0
        except Exception as e:
            print(f"Не удалось проверить {out}: {e}", file=sys.stderr)
            return 1


def main() -> int:
    return Application().run()
