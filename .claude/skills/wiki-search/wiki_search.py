# -*- coding: utf-8 -*-
"""Поиск ответа по корпоративной вики DataPeople с указанием источника.

    python wiki_search.py "как подключиться к Wi-Fi"
    python wiki_search.py "OKR на Q2" --top 3
    python wiki_search.py "..." --json          # машиночитаемый вывод
    python wiki_search.py "..." --no-refresh     # не трогать индекс
    python wiki_search.py "..." --check          # полная сверка свежести перед поиском

Логика свежести:
  • индекса нет            -> build
  • индексу больше TTL ч   -> refresh (сверка списков + перекачка изменённого)
  • --check                -> refresh всегда, если список доков разошёлся с сайтом
Результаты -> топ-N документов, для каждого: заголовок, ПОЛНЫЙ URL источника,
раздел/подраздел, дата «Обновлено», сниппет вокруг совпадения.
"""
import sys, re, json, argparse
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import wiki_common as C
import wiki_index as IDX

STOP = set("""и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по
только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если или
для это эта эти этот тем чем над без при про том тот там
какой какая какое какие каких каком какую есть быть нужно надо можно нельзя где куда
когда почему зачем чей чья кто кого кому чём чем сколько ли также этом нашем наш наша наше
the a an of to in is are for how what where when why which""".split())


def tokenize(s):
    toks = re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", (s or "").lower())
    return [t for t in toks if len(t) >= 2 and t not in STOP]


def ensure_fresh(no_refresh=False, full_check=False):
    """Проверить/обновить индекс перед поиском. Вернёт строку-статус.

    • индекса нет                 -> build
    • --no-refresh                -> ничего
    • --check                     -> полный refresh (перечитать все доки)
    • индексу больше TTL          -> полный refresh
    • иначе                       -> дешёвая сверка списка (7 запросов); если
                                     документы добавились/удалились -> refresh
    """
    docs = C.load_docs()
    if not docs:
        print("[индекс] не найден — собираю с нуля…", file=sys.stderr)
        IDX.build()
        return "индекс собран с нуля"
    if no_refresh:
        return "индекс не проверялся (--no-refresh)"

    age = C.index_age_hours()
    if full_check:
        print("[индекс] --check: полная перепроверка…", file=sys.stderr)
        IDX.refresh()
        return f"выполнен полный refresh (--check, индексу было {age:.1f} ч)"
    if age is not None and age > C.TTL_HOURS:
        print(f"[индекс] возраст {age:.1f} ч > TTL {C.TTL_HOURS} ч — refresh…", file=sys.stderr)
        IDX.refresh()
        return f"выполнен refresh (индексу было {age:.1f} ч)"

    add, rem = IDX.listing_diff()
    if add is None:
        return f"индекс возраст {age:.1f} ч; список на сайте сверить не удалось (сеть)"
    if add or rem:
        print(f"[индекс] на сайте +{len(add)}/-{len(rem)} документов — refresh…", file=sys.stderr)
        IDX.refresh()
        return f"выполнен refresh (на сайте добавилось {len(add)}, удалено {len(rem)})"
    return f"индекс свежий (возраст {age:.1f} ч, список совпадает)"


def _stem(t):
    """Грубая нормализация окончаний для русского: возвращает самый короткий
    вариант основы, по которому ищем вхождения (ловит падежи/число)."""
    if len(t) >= 7:
        return t[:-3]
    if len(t) >= 5:
        return t[:-2]
    return t


def score_doc(d, qtokens, qnorm):
    title = d["title"].lower()
    heads = " \n ".join(d.get("headings", [])).lower()
    body = d["text"].lower()
    present = 0
    s = 0
    for t in set(qtokens):
        st = _stem(t)
        # точное совпадение — полный вес; совпадение по основе — 0.6
        ct = title.count(t) + 0.6 * max(0, title.count(st) - title.count(t))
        ch = heads.count(t) + 0.6 * max(0, heads.count(st) - heads.count(t))
        cb = body.count(t) + 0.6 * max(0, body.count(st) - body.count(t))
        if ct or ch or cb:
            present += 1
        # слово в заголовке документа — сильный сигнал релевантности
        if ct:
            s += 12
        s += 8 * ct + 3 * ch + cb
    if s == 0:
        return 0.0, 0
    if qnorm and len(qnorm) >= 4:
        if qnorm in title:
            s += 25
        elif qnorm in body:
            s += 10
    coverage = present / max(1, len(set(qtokens)))
    return s * (0.35 + 0.65 * coverage), present


