#!/usr/bin/env python3
"""Данные для дашборда AI Executive Team — без ИИ, только из файлов репозитория.

Собирает JSON-таблицы, которые показывает дашборд (Claude Artifact):
  portfolio.json  — продукты из реестра и ключевые поля карточек
  feed.json       — лента: отчёты, материалы к решениям, аудиты, задания для сессий, решения собственника
  tasks.json      — управленческие задачи (tasks/)
  approvals.json  — карточки согласования (approvals/)
  questions.json  — открытые вопросы к собственнику из материалов к решениям
  handoff.json    — реестр заданий для сессий продуктов (handoff/README.md)
  activity.json   — журнал действий агентов по дням (logs/actions.jsonl)

Источник правды — репозиторий; дашборд только показывает. Ссылки ведут на файлы в GitHub.
Запуск:  python3 tools/build_dashboard_data.py --out <папка> [--ref main]
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://github.com/dkuplevatskij/AI-Executive-Team"


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def link(ref, path):
    return "%s/blob/%s/%s" % (REPO_URL, ref, path)


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    data = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.split("#")[0].strip()
    return data


def first_heading(text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def plain(md, limit=320, lists=True):
    """Markdown → одна строка простого текста для ленты (без разметки, обрезано по слову)."""
    t = re.sub(r"`([^`]*)`", r"\1", md)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    # Убираем только маркеры списков и цитат; цифры в начале («0 ₽», «3 задачи») — данные, их не трогаем.
    if lists:
        t = re.sub(r"^\s*(?:[>\-\*]|\d+\.)\s+", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t


def section(text, names):
    """Текст первого раздела «## …», чьё название начинается с одного из names."""
    for name in names:
        m = re.search(r"^##\s+(?:\d+\.\s*)?%s[^\n]*\n(.*?)(?=^##\s|\Z)" % re.escape(name), text, re.M | re.S)
        if m and m.group(1).strip():
            return m.group(1)
    return ""


def author(text, default):
    m = re.search(r"Подготовил:\s*([^·\n]+)", text)
    who = m.group(1).strip() if m else default
    m = re.search(r"Участники:\s*([^·\n]+)", text)
    if m:
        who += " · " + m.group(1).strip()
    return who


def date_of(path, text):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path)) or re.search(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else ""


def build_portfolio(ref, handoff_counts):
    import yaml
    reg = yaml.safe_load(read("portfolio/registry.yaml"))["products"]
    rows = []
    for p in reg:
        fields = {}
        card_path = p["card"]
        if os.path.exists(os.path.join(ROOT, card_path)):
            for line in read(card_path).splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 3 and cells[0].isdigit():
                    fields[int(cells[0])] = cells[2]
        rows.append({
            "product": p["name"],
            "status": p["status"],
            "launched": "да" if p.get("launched") else "нет",
            "revenue": plain(fields.get(11, "Не заполнено"), 60, lists=False),
            "paying": plain(fields.get(15, "Не заполнено"), 60, lists=False),
            "handoff": handoff_counts.get(p["id"], 0),
            "card": link(ref, card_path),
        })
    return rows


def build_handoff(ref):
    import yaml
    names = {p["id"]: p["name"] for p in yaml.safe_load(read("portfolio/registry.yaml"))["products"]}
    rows, counts = [], {}
    text = read("handoff/README.md")
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[1].startswith("`") and cells[2].isdigit():
            path = "handoff/" + cells[1].strip("`")
            pid = cells[1].strip("`").split("/")[0]
            counts[pid] = counts.get(pid, 0) + int(cells[2])  # у продукта может быть несколько файлов заданий
            # group — продукт из реестра (для графика по продуктам); общие задания — «Общее».
            rows.append({"product": cells[0], "group": names.get(pid, "Общее"), "tasks": int(cells[2]),
                         "created": cells[3], "sent": cells[4], "done": cells[5], "link": link(ref, path)})
    return rows, counts


def build_feed(ref):
    rows = []

    def add(path, kind, default_author, summary_sections):
        text = read(path)
        title = first_heading(text)
        summary = plain(section(text, summary_sections)) or plain(text.split("\n", 3)[-1])
        rows.append({"date": date_of(path, text), "kind": kind, "title": title,
                     "author": author(text, default_author), "summary": summary,
                     "link": link(ref, path)})

    for p in sorted(glob.glob(os.path.join(ROOT, "reports", "**", "*.md"), recursive=True)):
        rel = os.path.relpath(p, ROOT)
        kind = "Материал к решению" if "/decisions/" in rel else "Отчёт"
        add(rel, kind, "AI CEO", ["Краткое резюме", "Резюме", "Проблема"])
    for p in sorted(glob.glob(os.path.join(ROOT, "audit", "*", "00-*.md"))):
        add(os.path.relpath(p, ROOT), "Аудит", "AI CEO", ["Краткое резюме"])
    for p in sorted(glob.glob(os.path.join(ROOT, "handoff", "*", "*.md"))):
        rel = os.path.relpath(p, ROOT)
        text = read(rel)
        tasks = re.findall(r"^###\s+([A-Z]+-\d+)\.\s+(.+)$", text, re.M)
        rows.append({"date": date_of(rel, text), "kind": "Задание для сессии",
                     "title": first_heading(text).replace("Задания для сессии разработки: ", "Задания: "),
                     "author": "AI CEO · CTO",
                     "summary": plain("%d задач. Первая: %s" % (len(tasks), tasks[0][1] if tasks else "—")),
                     "link": link(ref, rel)})
    # Решения собственника — по записи журнала.
    log = read("company/decisions/log.md")
    for m in re.finditer(r"^\*\*(D-\d+)\s*·\s*(\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\*\*\n(.*?)(?=^\*\*D-|\Z)", log, re.M | re.S):
        rows.append({"date": m.group(2), "kind": "Решение собственника", "seq": int(m.group(1)[2:]),
                     "title": "%s. %s" % (m.group(1), m.group(3)),
                     "author": "собственник", "summary": plain(m.group(4)),
                     "link": link(ref, "company/decisions/log.md")})
    order = {"Решение собственника": 0, "Материал к решению": 1, "Отчёт": 2, "Аудит": 3, "Задание для сессии": 4}
    # Сначала свежие даты; внутри дня — решения собственника (новые выше), затем материалы, отчёты, аудиты, задания.
    rows.sort(key=lambda r: (r["date"], -order.get(r["kind"], 9), r.get("seq", 0)), reverse=True)
    for i, r in enumerate(rows):
        r["n"] = i + 1
        r.pop("seq", None)
    return rows


def build_questions(ref):
    """Открытые вопросы к собственнику — пункты раздела «Что нужно от собственника» материалов к решениям.

    Пункт с пометкой «[решено: …]» уже закрыт и не показывается.
    """
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "reports", "decisions", "*.md"))):
        rel = os.path.relpath(p, ROOT)
        text = read(rel)
        body = section(text, ["Что нужно от собственника"])
        topic = re.sub(r"^Решение:\s*", "", first_heading(text))
        for num, item in re.findall(r"^(\d+)\.\s+(.+?)(?=^\d+\.\s|\Z)", body, re.M | re.S):
            if "[решено" in item:
                continue
            m = re.match(r"\*\*([^*]+?):?\*\*:?\s*(.*)", item.strip(), re.S)
            head, rest = (m.group(1).rstrip(":"), m.group(2)) if m else ("", item)
            rows.append({"id": "%s-%s" % (os.path.basename(p)[:-3], num), "date": date_of(rel, text),
                         "topic": topic, "head": plain(head, 80), "question": plain(rest, 260),
                         "link": link(ref, rel)})
    return rows


