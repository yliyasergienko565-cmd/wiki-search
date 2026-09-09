# -*- coding: utf-8 -*-
"""Общие хелперы для /wiki-search: загрузка страниц, парсинг вики DataPeople,
чтение/запись индекса. Только stdlib."""
import os, re, json, time, html, hashlib, random, urllib.request, urllib.error, datetime
from concurrent.futures import ThreadPoolExecutor

BASE = "https://agentsim.online"
WIKI_ROOT = BASE + "/wiki/"
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(HERE, "index")
DOCS_PATH = os.path.join(INDEX_DIR, "docs.jsonl")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

TTL_HOURS = 6          # индекс старше — рекомендуем refresh
WORKERS = 8            # параллельных загрузок при краул/refresh
UA = "wiki-search-skill/1.0 (+ailearning course)"

SECTION_SKIP = {"sections", "pages"}


def fetch(url, timeout=30):
    """GET -> (html_text, http_status). Бросает при сетевой ошибке."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
        return raw.decode(enc, "replace"), r.status


def fetch_many(urls, workers=WORKERS):
    """Параллельно загрузить список URL. Возвращает {url: (html, status)} для
    успешных и {url: ("__ERR__", "текст ошибки")} для упавших."""
    out = {}

    def _one(u):
        time.sleep(random.uniform(0, 0.08))   # лёгкий джиттер, чтобы не бить залпом
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


DOC_SKIP_SLUGS = {"pages", "sections"}


def discover_docs(page_html, section=None):
    """Все ссылки вида /wiki/<section>/<slug> на странице (без служебных
    страниц-списков вроде /wiki/<section>/pages)."""
    urls = set()
    for m in re.findall(r'href="(/wiki/[a-z0-9-]+/[a-z0-9-]+)"', page_html):
        if m.rsplit("/", 1)[-1] in DOC_SKIP_SLUGS:
            continue
        urls.add(m)
    if section:
        urls = {u for u in urls if u.startswith(f"/wiki/{section}/")}
    return sorted(urls)


def parse_doc(doc_html, url):
    """HTML страницы дока -> dict(url, section, slug, title, author, created,
    updated, headings, text, sha)."""
    section, slug = url.rstrip("/").split("/")[-2:]

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

    body = content
    if mt:
        body = body[mt.end():]
    body = re.sub(r"</(p|div|li|h[1-6]|tr|blockquote)>", "\n", body, flags=re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"<hr\s*/?>", "\n", body, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", body))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()

    sha = hashlib.sha1((title + "\n" + text).encode("utf-8")).hexdigest()
    return {
        "url": BASE + url, "path": url, "section": section, "slug": slug,
        "title": title, "author": author, "created": created, "updated": updated,
        "headings": headings, "text": text, "sha": sha,
    }


# ---------- индекс ----------

def load_docs():
    if not os.path.exists(DOCS_PATH):
        return []
    out = []
    with open(DOCS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def save_docs(docs):
    os.makedirs(INDEX_DIR, exist_ok=True)
    docs = sorted(docs, key=lambda d: d["path"])
    with open(DOCS_PATH, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_meta():
    if not os.path.exists(META_PATH):
        return {}
    return json.load(open(META_PATH, encoding="utf-8"))


def save_meta(m):
    os.makedirs(INDEX_DIR, exist_ok=True)
    json.dump(m, open(META_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def index_age_hours():
    m = load_meta()
    ts = m.get("built_at") or m.get("refreshed_at")
    if not ts:
        return None
    try:
        dt = datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None
    return (datetime.datetime.now() - dt).total_seconds() / 3600.0
