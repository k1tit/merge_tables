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

  - `merge_3805/Trade Name.xlsx` — Trade Name заполнен
  - `merge_3805/Q+Vend.xlsx` — CGrp=Q или A7=246
  - `merge_3805/IN_ZW_235&249.xlsx` — Grp4=IN, CGrp=A/B/H, ZW_A7=235/249
  - `merge_3805/IN_Partner_CH6.xlsx` — остальные Grp4=IN
  - `merge_3805/A DI.xlsx`, `B DI.xlsx` — CGrp=A/B, Grp4=DI
  - `merge_3805/Direct_Rest.xlsx` — остаток

### Все папки сразу (3801–3806)

```powershell
python merge_columns.py --all
```

Результат: **`merge_3801/` … `merge_3806/`** — в каждой папке основной файл и bucket-файлы.

В интерактивном меню (`python merge_columns.py`): пункт **`a`** — сборка всех папок.

## Данные

**Выгрузки** — в папке SOrg (`3801/` … `3806/`), не в git.

**Справочник** — один файл в корне проекта (для всех SOrg):

- `References_CH6.xlsx` — листы `Key_CH6`, `Nodes_CH6`, `AtWo&Ed`

**Устаревшие** (в `references/`, не используются кодом):

- `Справочник_CH6_CGrp.xlsx`, `Справочник_CH6.xlsx`, `Справочник Ключ-Иерархия.xlsx`, …

Перед запуском закрой выходные файлы в Excel (папка `merge_3805/`, не корень проекта).
