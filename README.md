# merge_columns

Собирает **`merge_columns_3805.xlsx`** (и др. по SOrg) из Excel-выгрузок по **`config.yaml`**.

## Запуск

```powershell
pip install -r requirements.txt
python merge_columns.py
```

### Одна папка SOrg

```powershell
python merge_columns.py -s 3805 --no-menu
```

Результат: `merge_columns_3805.xlsx`

### Все папки сразу (3801–3806)

```powershell
python merge_columns.py --all
```

Результат: **`merge_columns_ALL.xlsx`** — данные из всех папок, где есть Excel.

В интерактивном меню (`python merge_columns.py`): введите **`a`**.

## Данные

**Выгрузки** — в папке SOrg (`3801/` … `3806/`), не в git.

**Справочники** — один раз в папке **`references/`** (для всех SOrg):

- `Справочник_CH6_CGrp.xlsx`
- `Справочник_CH6.xlsx`
- `Справочник Ключ-Иерархия.xlsx`
- `Справочник At Work&Education.xlsx`
- `trade.xlsx`

Перед запуском закрой выходной файл в Excel (например `merge_columns_3805.xlsx`).
