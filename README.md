# merge_columns

Собирает **`merge_columns_3805.xlsx`** (и др. по SOrg) из Excel-выгрузок по **`config.yaml`**.

## Запуск

```powershell
pip install -r requirements.txt
python merge_columns.py
```

Без меню: `python merge_columns.py -s 3805 --no-menu`

**Все SOrg сразу:** `python merge_columns.py --all` → `merge_columns_ALL.xlsx`  
В интерактивном меню: `a` или `все`.

## Данные

**Выгрузки** — в папке SOrg (`3801/` … `3806/`), не в git.

**Справочники** — один раз в папке **`references/`** (для всех SOrg):

- `Справочник_CH6_CGrp.xlsx`
- `Справочник_CH6.xlsx`
- `Справочник Ключ-Иерархия.xlsx`
- `Справочник At Work&Education.xlsx`
- `trade.xlsx`

Перед запуском закрой выходной файл в Excel (например `merge_columns_3805.xlsx`).
