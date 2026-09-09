---
name: ask
description: Use for any question about how DataPeople works or what's happening in sales when the answer may live in EITHER the corporate wiki OR the managers' spreadsheets (or both) — policy + pipeline, "what does the regulation say and do managers follow it", cross-source checks. Runs /wiki-search and /sheets-search under the hood, merges their findings into one answer, and ALWAYS cites every fact (wiki page URL or spreadsheet link with row range). Flags contradictions between sources explicitly. Triggers: «спроси», «/ask …», «узнай по компании», «что у нас по …».
---

# ask

Единая точка ответа по обоим источникам компании: **корпоративная вика**
(`/wiki-search`) и **таблицы менеджеров** (`/sheets-search`). Задача — не просто
переслать вопрос, а разложить его на подзапросы к нужным источникам, собрать
факты и вернуть **один** ответ, где у каждого факта есть ссылка, а расхождения
между источниками помечены явно.

Каталог проекта:
```
C:/Users/yliya/OneDrive/Документы/ailearning/wiki-search
```

## Что делать

1. **Разложить вопрос.** Определить, какие источники нужны:
   - процессы, политики, регламенты, определения, «как у нас принято» → **вика**;
   - клиенты, сделки, суммы, этапы, кто кого ведёт, лиды, звонки → **таблицы**;
   - «регламент говорит X — а по факту?» → **оба**.
   Крупную тему разбить на 2-5 конкретных под-вопросов.

2. **Прогнать вику** (если нужна) — по инструкции скилла `wiki-search`:
   ```
   cd "C:/Users/yliya/OneDrive/Документы/ailearning/wiki-search"
   python build_wiki_index.py check      # OK / WARN / REBUILD (→ python build_wiki_index.py)
   ```
   прочитать `wiki-index.md`, выбрать 2-3 карточки, открыть их
   `python fetch_pages.py <URL...>`.

3. **Прогнать таблицы** (если нужны) — по инструкции скилла `sheets-search`:
   ```
   python build_sheets_index.py check    # OK / WARN / REBUILD (→ python build_sheets_index.py)
   ```
   прочитать `sheets-index.md`, выбрать таблицы, открыть их
   `python fetch_sheets.py <N...> [--filter <слово>]`.

4. **Слить в один ответ.** Для каждого под-вопроса — вывод и **источники**:
   - вика: полный URL страницы;
   - таблицы: ссылка вида `…/edit?gid={GID}&range=A{N}:Z{N}` на конкретную строку.
   Если факт собран из нескольких мест — перечислить все.

5. **Пометить противоречия.** Если источники расходятся (вика ↔ вика,
   вика ↔ таблица, строка ↔ строка) — вынести это отдельным пунктом
   «⚠️ Противоречие: …» с обеими ссылками и коротким разбором, какой источник
   свежее / авторитетнее (для вики — дата «Обновлено» и слова
   «актуальн»/«текущ»; для таблиц — сводный пайплайн vs личная таблица,
   дата последнего контакта).

6. **Чего нет — так и сказать.** Не выдумывать, не додумывать.

## Заметки

- `/ask` ничего не считает «на глаз»: любые числа — из открытых строк/страниц,
  с ссылкой.
- Оба под-скилла сами следят за свежестью своих индексов (`… check`) — отдельно
  звать `/index-wiki` / `/index-sheets` не нужно.
- Один и тот же клиент может быть у нескольких менеджеров и в своде Анны —
  это часто и есть ответ (кто на самом деле ведёт, нет ли дубля).
