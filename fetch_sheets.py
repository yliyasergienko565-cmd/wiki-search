# -*- coding: utf-8 -*-
"""/sheets-search helper — открыть выбранные таблицы менеджеров (по номеру из
sheets-sources.txt, по ссылке или по gid) и вывести их строки с готовым
источником на каждую строку в формате `…/edit?gid={GID}&range=A{N}:Z{N}`.

    python fetch_sheets.py 8                     # вся таблица 8
    python fetch_sheets.py 1 9 10               # таблицы 1, 9, 10
    python fetch_sheets.py 2 --filter Северсталь # только строки со словом
    python fetch_sheets.py <url|id>[#gid=123]   # по ссылке/id
    python fetch_sheets.py 1 --json

Доступ к таблицам «по ссылке», без OAuth. Только стандартная библиотека."""
import re, sys, json, argparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sheets_common import (
    read_sources, list_tabs, load_table, nonempty, sheet_id, source_ref,
)


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def resolve(sel, sources):
    """'8' | url | id | '...#gid=123' -> (n, sid, edit_url, gid_or_None)."""
    by_n = {n: (n, sid, url) for n, sid, url in sources}
    by_sid = {sid: (n, sid, url) for n, sid, url in sources}
    gid = None
    mg = re.search(r"[#?&]gid=(\d+)", sel)
    if mg:
        gid = mg.group(1)
        sel = sel[:mg.start()]
    if sel.isdigit() and int(sel) in by_n:
        n, sid, url = by_n[int(sel)]
    else:
        sid = sheet_id(sel)
        if sid in by_sid:
            n, sid, url = by_sid[sid]
        else:
            n, url = "?", f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    return n, sid, url, gid


def dump_tab(n, sid, edit_url, tab, gid, flt):
    rows = load_table(sid, gid)
    ne = nonempty(rows)
    header = ne[0]["cells"] if ne else []
    hrow = ne[0]["row"] if ne else 1
    result = {
        "table": n, "spreadsheet": edit_url, "tab": tab, "gid": gid,
        "header_row": hrow, "columns": header, "rows": [],
    }
    for r in ne[1:]:
        cells = r["cells"]
        if flt and not any(flt.lower() in c.lower() for c in cells):
            continue
        pairs = {header[i] if i < len(header) and header[i] else col_letter(i): c
                 for i, c in enumerate(cells) if c}
        result["rows"].append({
            "row": r["row"], "values": pairs,
            "source": source_ref(sid, gid, r["row"]),
        })
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("selectors", nargs="+")
    ap.add_argument("--filter", default=None, help="показать только строки с этой подстрокой")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    sources = read_sources()
    out = []
    for sel in a.selectors:
        n, sid, edit_url, gid = resolve(sel, sources)
        tabs = [(None, gid)] if gid else list_tabs(sid)
        for tab, g in tabs:
            try:
                out.append(dump_tab(n, sid, edit_url, tab, g, a.filter))
            except Exception as e:
                out.append({"table": n, "spreadsheet": edit_url, "tab": tab,
                            "gid": g, "error": repr(e)})

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    for t in out:
        print("=" * 72)
        print(f"Таблица {t['table']} — {t['spreadsheet']}")
        if "error" in t:
            print("ОШИБКА:", t["error"])
            print()
            continue
        print(f"Вкладка: {t['tab']} · gid={t['gid']}")
        cols = " | ".join(f"{col_letter(i)}={h}" for i, h in enumerate(t["columns"]) if h)
        print(f"Колонки (строка {t['header_row']}): {cols}")
        print("-" * 72)
        if not t["rows"]:
            print("(строк не найдено" + (f" по фильтру «{a.filter}»" if a.filter else "") + ")")
        for r in t["rows"]:
            vals = "; ".join(f"{k}: {v}" for k, v in r["values"].items())
            print(f"[строка {r['row']}] {vals}")
            print(f"    источник: {r['source']}")
        print()


if __name__ == "__main__":
    main()
