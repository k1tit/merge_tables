# merge_columns — сборка отчёта по клиентам SAP

Скрипт объединяет несколько Excel-выгрузок и справочников в один файл **`merge_columns.xlsx`**: база клиентов, иерархии CH6, ZW, проверки качества и вычисляемые ключи.

Настройка — в **`config.yaml`**. Вся логика вынесена в пакет **`lib/`** и построена по принципам **ООП**: отдельные классы с одной зоной ответственности, общий контекст прогона, декларативная конфигурация вместо «скрипта из одного файла».

---

## Быстрый старт

### 1. Клонировать репозиторий

```powershell
git clone https://github.com/k1tit/merge_tables.git
cd merge_tables
```

### 2. Установить зависимости

```powershell
pip install -r requirements.txt
```

### 3. Положить исходные Excel

В репозитории **нет** папки с данными (она в `.gitignore`). Создайте каталог с кодом SOrg, например:

```
merge_tables\
  merge_columns.py
  config.yaml
  3805\                    ← папка с выгрузками
    3805 Base.xlsx
    3805 CH6.xlsx
    3805 ZW.xlsx
    3805 ZW base.xlsx
    3805 ZW CH6.xlsx
    Справочник_CH6_CGrp.xlsx
    Справочник Ключ-Иерархия.xlsx
  Справочник At Work&Education.xlsx   ← поводы A8 для Key (в корне проекта)
```

Имена файлов должны начинаться с кода SOrg (`3805`, `3804`, …) — при смене SOrg скрипт подставит нужный префикс автоматически.

### 4. Запустить сборку

**Интерактивно** (меню SOrg + пошаговый вывод в консоль):

```powershell
python merge_columns.py
```

или двойной клик / из PowerShell:

```powershell
.\run.ps1
```

В меню: номер папки `3801`–`3806`, код папки или **Enter** = значение из `config.yaml`.  
В консоли видны все шаги сборки; полный лог — в **`merge_build.log`**.

Для скриптов и CI (без меню):

```powershell
python merge_columns.py -s 3805 --no-menu
```

Тихий режим (только итог):

```powershell
python merge_columns.py -s 3805 --no-menu -q
```

Результат: **`merge_columns.xlsx`** в корне проекта.

> Перед запуском закройте `merge_columns.xlsx` в Excel — иначе запись завершится ошибкой `Permission denied`.

---

## Что делает отчёт

```
3805 Base          → основная таблица (клиенты)
     ↓ merge
3805 CH6, справочники → CH6, CH6_CGrp, TN_CH6
3805 ZW / ZW CH6   → ZW, ZW_CH6, ZW_A7, …
     ↓
вычисляемые колонки → Customer Key, Key
     ↓
Справочник Ключ-Иерархия → Key_CH6, Key_CH6_Name
     ↓
проверки Check *   → true / false
     ↓
merge_columns.xlsx
```

Одна строка отчёта = **клиент (SOrg. + Customer)**. Несколько узлов TN_CH6 на Trade Name остаются в одной ячейке через `, `.

---

## Колонки отчёта

Порядок задаётся в `config.yaml` → `column_order`.

### База (из 3805 Base)

| Колонка | Источник в файле |
|---------|------------------|
| SOrg., Customer, Name | как в выгрузке |
| Trade Name | Search Term 2 |
| Indus., A7, A8, CGrp, Grp4, … | как в выгрузке |

### CH6 и иерархия

| Колонка | Откуда | Ключ merge |
|---------|--------|------------|
| **CH6** | 3805 CH6 → HgLvCust. | SOrg. + Customer |
| **CH6_Name** | 3805 CH6 → Text:Customer number of the higher-level | SOrg. + Customer |
| **CH6_CGrp** | Справочник_CH6_CGrp | CH6 = 6th level |
| **TN_CH6** | Справочник_CH6_CGrp → 6th level | SOrg. + Trade Name |
| **TN_CH6_Name** | Справочник → 6th level_name | то же |

**TN_CH6:** несколько узлов на один Trade Name склеиваются через `, ` (как ZW_CH6).  
Проверка **Check CH6 Customer & TN** сравнивает CH6 со **списком** в TN_CH6: найден → `true`, не найден → `false`.

### ZW (нулевой уровень)

