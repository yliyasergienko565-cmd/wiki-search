# -*- coding: utf-8 -*-
"""Общие хелперы: загрузка страниц корпоративной вики DataPeople и их парсинг.
Используется обоими скиллами — /index-wiki (build_wiki_index.py) и
/wiki-search (fetch_pages.py). Только стандартная библиотека."""
import re, time, html, random, datetime, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = "https://agentsim.online"
WIKI_ROOT = BASE + "/wiki/"
WORKERS = 8
UA = "wiki-search-skill/2.0 (+ailearning course)"

SECTION_SKIP = {"sections", "pages"}
DOC_SKIP_SLUGS = {"pages", "sections"}


def fetch(url, timeout=30):
    """GET -> (html_text, http_status). Бросает при сетевой ошибке."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
        return raw.decode(enc, "replace"), r.status


def fetch_many(urls, workers=WORKERS):
    """Параллельно загрузить список URL. -> {url: (html, status)} для успешных,
    {url: ("__ERR__", "текст ошибки")} для упавших."""
    out = {}

    def _one(u):
        time.sleep(random.uniform(0, 0.08))
        try:
            return u, fetch(u)
        except Exception as e:
            return u, ("__ERR__", repr(e))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for u, res in ex.map(_one, list(urls)):
            out[u] = res
    return out


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def discover_sections(root_html):
    out = []
    for seg in re.findall(r'href="/wiki/([a-z0-9-]+)"', root_html):
        if seg not in SECTION_SKIP and seg not in out:
            out.append(seg)
    return out


def discover_docs(page_html, section=None):
    """Ссылки вида /wiki/<section>/<slug> на странице (без служебных списков)."""
    urls = set()
    for m in re.findall(r'href="(/wiki/[a-z0-9-]+/[a-z0-9-]+)"', page_html):
        if m.rsplit("/", 1)[-1] in DOC_SKIP_SLUGS:
            continue
        urls.add(m)
    if section:
        urls = {u for u in urls if u.startswith(f"/wiki/{section}/")}
    return sorted(urls)


def parse_doc(doc_html, path):
    """HTML страницы -> dict(url, path, section, slug, title, author, created,
    updated, headings, lead, text)."""
    section, slug = path.rstrip("/").split("/")[-2:]

    m = re.search(r'<div class="wiki-content">(.*?)</div>', doc_html, re.S)
    content = m.group(1) if m else doc_html

    mt = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.S)
    title = _clean(mt.group(1)) if mt else slug.replace("-", " ")

    def meta(label):
        mm = re.search(re.escape(label) + r"</span>\s*([^<]+)", doc_html)
        return mm.group(1).strip() if mm else ""

    author = meta("Автор:")
    created = meta("Создано:")
    updated = meta("Обновлено:") or created

    headings = [_clean(h) for lvl, h in re.findall(r"<h([2-4])[^>]*>(.*?)</h\1>", content, re.S)]

    # тело после h1
    body_html = content[mt.end():] if mt else content
    # первый абзац (до первого подзаголовка / <hr>) — для краткого «о чём»
    lead_html = re.split(r"<h[2-4][^>]*>|<hr\s*/?>", body_html, maxsplit=1)[0]
    lead = _clean(lead_html)

    body = re.sub(r"</(p|div|li|h[1-6]|tr|blockquote)>", "\n", body_html, flags=re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"<hr\s*/?>", "\n", body, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", body))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()

    return {
        "url": BASE + path, "path": path, "section": section, "slug": slug,
        "title": title, "author": author, "created": created, "updated": updated,
        "headings": headings, "lead": lead, "text": text,
    }


def crawl_doc_paths():
    """корень -> разделы -> все пути документов. -> (paths, sections)."""
    root_html, _ = fetch(WIKI_ROOT)
    sections = discover_sections(root_html)
    if not sections:
        raise SystemExit("Не нашёл ни одного раздела на " + WIKI_ROOT)
    sec_pages = fetch_many([f"{BASE}/wiki/{s}" for s in sections])
    paths = set()
    for s in sections:
        res = sec_pages.get(f"{BASE}/wiki/{s}")
        if not res or res[0] == "__ERR__":
            print(f"  ! раздел {s}: {res[1] if res else 'нет ответа'}")
            continue
        for p in discover_docs(res[0], section=s):
            paths.add(p)
    return sorted(paths), sections


def now_date():
    return datetime.date.today().isoformat()
