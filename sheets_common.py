# -*- coding: utf-8 -*-
"""Общие хелперы для скиллов /index-sheets и /sheets-search: чтение
Google-таблиц менеджеров через публичный CSV-экспорт (доступ «по ссылке»,
без OAuth). Только стандартная библиотека."""
import os, re, io, csv, time, random, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(HERE, "sheets-sources.txt")
INDEX_PATH = os.path.join(HERE, "sheets-index.md")
WORKERS = 8
UA = "sheets-search-skill/1.0 (+ailearning course)"

_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.status


def fetch_many(urls, workers=WORKERS):
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


def sheet_id(url_or_id):
    m = _ID_RE.search(url_or_id)
    return m.group(1) if m else url_or_id.strip()


def read_sources(path=SOURCES_PATH):
    """sheets-sources.txt -> [(n, spreadsheet_id, edit_url)] по порядку."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sid = sheet_id(line)
            out.append((len(out) + 1, sid, f"https://docs.google.com/spreadsheets/d/{sid}/edit"))
    return out


def list_tabs(spreadsheet_id):
    """-> [(tab_name, gid)] через /htmlview (без OAuth)."""
    html, _ = fetch(f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/htmlview")
    tabs = re.findall(r'items\.push\(\{name:\s*"((?:[^"\\]|\\.)*)"[^}]*?gid:\s*"(\d+)"', html)
    seen, out = set(), []
    for name, gid in tabs:
        if gid in seen:
            continue
        seen.add(gid)
        out.append((name.encode().decode("unicode_escape") if "\\" in name else name, gid))
    return out


def csv_url(spreadsheet_id, gid):
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def parse_csv(text):
    """CSV -> список строк; каждая строка = dict(row=<1-based номер в таблице>,
    cells=[...]). Пустые строки сохраняются (нумерация не сбивается)."""
    rows = []
    for i, cells in enumerate(csv.reader(io.StringIO(text)), start=1):
        rows.append({"row": i, "cells": [c.strip() for c in cells]})
    return rows


def nonempty(rows):
    return [r for r in rows if any(c for c in r["cells"])]


def source_ref(spreadsheet_id, gid, row, last_col="Z"):
    """Ссылка-источник в требуемом формате ?gid={GID}&range=A{N}:Z{N}."""
    return (f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            f"/edit?gid={gid}&range=A{row}:{last_col}{row}")


def load_table(spreadsheet_id, gid):
    text, status = fetch(csv_url(spreadsheet_id, gid))
    if status != 200:
        raise RuntimeError(f"HTTP {status}")
    return parse_csv(text)