| Колонка | Откуда |
|---------|--------|
| **ZW** | 3805 ZW → KTONR |
| **ZW_SO** | 3805 ZW → VKORG |
| **ZW_A7**, **ZW_CGrp** | 3805 ZW base |
| **ZW_CH6** | 3805 ZW CH6 → HgLvCust. (через enrich по ZW_SO + ZW) |
| **ZW_CH6_Name** | текст верхнего уровня из того же файла |

Несколько ZW на одного клиента склеиваются в одну ячейку через `, ` (aggregate).

### Вычисляемые ключи

#### Customer Key

Компактный ключ для join со справочником «Ключ-Иерархия»:

- обычно: `Grp4` + `CGrp` + `A7` + суффикс `380N`
- с A8: если сработала логика At work/Education **и** A8 есть в справочнике (см. Key)

В итоговый Excel **не выводится** — используется только внутри сборки.

#### Key

**Конкатенация** значений полей **без разделителя** (как `astype(str)` + сложение в pandas).

Запись `Grp4 & CGrp & A7 & …` в макете — это **список колонок**, не символ `&` в результате.

| Сценарий | Поля в Key |
|----------|------------|
| Обычный клиент | Grp4 + CGrp + A7 + ZW_A7 + Indus. |
| Grp4 = **DI** | Grp4 + CGrp + A7 + Indus. (**без ZW_A7**) |
| At work / Education | + **A8** (4-й элемент) между A7 и ZW_A7 |

**Справочник At Work&Education** — второй лист **`Справочник At Work&Education`** в `merge_columns.xlsx` (исходник для правок: файл в корне проекта):

повод потребления (колонка **A8**) включается в Key только если значение есть в справочнике.  
Список по умолчанию в `config.yaml` → `at_work_a8_reference.values` (At Work: 216, 030, 044, 043, 025, 029, 042, 207).

**Условия для A8 и обратной проверки:**

| CH6_CGrp (повод At w/Ed) | CGrp (бизнес-тип) | A8 в справочнике | Результат |
|--------------------------|-------------------|------------------|-----------|
| не P | любой | — | Key без A8 |
| P | P или Q | да | Key **с A8** |
| P | P или Q | нет | Key **без A8** |
| P | не P и не Q | любой | Key **пустой** (ошибка данных) |

P/Q в CGrp сами по себе **не** включают A8 — нужен повод `CH6_CGrp = P` и A8 из справочника.

#### Key_CH6, Key_CH6_Name

Из справочника **Справочник Ключ-Иерархия** по join `Customer Key` = `Ключ`:

- **Key_CH6** ← поле «Иерархия» (узел)
- **Key_CH6_Name** ← «Название узла»

---

## Проверки (колонки Check *)

Значения: **`true`** / **`false`** (не ОК/FAIL).

| Колонка | Смысл |
|---------|--------|
| **Check CH6_CGrp_KA** | Если CGrp или CH6_CGrp ∈ {S, F, K, Q} — они должны совпадать |
| **Check CH6 Customer & ZW** | CH6 входит в список ZW_CH6 (через `, `); только при Grp4 = IN |
| **Check CH6 Customer & TN** | CH6 входит в список TN_CH6 (через `, `); нужны CH6, TN_CH6, Trade Name |
| **Check CH6 Customer & Key_CH6** | CH6 = Key_CH6; нужны CH6 и Key_CH6 |

Если условие `apply_when` не выполняется, проверка остаётся `true` (не применялась).

---

## Конфигурация

Файл **`config.yaml`**:

| Секция | Назначение |
|--------|------------|
| `sorg` | Шаблон имён файлов (3805 → 3804 при выборе другой папки) |
| `column_order` | Порядок колонок в отчёте |
| `sources` | Источники и правила merge (ключи, aggregate, dedupe) |
| `computed_columns` | Key, Customer Key |
| `post_sources` | Справочники после вычисления Key |
| `checks` | Правила проверок |
| `text_columns` | Колонки, которые пишутся в Excel как текст (ИНН, A8) |

### Полезные флаги в sources

| Параметр | Эффект |
|----------|--------|
| `dedupe: false` | Не схлопывать дубликаты по ключу — размножать строки |
| `aggregate` | Несколько значений на ключ → одна ячейка через `, ` (ZW, ZW_A7, TN_CH6) |
| `enrich_from` | Подмешать колонки из другого файла до merge (ZW_CH6 из ZW CH6) |
| `merge_require_non_empty` | Очистить добавленные колонки, если ключ пустой |
| `optional: true` | Колонки нет в файле — добавить пустую, не падать |

