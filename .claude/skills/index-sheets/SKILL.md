---
name: index-sheets
description: Use to build or refresh the sheets index — the single file sheets-index.md that maps every manager spreadsheet listed in sheets-sources.txt (manager, tab + gid, columns, row count, what the data is, deal stages, list of companies). Run this for a manual rebuild — sheets-index.md is missing, looks stale, or the set of tables / their structure changed. Note: /sheets-search already self-checks the index and rebuilds it automatically before searching. Triggers: «обнови индекс таблиц», «пересобери sheets-index», «проиндексируй таблицы менеджеров».
---

# index-sheets

Собирает **`sheets-index.md`** в корне репозитория — карту всех таблиц
менеджеров (по карточке на вкладку): менеджер, ссылка + `gid`, колонки, число
строк, про что данные, какие стадии сделок, список компаний/лидов. Этот файл
читает `/sheets-search`, чтобы выбрать 2-3 нужные таблицы и открыть только их.

Каталог проекта:
```
C:/Users/yliya/OneDrive/Документы/ailearning/wiki-search
```

## Что делать

1. Список таблиц — в `sheets-sources.txt` (одна ссылка на Google-таблицу в
   строке). Нужно добавить/убрать таблицу — сначала поправить этот файл.

2. Собрать индекс:
   ```
   cd "C:/Users/yliya/OneDrive/Документы/ailearning/wiki-search"
   python build_sheets_index.py
   ```
   Скрипт по каждой таблице читает вкладки (через `/htmlview`) и данные
   (CSV-экспорт, доступ «по ссылке», без OAuth) и перезаписывает
   `sheets-index.md`.

3. Проверить вывод: `Записано: …\sheets-index.md (N карточек …)`; в шапке
   `Собрано: <сегодня>` и `таблиц: 10`. Пробежать пару карточек — колонки и
   список компаний должны выглядеть осмысленно.

## Заметки

- Зависимостей нет — только стандартная библиотека Python 3.
- `sheets-index.md` **коммитится**: это общий артефакт данных, его читает
  `/sheets-search`.
- Таблицы должны быть открыты «для всех, у кого есть ссылка» (просмотр). Если
  какая-то закрыта — её вкладки/данные не прочитаются, в логе будет `! Таблица N`.
- `python build_sheets_index.py check` — печатает `OK` / `WARN` / `REBUILD`
  (используется скиллом `/sheets-search`, отдельно звать не нужно).
