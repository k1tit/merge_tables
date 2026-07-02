# merge_columns

Собирает отчёты в **`merge_3805/`** (и др. по SOrg) из Excel-выгрузок по **`config.yaml`**.

> **Важно:** основной файл — **`merge_3805/merge_columns_3805.xlsx`**, не `merge_columns_3805.xlsx` в корне проекта.  
> Файл в корне — устаревший (без разбивки на ADI/AIN/…); при сборке удаляется автоматически.

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
  - `merge_3805/Trade Name.xlsx` — все строки с заполненным Trade Name (включая QDI/QIN)
  - `merge_3805/ADI.xlsx`, `AIN.xlsx`, `BDI.xlsx`, `BIN.xlsx` — по **Check bucket**, Trade Name пустой
  - `merge_3805/QDI QIN.xlsx` — bucket **QDI** / **QIN**, Trade Name пустой

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

Перед запуском закрой выходные файлы в Excel (папка `merge_3805/`, не корень проекта).
