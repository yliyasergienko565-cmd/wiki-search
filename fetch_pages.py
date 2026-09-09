# -*- coding: utf-8 -*-
"""/wiki-search helper — открыть 2-3 конкретные страницы вики DataPeople,
которые /wiki-search выбрал по `wiki-index.md`, и вывести их чистым текстом
с обязательной строкой `Источник:` (полный URL).

    python fetch_pages.py <url1> [<url2> <url3>] [--json]

Принимает только ссылки на https://agentsim.online/wiki/<раздел>/<слаг>."""
import re, sys, json, argparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from wiki_common import BASE, fetch, parse_doc

DOC_RE = re.compile(r"^https?://agentsim\.online(/wiki/[a-z0-9-]+/[a-z0-9-]+)/?$", re.I)


def normalize(url):
    m = DOC_RE.match(url.strip())
    if not m:
        return None
    return m.group(1)


def one(url):
    path = normalize(url)
    if not path:
        return {"url": url, "error": "не ссылка на документ вики "
                "(нужен вид https://agentsim.online/wiki/<раздел>/<слаг>)"}
    try:
        html_text, status = fetch(BASE + path)
    except Exception as e:
        return {"url": BASE + path, "error": f"не загрузилось: {e!r}"}
    if status != 200:
        return {"url": BASE + path, "error": f"HTTP {status}"}
    d = parse_doc(html_text, path)
    return {
        "url": d["url"], "title": d["title"], "section": d["section"],
        "updated": d["updated"], "author": d["author"],
        "headings": d["headings"], "text": d["text"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    results = [one(u) for u in a.urls]

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for r in results:
        print("=" * 70)
        if "error" in r:
            print(f"Источник: {r['url']}")
            print(f"ОШИБКА: {r['error']}")
            print()
            continue
        print(f"Источник: {r['url']}")
        head = f"Заголовок: {r['title']} · Раздел: {r['section']}"
        if r["updated"]:
            head += f" · Обновлено: {r['updated']}"
        if r["author"]:
            head += f" · Автор: {r['author']}"
        print(head)
        print("-" * 70)
        print(r["text"])
        print()


if __name__ == "__main__":
    main()
