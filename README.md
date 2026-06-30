# merge_columns

Собирает **`merge_columns_3805.xlsx`** (и др. по SOrg) из Excel-выгрузок по **`config.yaml`**.

## Запуск

```powershell
pip install -r requirements.txt
python merge_columns.py
```

Без меню: `python merge_columns.py -s 3805 --no-menu`

## Данные

Папка с выгрузками (например `3805/`) — не в git. В корне проекта: **`Справочник At Work&Education.xlsx`**.

Перед запуском закройте выходной файл в Excel (например `merge_columns_3805.xlsx`).
