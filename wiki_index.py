# -*- coding: utf-8 -*-
"""Индексатор корпоративной вики DataPeople (https://agentsim.online/wiki/).

Команды:
    python wiki_index.py build     — полный краул, пересобрать индекс с нуля
    python wiki_index.py refresh   — инкрементально: добавить новые доки, убрать
                                     удалённые, перекачать изменённые (по дате
                                     «Обновлено» и хэшу содержимого)
    python wiki_index.py status    — состояние индекса и нужен ли refresh

Индекс: index/docs.jsonl (по строке на документ) + index/meta.json.
Загрузка страниц параллельная (WORKERS потоков) — полный краул ~5-10 сек.
"""
import sys, json
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import wiki_common as C


def _crawl_doc_paths():
    """корень -> разделы -> список путей всех документов. -> (paths, sections)."""
    root_html, _ = C.fetch(C.WIKI_ROOT)
    sections = C.discover_sections(root_html)
    if not sections:
        raise SystemExit("Не нашёл ни одного раздела на " + C.WIKI_ROOT)
    sec_pages = C.fetch_many([f"{C.BASE}/wiki/{s}" for s in sections])
    paths = set()
    for s in sections:
        res = sec_pages.get(f"{C.BASE}/wiki/{s}")
        if not res or res[0] == "__ERR__":
            print(f"  ! раздел {s}: {res[1] if res else 'нет ответа'}")
            continue
        for p in C.discover_docs(res[0], section=s):
            paths.add(p)
    return sorted(paths), sections


def _fetch_docs(paths):
    """Параллельно скачать и распарсить документы. -> (list[doc], list[(path,err)])."""
    res = C.fetch_many([C.BASE + p for p in paths])
    docs, errors = [], []
    for p in paths:
        r = res.get(C.BASE + p)
        if not r or r[0] == "__ERR__":
            errors.append((p, r[1] if r else "нет ответа"))
            continue
        try:
            docs.append(C.parse_doc(r[0], p))
        except Exception as e:
            errors.append((p, repr(e)))
    return docs, errors


def build():
    paths, sections = _crawl_doc_paths()
    print(f"Разделов: {len(sections)}  •  документов найдено: {len(paths)}  •  качаю…")
    docs, errors = _fetch_docs(paths)
    C.save_docs(docs)
    C.save_meta({
        "base": C.WIKI_ROOT,
        "built_at": C.now_iso(), "refreshed_at": C.now_iso(),
        "doc_count": len(docs), "sections": sections,
        "ttl_hours": C.TTL_HOURS, "errors": errors,
    })
    _by_section(docs)
    _print_summary(docs, errors)


def refresh():
    old = {d["path"]: d for d in C.load_docs()}
    if not old:
        print("Индекс пуст — делаю build.")
        return build()

    paths, sections = _crawl_doc_paths()
    cur, prev = set(paths), set(old)
    added, removed = sorted(cur - prev), sorted(prev - cur)
    common = sorted(cur & prev)

    fresh, errors = _fetch_docs(common + added)
    fresh_by_path = {d["path"]: d for d in fresh}

    docs, changed, unchanged = [], [], 0
    for path in common:
        d = fresh_by_path.get(path)
        if d is None:                       # не скачался — оставляем старую версию
            docs.append(old[path]); continue
        o = old[path]
        if d["sha"] != o["sha"] or d["updated"] != o.get("updated"):
            changed.append((path, o.get("updated"), d["updated"]))
            docs.append(d)
        else:
            unchanged += 1
            docs.append(o)
    for path in added:
        if path in fresh_by_path:
            docs.append(fresh_by_path[path])

    C.save_docs(docs)
    meta = C.load_meta()
    meta.update({"refreshed_at": C.now_iso(), "doc_count": len(docs),
                 "sections": sections, "ttl_hours": C.TTL_HOURS, "errors": errors})
    meta.setdefault("built_at", C.now_iso())
    C.save_meta(meta)

    print("\n=== refresh ===")
    print(f"  новых:        {len(added)}   " + ", ".join(p.split('/')[-1] for p in added))
    print(f"  удалённых:    {len(removed)}   " + ", ".join(p.split('/')[-1] for p in removed))
    print(f"  изменённых:   {len(changed)}")
    for path, o, n in changed:
        print(f"     ~ {path.split('/')[-1]}: «Обновлено» {o} -> {n}")
    print(f"  без изменений: {unchanged}")
    if errors:
        print(f"  ошибок: {len(errors)}  " + ", ".join(p.split('/')[-1] for p, _ in errors[:8]))
    _by_section(docs)
    _print_summary(docs, errors)


def listing_diff():
    """Дёшево (7 запросов): расходится ли список документов на сайте с индексом.
    -> (set_добавленных_путей, set_удалённых_путей) или (None, None) при ошибке."""
    try:
        paths, _ = _crawl_doc_paths()
    except Exception:
        return None, None
    have = {d["path"] for d in C.load_docs()}
    cur = set(paths)
    return cur - have, have - cur


def status():
    docs = C.load_docs()
    meta = C.load_meta()
    if not docs:
        print("Индекс не создан. Запусти:  python wiki_index.py build")
        return
    age = C.index_age_hours()
    print(f"Документов в индексе: {len(docs)}")
    print(f"Собран:   {meta.get('built_at','?')}")
    if age is not None:
        print(f"Обновлён: {meta.get('refreshed_at','?')}  ({age:.1f} ч назад, TTL {C.TTL_HOURS} ч)")
    _by_section(docs)

    stale_ttl = age is not None and age > C.TTL_HOURS
    add, rem = listing_diff()
    print()
    if stale_ttl:
        print(f"→ индексу больше TTL — рекомендуется:  python wiki_index.py refresh")
    if add or rem:
        print(f"→ список на сайте изменился: +{len(add or [])} / -{len(rem or [])} — нужен refresh")
        for p in sorted(add or []):
            print(f"     новый:    {p}")
        for p in sorted(rem or []):
            print(f"     удалён:   {p}")
    if add is None:
        print("→ не удалось проверить список разделов (сеть).")
    if not stale_ttl and not add and not rem and add is not None:
        print("→ индекс актуален.")


def _by_section(docs):
    c = {}
    for d in docs:
        c[d["section"]] = c.get(d["section"], 0) + 1
    print("По разделам: " + ", ".join(f"{k}:{v}" for k, v in sorted(c.items())))


def _print_summary(docs, errors):
    print(f"\nГотово: {len(docs)} документов в {C.DOCS_PATH}")
    if errors:
        print(f"Ошибок при загрузке: {len(errors)}")
        for p, e in errors[:10]:
            print(f"   {p}: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"build": build, "refresh": refresh, "status": status}.get(cmd, status)()
