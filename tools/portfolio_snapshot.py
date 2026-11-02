#!/usr/bin/env python3
"""Сравнительная сводка по портфелю — без ИИ, только по файлам.

Читает portfolio/registry.yaml и карточки portfolio/<id>/card.md и печатает таблицу:
статус, запущен ли, дата обновления карточки (устарела, если старше 30 дней), сколько из 23 полей
заполнено, сколько помечено «нет данных», и значения ключевых денежных полей (11–15).

Зачем отдельный скрипт: цифры заполненности и свежести должны быть посчитаны, а не «оценены»
моделью. AI CEO и CDO используют вывод как основу /portfolio-review.

Запуск из корня репозитория:  python3 tools/portfolio_snapshot.py
С ключом --check возвращает код 1, если у продукта из реестра нет карточки или в ней не 23 поля.
"""
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Пустым считается поле, которое начинается с «нет данных»: частичное упоминание внутри
# заполненного поля («модель есть; планы — нет подтверждённых данных») пустым не считается.
EMPTY_RE = re.compile(r"^\W*(нет подтвержд|не заполнено)", re.IGNORECASE)
STALE_DAYS = 30


def load_registry():
    import yaml  # PyYAML есть в стандартной поставке большинства систем; иначе: pip install pyyaml
    with open(os.path.join(ROOT, "portfolio", "registry.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["products"]


def parse_card(path):
    """Возвращает (дата обновления, {номер поля: значение})."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    updated = datetime.date.fromisoformat(m.group(1)) if m else None
    fields = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].isdigit():
            fields[int(cells[0])] = cells[2]
    return updated, fields


def short(value, width=28):
    value = re.sub(r"\s+", " ", value or "")
    return value if len(value) <= width else value[: width - 1] + "…"


def main():
    check = "--check" in sys.argv
    today = datetime.date.today()
    problems = []
    rows = []
    for p in load_registry():
        card = os.path.join(ROOT, p["card"])
        if not os.path.exists(card):
            problems.append("%s: нет карточки %s" % (p["id"], p["card"]))
            continue
        updated, fields = parse_card(card)
        if sorted(fields) != list(range(1, 24)):
            problems.append("%s: в карточке не 23 поля (найдены: %s)" % (p["id"], sorted(fields)))
        empty = sum(1 for v in fields.values() if EMPTY_RE.search(v) or not v)
        age = (today - updated).days if updated else None
        fresh = "нет даты" if age is None else ("УСТАРЕЛА %d дн." % age if age > STALE_DAYS else str(updated))
        rows.append([p["id"], p["status"], "да" if p.get("launched") else "нет", fresh,
                     "%d/23" % (len(fields) - empty), str(empty),
                     short(fields.get(11)), short(fields.get(12)), short(fields.get(14))])

    head = ["Продукт", "Статус", "Запущен", "Карточка", "Заполнено", "Нет данных",
            "Выручка (11)", "MRR (12)", "Пользователи (14)"]
    widths = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    fmt = "  ".join("%-" + str(w) + "s" for w in widths)
    print("Сводка портфеля на %s (реестр: %d продуктов)\n" % (today, len(rows) + len(problems)))
    print(fmt % tuple(head))
    print(fmt % tuple("-" * w for w in widths))
    for r in rows:
        print(fmt % tuple(r))
    if problems:
        print("\nПроблемы:")
        for pr in problems:
            print("  - " + pr)
    sys.exit(1 if (check and problems) else 0)


if __name__ == "__main__":
    main()