def best_snippet(d, qtokens, width=340):
    body = d["text"]
    low = body.lower()
    pos = -1
    for t in sorted(set(qtokens), key=len, reverse=True):
        p = low.find(t)
        if p != -1:
            pos = p
            break
    if pos == -1:
        pos = 0
    start = max(0, pos - width // 3)
    # к началу предложения/строки
    for b in ("\n", ". ", "! ", "? "):
        k = body.rfind(b, max(0, start - 120), pos)
        if k != -1:
            start = k + len(b)
            break
    end = min(len(body), start + width)
    k = body.find("\n", end - 60, end + 120)
    if k != -1:
        end = k
    snip = body[start:end].strip()
    snip = re.sub(r"\s*\n\s*", " / ", snip)
    return ("…" if start > 0 else "") + snip + ("…" if end < len(body) else "")


def nearest_heading(d, qtokens):
    body = d["text"]
    low = body.lower()
    pos = min((low.find(t) for t in set(qtokens) if low.find(t) != -1), default=-1)
    if pos == -1:
        return d.get("headings", [None])[0] if d.get("headings") else None
    best = None
    for h in d.get("headings", []):
        hp = low.find(h.lower())
        if hp != -1 and hp <= pos:
            best = h
    return best or (d.get("headings", [None])[0] if d.get("headings") else None)


def search(query, top=5):
    qtokens = tokenize(query)
    nterms = max(1, len(set(qtokens)))
    qnorm = " ".join(qtokens)
    docs = C.load_docs()
    scored = []
    for d in docs:
        sc, present = score_doc(d, qtokens, qnorm)
        if sc > 0:
            scored.append((sc, present, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for sc, present, d in scored[:top]:
        out.append({
            "score": round(sc, 1),
            "matched_terms": present,
            "query_terms": nterms,
            "title": d["title"],
            "source": d["url"],
            "section": d["section"],
            "updated": d.get("updated", ""),
            "author": d.get("author", ""),
            "heading": nearest_heading(d, qtokens),
            "snippet": best_snippet(d, qtokens),
        })
    # низкая уверенность: лучший результат покрывает < половины слов запроса и
    # при этом слабый по абсолютному счёту
    low_conf = bool(out) and (out[0]["matched_terms"] / nterms < 0.5) and out[0]["score"] < 22
    return qtokens, out, low_conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-refresh", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    fresh = ensure_fresh(no_refresh=a.no_refresh, full_check=a.check)
    qtokens, results, low_conf = search(a.query, top=a.top)

    if a.json:
        print(json.dumps({
            "query": a.query, "tokens": qtokens, "index_status": fresh,
            "count": len(results), "low_confidence": low_conf, "results": results,
        }, ensure_ascii=False, indent=1))
        return

    print(f"Запрос: {a.query}")
    print(f"Индекс: {fresh}")
    if not results:
        print("\nВ вики ничего подходящего не найдено. "
              "Попробуй переформулировать запрос или проверь раздел вручную: " + C.WIKI_ROOT)
        return
    if low_conf:
        print("\n⚠ НИЗКАЯ УВЕРЕННОСТЬ: ни один документ не покрывает запрос целиком — "
              "возможно, в вики этого нет. Проверь сниппеты; если не по теме — так и скажи пользователю.")
    print(f"\nНайдено документов: {len(results)}\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['title']}   (score {r['score']})")
        print(f"    Источник:  {r['source']}")
        meta = f"    Раздел: {r['section']}"
        if r["updated"]:
            meta += f"  ·  Обновлено: {r['updated']}"
        if r["author"]:
            meta += f"  ·  Автор: {r['author']}"
        print(meta)
        if r["heading"]:
            print(f"    Подраздел: «{r['heading']}»")
        print(f"    {r['snippet']}")
        print()


if __name__ == "__main__":
    main()