---

## Архитектура (ООП)

Код организован как **библиотека классов**, а не монолитный скрипт. Точка входа `merge_columns.py` только делегирует работу пакету `lib`.

### Принципы

| Принцип | Как реализовано |
|---------|-----------------|
| **Single Responsibility** | Чтение Excel, merge, агрегация, проверки и вычисление Key — разные классы |
| **Open/Closed** | Новый источник или проверка добавляются в `config.yaml` и при необходимости — новый handler в `CheckEngine`, без переписывания пайплайна |
| **Dependency injection** | Сервисы получают `BuildContext` (пути, config, движки, лог) — не читают глобальное состояние |
| **Разделение данных и логики** | `config.yaml` описывает *что* мержить; классы `lib/` — *как* |

### Цепочка сборки

```
Application (CLI)
    → SorgSelector          # выбор 3801–3806, подстановка имён файлов
    → ReportBuilder         # оркестратор пайплайна
        → ExcelSourceReader # чтение листов
        → DataMerger        # последовательный merge / enrich_from / post-merge
            → MergeKeysParser
            → DataAggregator
            → ColumnResolver / ColumnSpecParser
        → ComputedColumnsApplier   # Key, Customer Key
        → CheckEngine              # колонки Check *
```

### Классы `lib/`

| Класс | Файл | Ответственность |
|-------|------|-----------------|
| `Application` | `cli.py` | argparse, меню SOrg, запуск сборки |
| `ReportBuilder` | `builder.py` | Оркестрация: read → merge → compute → checks → Excel |
| `BuildContext` | `context.py` | Dataclass: config, пути, движки, лог одного прогона |
| `SorgSelector` | `sorg.py` | Выбор папки SOrg и переписывание префиксов в config |
| `ExcelSourceReader` | `sources.py` | Чтение Excel, переименование колонок по spec |
| `DataMerger` | `merger.py` | Left join источников, `enrich_from`, post-merge |
| `MergeKeysParser` | `merge_keys.py` | Разбор `merge_on`, нормализация ключей |
| `DataAggregator` | `aggregate.py` | Склейка нескольких строк на ключ (ZW, ZW_A7) |
| `ColumnSpecParser` / `ColumnResolver` | `column_resolver.py` | Маппинг «поле в файле» → «колонка в отчёте» |
| `ComputedColumnsApplier` | `computed.py` | Вычисляемые колонки: Key, Customer Key |
| `CheckEngine` | `checks.py` | Проверки качества (`true` / `false`) |
| `TextNorm` | `text_utils.py` | Нормализация значений и имён колонок |
| `PathResolver` | `paths.py` | Поиск файлов по имени и алиасам |

Вспомогательные функции (`build_merge`, `main`) — тонкие фасады над `ReportBuilder` / `Application`.

### Расширение

- **Новый источник** — блок в `sources` / `post_sources` в `config.yaml`.
- **Новая проверка** — запись в `checks` + метод в `CheckEngine._handlers` (если нужен новый тип).
- **Новая вычисляемая колонка** — spec в `computed_columns` + ветка в `ComputedColumnsApplier.apply`.

---

## Структура проекта

```
merge_columns.py      # точка входа (делегирует в lib)
config.yaml           # декларативная конфигурация
requirements.txt
run.ps1
lib/                  # пакет классов (см. таблицу выше)
3805/                 # данные (не в git)
```

---

## Частые проблемы

| Ошибка | Решение |
|--------|---------|
| `Папка SOrg '3805' не найдена` | Создайте `3805\` и скопируйте Excel-выгрузки |
| `Permission denied: merge_columns.xlsx` | Закройте файл в Excel |
| `HgLvCust.` / `CH6_Name` пустые | Поля могут отсутствовать в выгрузке; для CH6_Name задан `optional: true` |
| Много строк с одним Trade Name | Нормально после включения построчного TN_CH6 |

---

## Версия

В логе сборки: `merge_columns 2026-06-04-oop-v1` (`lib/constants.py` → `SCRIPT_VERSION`).

---

## Передача коллеге

1. Репозиторий: `git clone` + `pip install -r requirements.txt`
2. Отдельно: zip-папка **`3805\`** с Excel (или общая сетевая папка)
3. Запуск: `python merge_columns.py` (или `.\run.ps1`)

Код и данные разделены намеренно: выгрузки большие и меняются часто, в git хранится только логика сборки.
