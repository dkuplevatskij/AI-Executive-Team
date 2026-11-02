#!/usr/bin/env python3
"""Уведомления собственнику в Telegram о работе AI Executive Team.

Запускается GitHub Actions (.github/workflows/telegram-notify.yml), а не агентами: агентам отправка во
внешние сервисы запрещена замком. Ключ бота и номер чата — только в секретах GitHub
(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID), в репозитории и в чате их нет.

Что присылает:
  * push в любую ветку — какие отчёты, материалы, аудиты, задания для сессий, карточки согласования
    и задачи появились, и новые решения в журнале — со ссылками на файлы;
  * pull request — открыт или готов к слиянию, слит или закрыт.
Без секретов просто выходит (уведомления ещё не настроены) — задание не падает.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

REPO_URL = "https://github.com/" + os.environ.get("GITHUB_REPOSITORY", "dkuplevatskij/AI-Executive-Team")
DASHBOARD = os.environ.get("DASHBOARD_URL", "")

KINDS = [  # (префикс пути, подпись) — порядок задаёт порядок в сообщении
    ("approvals/pending/", "Ждёт вашего решения"),
    ("reports/decisions/", "Материал к решению"),
    ("reports/", "Отчёт"),
    ("audit/", "Аудит"),
    ("handoff/", "Задание для сессии продукта"),
    ("tasks/", "Задача"),
]


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def title_of(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("# "):
                    return line[2:].strip().replace("Задания для сессии разработки: ", "")
    except OSError:
        pass
    return os.path.basename(path)


def push_message():
    before, after, ref = os.environ.get("BEFORE", ""), os.environ.get("AFTER", "HEAD"), os.environ.get("REF_NAME", "")
    if not before or set(before) == {"0"}:
        diff = git("show", "--name-status", "--format=", after)
    else:
        diff = git("diff", "--name-status", before, after)
    added = [line.split("\t")[-1] for line in diff.splitlines() if line[:1] in ("A", "R")]
    lines = []
    for prefix, label in KINDS:
        for path in sorted(p for p in added if p.startswith(prefix) and p.endswith(".md") and not p.endswith("README.md")):
            if any(path.startswith(pp) for pp, _ in KINDS[:KINDS.index((prefix, label))]):
                continue  # уже учтён более точным префиксом
            url = "%s/blob/%s/%s" % (REPO_URL, ref, path)
            lines.append("• <b>%s</b>: <a href=\"%s\">%s</a>" % (label, url, esc(title_of(path))))
    # Новые решения собственника — новые строки «**D-NNN · …**» в журнале.
    if before and set(before) != {"0"}:
        log_diff = git("diff", before, after, "--", "company/decisions/log.md")
        for m in re.finditer(r"^\+\*\*(D-\d+)\s*·\s*[\d-]+\s*·\s*(.+?)\*\*", log_diff, re.M):
            lines.append("• <b>Решение записано</b>: %s. %s" % (m.group(1), esc(m.group(2))))
    if not lines:
        return None
    head = "AI Executive Team · ветка <code>%s</code>" % esc(ref)
    # Лимит Telegram — 4096 символов; обрезать посреди тега нельзя, поэтому сворачиваем целыми строками.
    out, size = [], len(head) + 200
    for i, line in enumerate(lines):
        if size + len(line) > 3500:
            out.append("…и ещё %d" % (len(lines) - i))
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join([head, ""] + out)


def pr_message():
    action = os.environ.get("PR_ACTION", "")
    merged = os.environ.get("PR_MERGED", "") == "true"
    title, url = os.environ.get("PR_TITLE", ""), os.environ.get("PR_URL", "")
    draft = os.environ.get("PR_DRAFT", "") == "true"
    if action == "opened" and draft:
        what = "Открыт черновой PR"
    elif action in ("opened", "ready_for_review"):
        what = "PR ждёт вашего слияния"
    elif action == "closed":
        what = "PR слит" if merged else "PR закрыт без слияния"
    else:
        return None
    return "AI Executive Team · %s\n<a href=\"%s\">%s</a>" % (what, url, esc(title))


def send(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Секреты TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — уведомление не отправлено.")
        return
    if DASHBOARD:
        text += "\n\n<a href=\"%s\">Дашборд</a>" % DASHBOARD
    body = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=body)
    with urllib.request.urlopen(req, timeout=20) as resp:
        ok = json.loads(resp.read().decode()).get("ok")
    print("Отправлено" if ok else "Telegram ответил ошибкой")
    if not ok:
        sys.exit(1)


def main():
    event = os.environ.get("EVENT_NAME", "")
    text = pr_message() if event == "pull_request" else push_message()
    if text:
        print(text)
        send(text)
    else:
        print("Нечего сообщать.")


if __name__ == "__main__":
    main()
