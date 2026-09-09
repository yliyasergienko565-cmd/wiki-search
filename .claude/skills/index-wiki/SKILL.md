---
name: index-wiki
description: Use to build or refresh the wiki index — the single file wiki-index.md that maps every document in the DataPeople corporate wiki (https://agentsim.online/wiki/) with a short "what it's about" + list of questions it covers. Run this for a manual rebuild — wiki-index.md is missing, looks stale, or the wiki has changed (docs added/removed/rewritten). Note: /wiki-search already self-checks the index (build_wiki_index.py check) and rebuilds it automatically before searching, so calling this by hand is only needed when you want to force a fresh index now. Triggers: «обнови индекс вики», «пересобери wiki-index», «проиндексируй вики».
---

# index-wiki

Собирает **`wiki-index.md`** в корне репозитория — карту всей корпоративной вики
DataPeople: по карточке на каждый из ~99 документов (заголовок, полный URL,
раздел, дата «Обновлено», 2-3 предложения «о чём» и список вопросов из
подзаголовков). Этот файл потом читает `/wiki-search`, чтобы выбрать 2-3 нужных
документа и открыть только их.

## Что делать

1. Перейти в каталог проекта (там лежат `build_wiki_index.py` и `wiki_common.py`):
   ```
   cd "C:/Users/yliya/OneDrive/Документы/ailearning/wiki-search"
   python build_wiki_index.py
   ```
   Скрипт обходит корень вики → 7 разделов → все документы (параллельно,
   ~5-10 сек) и перезаписывает `wiki-index.md`.

2. Проверить вывод: в конце должно быть `Записано: …\wiki-index.md (99 карточек…)`.
   Если напечатано `ВНИМАНИЕ: N документ(ов) не загрузились` — повторить запуск
   (обычно разовый сетевой сбой).

3. Открыть `wiki-index.md`, глянуть шапку: `Собрано: <сегодня>`, число документов
   правдоподобное (около 99). Пробежать 2-3 карточки — поле «О чём» должно
   осмысленно описывать документ.

4. Если какое-то «О чём» получилось совсем кривым (обрывок таблицы, мусор) —
   можно вручную переписать эту строку в `wiki-index.md`. Помнить: следующий
   запуск `/index-wiki` перезатрёт правку целиком.

## Заметки

- Зависимостей нет — только стандартная библиотека Python 3.
- `wiki-index.md` **коммитится** в репозиторий: это общий артефакт данных,
  его читает `/wiki-search`.
- Флаг `--out <путь>` — записать индекс в другое место (для отладки).
- Разделы вики: finance, general, hr, marketing, product, sales, tech.
