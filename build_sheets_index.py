# -*- coding: utf-8 -*-
"""/index-sheets — пройти по таблицам менеджеров (список в sheets-sources.txt) и
собрать один файл `sheets-index.md` в корне репозитория: карточка на каждую
таблицу (менеджер, вкладка+gid, колонки, число строк, про что данные, какие
стадии, список компаний).

    python build_sheets_index.py            # собрать/пересобрать sheets-index.md
    python build_sheets_index.py build      # то же явно
    python build_sheets_index.py check      # не пора ли пересобрать? (для /sheets-search)

Когда индекс считается устаревшим (`check`):
  1. файла нет / не читается шапка                       -> REBUILD
  2. индексу больше MAX_AGE_DAYS (14) дней               -> REBUILD
  3. изменился список таблиц в sheets-sources.txt        -> REBUILD
  4. у какой-то таблицы изменился набор вкладок (gid)    -> REBUILD
  5. сеть не дала проверить пп.3-4, но индекс не стар    -> WARN (ищем по текущему)
  6. иначе                                               -> OK

Коды выхода: 0 — можно искать (OK/WARN), 3 — нужна пересборка (REBUILD).
Только стандартная библиотека, доступ к таблицам «по ссылке» без OAuth."""
import os, re, sys, argparse, datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sheets_common import (
    INDEX_PATH, read_sources, list_tabs, load_table, nonempty,
)

MAX_AGE_DAYS = 14

# префикс имени вкладки -> имя менеджера
MANAGER_BY_PREFIX = {
    "anna": "Анна", "artem": "Артём", "dasha": "Даша", "katya": "Катя",
    "ksenia": "Ксения", "lena": "Лена", "nikita": "Никита", "oleg": "Олег",
    "petrov": "Пётр Петров", "petr": "Пётр Петров", "ruslan": "Руслан",
}
NAME_COLS = ("компания", "клиент", "организация", "название", "предприятие",
             "лид", "компания/лид")
STAGE_COLS = ("этап", "стадия", "статус", "статус сделки", "этап воронки",
              "квалификация", "итог")
MANAGER_COLS = ("менеджер", "ответственный", "owner")


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _pick_col(header, names):
    low = [h.lower().strip() for h in header]
    for i, h in enumerate(low):
        if h in names:
            return i
    for i, h in enumerate(low):
        if any(h.startswith(n) or n in h for n in names):
            return i
    return None


def _distinct(values, cap=14):
    seen, out = set(), []
    for v in values:
        v = _norm(v)
        k = v.lower()
        if v and k not in seen:
            seen.add(k)
            out.append(v)
        if len(out) >= cap:
            break
    return out


def manager_label(tab_name, header, data_rows):
    """-> (короткая метка для заголовка, подробность для «О чём», is_master)."""
    mi = _pick_col(header, MANAGER_COLS)
    if mi is not None:
        vals = _distinct([r["cells"][mi] for r in data_rows if len(r["cells"]) > mi], cap=12)
        if vals:
            return ("общий пайплайн (все менеджеры)",
                    "Менеджеры в таблице: " + ", ".join(vals) + ".", True)
    pref = re.split(r"[-_]", tab_name.lower())[0]
    name = MANAGER_BY_PREFIX.get(pref)
    if name:
        return name, f"Менеджер — {name} (по имени вкладки «{tab_name}»).", False
    return f"вкладка «{tab_name}»", "Менеджер в данных не указан.", False


def describe(tab_name, header, data_rows):
    data = [r for r in data_rows if any(c for c in r["cells"])]
    short, detail, is_master = manager_label(tab_name, header, data)

    ni = _pick_col(header, NAME_COLS)
    si = _pick_col(header, STAGE_COLS)

    companies = _distinct([r["cells"][ni] for r in data if len(r["cells"]) > ni]) if ni is not None else []
    stages = _distinct([r["cells"][si] for r in data if len(r["cells"]) > si], cap=12) if si is not None else []

    kind = ("Свод сделок всех менеджеров" if is_master
            else "Личная таблица менеджера")
    about = f"{detail} {kind}, строк данных: {len(data)}."
    if stages:
        about += " Стадии в колонке «%s»: %s." % (header[si], ", ".join(stages))
    return {
        "manager": short, "about": about,
        "columns": [h for h in header if _norm(h)],
        "n_data": len(data),
        "companies": companies,
        "stage_col": header[si] if si is not None else None,
    }


