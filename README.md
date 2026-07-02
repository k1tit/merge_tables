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

  - `merge_3805/merge_columns_3805.xlsx` — остаток: всё, что не попало в split-файлы ниже (в т.ч. без Trade Name)
  - `merge_3805/Trade Name.xlsx` — Trade Name заполнен, не в bucket ADI/AIN/BDI/BIN/QDI/QIN
  - `merge_3805/ADI.xlsx`, `AIN.xlsx`, `BDI.xlsx`, `BIN.xlsx` — по **Check bucket** (CGrp+Grp4)
  - `merge_3805/QDI QIN.xlsx` — оба bucket **QDI** и **QIN** в одном файле

### Все папки сразу (3801–3806)

```powershell
python merge_columns.py --all
```

Результат: **`merge_3801/` … `merge_3806/`** — в каждой папке основной файл и bucket-файлы.

В интерактивном меню (`python merge_columns.py`): пункт **`a`** — сборка всех папок.

## Данные

**Выгрузки** — в папке SOrg (`3801/` … `3806/`), не в git.

**Справочники** — один раз в папке **`references/`** (для всех SOrg):

- `Справочник_CH6_CGrp.xlsx`
- `Справочник_CH6.xlsx`
- `Справочник Ключ-Иерархия.xlsx`
- `Справочник At Work&Education.xlsx`
- `trade.xlsx`

Перед запуском закрой выходной файл в Excel (например `merge_columns_3805.xlsx`).