def build_tasks(ref):
    rows, today = [], datetime.date.today().isoformat()
    for p in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "T-*.md"))):
        rel = os.path.relpath(p, ROOT)
        text = read(rel)
        fm = frontmatter(text)
        status = fm.get("status", rel.split("/")[1])
        due = fm.get("due", "")
        rows.append({"id": fm.get("id", os.path.basename(p)[:13]), "title": first_heading(text),
                     "owner": fm.get("owner", ""), "due": due, "status": status,
                     "overdue": "да" if (due[:4].isdigit() and due < today and status != "completed") else "нет",
                     "link": link(ref, rel)})
    return rows


def build_approvals(ref):
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "approvals", "*", "APR-*.md"))):
        rel = os.path.relpath(p, ROOT)
        text = read(rel)
        fm = frontmatter(text)
        rows.append({"id": fm.get("id", ""), "title": first_heading(text), "status": fm.get("status", ""),
                     "created": fm.get("created", ""), "product": fm.get("product", ""), "link": link(ref, rel)})
    if not rows:
        # Дашборд не читает пустой набор («no rows»), поэтому — одна служебная строка-факт.
        # Счётчик «ждут решения» считает только status == PENDING, её не учитывает.
        rows.append({"id": "—", "title": "Карточек согласования нет", "status": "НЕТ",
                     "created": datetime.date.today().isoformat(), "product": "—", "link": link(ref, "approvals/README.md")})
    return rows


def build_activity():
    counts = collections.OrderedDict()
    path = os.path.join(ROOT, "logs", "actions.jsonl")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            day = e.get("ts", "")[:10]
            key = (day, e.get("who", "ceo"))
            c = counts.setdefault(key, {"done": 0, "blocked": 0, "ask_owner": 0})
            c[e.get("decision", "done")] = c.get(e.get("decision", "done"), 0) + 1
    return [{"key": "%s %s" % k, "day": k[0], "who": "AI CEO" if k[1] == "ceo" else k[1],
             "done": v["done"], "blocked": v["blocked"], "asked": v["ask_owner"]} for k, v in counts.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default="main")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    handoff, counts = build_handoff(a.ref)
    data = {
        "portfolio": build_portfolio(a.ref, counts),
        "feed": build_feed(a.ref),
        "tasks": build_tasks(a.ref),
        "approvals": build_approvals(a.ref),
        "questions": build_questions(a.ref),
        "handoff": handoff,
        "activity": build_activity(),
    }
    for name, rows in data.items():
        with open(os.path.join(a.out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("%-10s %3d строк" % (name, len(rows)))


if __name__ == "__main__":
    main()