def build(out_path):
    sources = read_sources()
    print(f"Таблиц в sheets-sources.txt: {len(sources)}")
    cards = []
    for n, sid, edit_url in sources:
        tabs = list_tabs(sid)
        if not tabs:
            print(f"  ! Таблица {n} ({sid}): не удалось получить вкладки")
            continue
        for tab_name, gid in tabs:
            rows = load_table(sid, gid)
            ne = nonempty(rows)
            header = ne[0]["cells"] if ne else []
            data_rows = ne[1:] if ne else []
            info = describe(tab_name, header, data_rows)
            cards.append({
                "n": n, "sid": sid, "edit_url": edit_url,
                "tab": tab_name, "gid": gid,
                "header_row": ne[0]["row"] if ne else 1,
                "first_data_row": data_rows[0]["row"] if data_rows else None,
                "last_data_row": data_rows[-1]["row"] if data_rows else None,
                **info,
            })
            print(f"  Таблица {n}: вкладка «{tab_name}» gid={gid}, {info['n_data']} строк")

    lines = [
        "# Индекс таблиц менеджеров",
        "",
        f"Собрано: {datetime.date.today().isoformat()} · таблиц: {len(sources)} · "
        f"карточек (вкладок): {len(cards)}",
        "",
        "Файл генерируется скриптом `build_sheets_index.py` (скилл `/index-sheets`). "
        "Вручную не редактировать — перезапусти `/index-sheets`.",
        "",
        "`/sheets-search` читает только этот файл, выбирает по описаниям 2-3 таблицы "
        "и открывает лишь их (`fetch_sheets.py`). Источник в ответе — "
        "`…/edit?gid={GID}&range=A{N}:Z{N}`.",
        "",
    ]
    for c in cards:
        lines.append(f"## Таблица {c['n']} — {c['manager']}")
        lines.append(f"- Таблица: {c['edit_url']}")
        rng = ""
        if c["first_data_row"]:
            rng = f" · строки данных {c['first_data_row']}–{c['last_data_row']}"
        lines.append(f"- Вкладка: {c['tab']} · gid={c['gid']}{rng}")
        lines.append(f"- Колонки: {' | '.join(c['columns'])}")
        lines.append(f"- О чём: {c['about']}")
        if c["companies"]:
            more = "; …" if len(c["companies"]) >= 14 else ""
            lines.append(f"- Компании/лиды: {'; '.join(c['companies'])}{more}")
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nЗаписано: {out_path}  ({len(cards)} карточек, {len(text)} байт)")


def check(out_path):
    if not os.path.exists(out_path):
        print("REBUILD: индекса нет —", out_path)
        return 3
    head = open(out_path, encoding="utf-8").read(4000)
    md = re.search(r"Собрано:\s*(\d{4}-\d{2}-\d{2}).*?таблиц:\s*(\d+)", head, re.S)
    if not md:
        print("REBUILD: не читается шапка индекса")
        return 3
    built = datetime.date.fromisoformat(md.group(1))
    n_index = int(md.group(2))
    age = (datetime.date.today() - built).days
    if age > MAX_AGE_DAYS:
        print(f"REBUILD: индексу {age} дн. (> {MAX_AGE_DAYS}) — собран {built}")
        return 3

    full = open(out_path, encoding="utf-8").read()
    have_gids = set(re.findall(r"gid=(\d+)", full))
    try:
        sources = read_sources()
        if len(sources) != n_index:
            print(f"REBUILD: список таблиц изменился ({n_index} -> {len(sources)})")
            return 3
        live_gids = set()
        for n, sid, _ in sources:
            for _, gid in list_tabs(sid):
                live_gids.add(gid)
    except Exception as e:
        print(f"WARN: проверка таблиц не удалась ({e!r}); индексу {age} дн. — "
              f"ищу по текущему индексу")
        return 0
    if live_gids != have_gids:
        add, rem = live_gids - have_gids, have_gids - live_gids
        print(f"REBUILD: набор вкладок изменился (+{len(add)} / -{len(rem)})")
        return 3
    print(f"OK: индексу {age} дн. (собран {built}), таблиц {n_index}, "
          f"вкладки совпадают ({len(have_gids)})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="build", choices=["build", "check"])
    ap.add_argument("--out", default=INDEX_PATH)
    a = ap.parse_args()
    if a.mode == "check":
        raise SystemExit(check(a.out))
    build(a.out)
