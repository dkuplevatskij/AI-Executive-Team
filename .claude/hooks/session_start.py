#!/usr/bin/env python3
"""Сводка при старте сессии (хук SessionStart).

Что видит AI CEO в начале каждой сессии, не тратя на это шагов:
сегодняшнюю дату, сколько согласований ждут собственника и дату последнего отчёта.
Всё, что печатается в stdout, Claude Code добавляет в контекст сессии.
"""
import datetime
import glob
import os

project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def count(pattern):
    return len([p for p in glob.glob(os.path.join(project, pattern)) if not p.endswith("README.md")])


def latest(pattern):
    files = sorted(glob.glob(os.path.join(project, pattern)))
    return os.path.relpath(files[-1], project) if files else "отчётов ещё нет"


print("Управляющий центр AI Executive Team. Сегодня: %s." % datetime.date.today().isoformat())
print("Ждут решения собственника (approvals/pending): %d." % count("approvals/pending/*.md"))
print("Активных задач (tasks/active): %d." % count("tasks/active/*.md"))
print("Последняя ежедневная сводка: %s." % latest("reports/daily/*.md"))
print("Замки (.claude/hooks) активны: перед каждым действием работает guard.py.")
