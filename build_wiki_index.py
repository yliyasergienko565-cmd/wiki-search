# -*- coding: utf-8 -*-
"""/index-wiki — обойти корпоративную вику DataPeople и собрать один файл
`wiki-index.md` в корне репозитория: карточка на каждый документ (заголовок,
ссылка, раздел, дата, 2-3 предложения «о чём» + список вопросов из подзаголовков).

    python build_wiki_index.py            # собрать/пересобрать wiki-index.md
    python build_wiki_index.py build      # то же явно
    python build_wiki_index.py check      # не пора ли пересобрать? (для /wiki-search)
    python build_wiki_index.py --out X.md  # другой путь для вывода

Только стандартная библиотека. Полный обход ~99 документов ≈ 5-10 сек.

Когда индекс считается устаревшим (`check`):
  1. файла нет или не читается шапка          -> REBUILD
  2. индексу больше MAX_AGE_DAYS (14) дней     -> REBUILD
     (страховка от тихих правок содержимого — дат правок в самом индексе нет)
  3. дешёвая сверка списка: обходим 7 страниц разделов (~1-2 с, документы не
     качаем) и сравниваем набор URL с индексом. Добавили/удалили документ -> REBUILD
  4. сверка не удалась из-за сети              -> WARN, ищем по текущему индексу
  5. иначе                                     -> OK

Коды выхода: 0 — можно искать (OK/WARN), 3 — нужна пересборка (REBUILD)."""
import os, re, sys, argparse, datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from wiki_common import (
    BASE, WIKI_ROOT, fetch_many, parse_doc, crawl_doc_paths, now_date,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DEFAULT = os.path.join(HERE, "wiki-index.md")
MAX_AGE_DAYS = 14

_NUM_PREFIX = re.compile(r"^\s*(?:\d+[.)]\s*|[-–—•]\s*)")


def _first_sentences(txt, n=2, cap=320):
    """Первые n предложений строки, не длиннее cap символов."""
    txt = re.sub(r"\s+", " ", txt or "").strip()
    if not txt:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", txt)
    out = " ".join(parts[:n]).strip()
    if len(out) > cap:
        out = out[:cap].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    if out and out[-1] not in ".!?…":
        out += "."
    return out


def describe(doc):
    """(про что, список вопросов) для карточки."""
    about = _first_sentences(doc.get("lead") or "", 2)
    if len(about) < 40:  # лид пустой/куцый — берём начало тела без строк-подзаголовков
        hset = {h.strip().lower() for h in doc.get("headings", [])}
        body = "\n".join(
            ln for ln in (doc.get("text") or "").splitlines()
            if ln.strip().lower() not in hset
        )
        about = _first_sentences(body, 3)
    if not about:
        about = f"Документ раздела «{doc['section']}»."

    seen, topics = set(), []
    for h in doc.get("headings", []):
        h = _NUM_PREFIX.sub("", h).strip().rstrip(":")
        low = h.lower()
        if h and low not in seen and low not in ("faq", "содержание"):
            seen.add(low)
            topics.append(h)
    return about, topics[:10]


def build(out_path):
    print("Обход вики:", WIKI_ROOT)
    paths, sections = crawl_doc_paths()
    print(f"  разделов: {len(sections)}, документов найдено: {len(paths)}")

    pages = fetch_many([BASE + p for p in paths])
    docs, errors = [], []
    for p in paths:
        res = pages.get(BASE + p)
        if not res or res[0] == "__ERR__":
            errors.append((p, res[1] if res else "нет ответа"))
            continue
        docs.append(parse_doc(res[0], p))
    for p, e in errors:
        print(f"  ! {p}: {e}")

    docs.sort(key=lambda d: (d["section"], d["slug"]))
    by_section = {}
    for d in docs:
        by_section.setdefault(d["section"], []).append(d)

    lines = [
        "# Индекс корпоративной вики DataPeople",
        "",
        f"Собрано: {now_date()} · документов: {len(docs)} · источник: {WIKI_ROOT}",
        "",
        "Файл генерируется скриптом `build_wiki_index.py` (скилл `/index-wiki`). "
        "Вручную не редактировать — перезапусти `/index-wiki`.",
        "",
        "`/wiki-search` читает только этот файл, выбирает по описаниям 2-3 "
        "релевантные карточки и открывает лишь их страницы.",
        "",
    ]

    for sec in sorted(by_section):
        group = by_section[sec]
        lines.append(f"## Раздел: {sec} ({len(group)})")
        lines.append("")
        for d in group:
            about, topics = describe(d)
            meta = f"- Обновлено: {d['updated'] or '—'}"
            if d["author"]:
                meta += f" · Автор: {d['author']}"
            lines.append(f"### {d['title']}")
            lines.append(f"- URL: {d['url']}")
            lines.append(meta)
            lines.append(f"- О чём: {about}")
            if topics:
                lines.append(f"- Вопросы: {'; '.join(topics)}")
            lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nЗаписано: {out_path}  ({len(docs)} карточек, {len(text)} байт)")
    if errors:
        print(f"ВНИМАНИЕ: {len(errors)} документ(ов) не загрузились — см. выше.")


def check(out_path):
    """Решить, пора ли пересобирать индекс. -> код выхода (0 искать / 3 пересобрать)."""
    if not os.path.exists(out_path):
        print("REBUILD: индекса нет —", out_path)
        return 3
    head = open(out_path, encoding="utf-8").read(2000)
    md = re.search(r"Собрано:\s*(\d{4}-\d{2}-\d{2})\s*·\s*документов:\s*(\d+)", head)
    if not md:
        print("REBUILD: не читается шапка индекса")
        return 3
    built = datetime.date.fromisoformat(md.group(1))
    n_index = int(md.group(2))
    age = (datetime.date.today() - built).days
    if age > MAX_AGE_DAYS:
        print(f"REBUILD: индексу {age} дн. (> {MAX_AGE_DAYS}) — собран {built}")
        return 3

    # дешёвая сверка списка документов (без загрузки самих страниц)
    try:
        live_paths, sections = crawl_doc_paths()
    except Exception as e:
        print(f"WARN: сверка списка не удалась ({e!r}); индексу {age} дн. — "
              f"ищу по текущему индексу")
        return 0
    live = {BASE + p for p in live_paths}
    have = set(re.findall(r"^- URL:\s*(\S+)", open(out_path, encoding="utf-8").read(), re.M))
    added, removed = live - have, have - live
    if added or removed:
        print(f"REBUILD: список изменился (+{len(added)} / -{len(removed)}), "
              f"разделов {len(sections)}")
        for u in sorted(added):
            print("   + " + u)
        for u in sorted(removed):
            print("   - " + u)
        return 3
    print(f"OK: индексу {age} дн. (собран {built}), документов {n_index}, "
          f"список совпадает ({len(live)})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="build", choices=["build", "check"],
                    help="build (по умолчанию) — собрать индекс; check — не пора ли пересобрать")
    ap.add_argument("--out", default=OUT_DEFAULT, help="путь к индексу")
    a = ap.parse_args()
    if a.mode == "check":
        raise SystemExit(check(a.out))
    build(a.out)
