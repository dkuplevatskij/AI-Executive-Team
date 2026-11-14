#!/usr/bin/env python3
"""Замок перед каждым действием агента (хук PreToolUse Claude Code).

Зачем: правила в CLAUDE.md и .claude/rules — это текст, агент может его нарушить.
Этот скрипт запускается Claude Code перед каждым вызовом инструмента — и в главной
сессии, и у субагентов — и решает: разрешить, спросить собственника или запретить.

Решения:
  * запрет — выход с кодом 2, причина в stderr (Claude Code блокирует вызов);
  * «спросить» — JSON с permissionDecision=ask (собственник подтверждает в окне прав);
  * разрешение уровня 2 — JSON с permissionDecision=allow;
  * ничего не вывести — решают обычные права из settings.json.

Скрипт закрыт на ошибку: если он сам упал, действие запрещается (exit 2).
Список правил — ниже, в таблицах BASH_DENY, GITHUB_* и в check_write().
"""
import datetime
import json
import os
import re
import subprocess
import sys

HOME_REPO = "ai-executive-team"          # управляющий репозиторий
PROTECTED_BRANCHES = ("main", "master")  # в них агент не пишет никогда

# Пути, которые агент не меняет: замки и права. Их правит только собственник.
GUARDED_RE = r"\.claude/(settings(\.local)?\.json|hooks(/|\b))"

# Журналы только на дописывание: историю решений и действий не переписываем.
APPEND_ONLY_PREFIXES = ("company/decisions/", "logs/")


# ---------------------------------------------------------------- инфраструктура

def project_dir():
    return os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def log_dir():
    # AET_LOG_DIR — только для тестов, чтобы не засорять журнал.
    return os.environ.get("AET_LOG_DIR") or os.path.join(project_dir(), "logs")


SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|"
    r"((token|key|secret|password|passwd)\s*[=:]\s*)\S+)",
    re.IGNORECASE,
)


def redact(text):
    return SECRET_RE.sub("[скрыто]", text or "")


def log_event(payload, decision, reason, target):
    """Пишем в журнал каждое запрещённое или отправленное на подтверждение действие."""
    try:
        os.makedirs(log_dir(), exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "who": payload.get("agent_type") or "ceo",
            "tool": payload.get("tool_name"),
            "target": redact(target)[:300],
            "decision": decision,
            "reason": reason,
        }
        with open(os.path.join(log_dir(), "actions.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # журнал не должен ломать сам замок


def deny(payload, reason, target=""):
    log_event(payload, "blocked", reason, target)
    sys.stderr.write("ЗАПРЕЩЕНО замком управляющего центра: " + reason + "\n")
    sys.exit(2)


def ask(payload, reason, target=""):
    log_event(payload, "ask_owner", reason, target)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": "Нужно подтверждение собственника: " + reason,
    }}, ensure_ascii=False))
    sys.exit(0)


def allow(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------- команды терминала

# (шаблон, причина). Поиск по всей строке: ловит и «git -C папка push», и цепочки через && и ;.
BASH_DENY = [
    (r"\bgit\b[^;&|]*\bpush\b[^;&|]*(--force|--force-with-lease|\s-f\b|--mirror|--delete|\s-d\b)",
     "принудительная запись или удаление веток на GitHub"),
    (r"\bgit\b[^;&|]*\bpush\b[^;&|]*[\s:/+](main|master)(\s|$|[;&|])",
     "запись в основную ветку main/master — только через PR, слияние делает собственник"),
    (r"\bgit\b[^;&|]*\bpush\b[^;&|]*\s:\S", "удаление ветки на GitHub"),
    (r"\bgit\b[^;&|]*\breset\b[^;&|]*--hard", "git reset --hard уничтожает несохранённую работу"),
    (r"\bgit\b[^;&|]*\bclean\b[^;&|]*\s-[a-zA-Z]*f", "git clean удаляет файлы"),
    (r"\bgit\b[^;&|]*\bfilter-(branch|repo)\b", "переписывание истории git"),
    (r"\bgit\b[^;&|]*\bbranch\b[^;&|]*\s-D\b", "удаление ветки без проверки слияния"),
    (r"\brm\b\s+(-[a-zA-Z]*[rRf]|--recursive|--force)", "удаление файлов (rm -r / rm -f)"),
    (r"\bfind\b[^;&|]*\s-delete\b", "массовое удаление файлов"),
    (r"(^|[\s;&|(])(shred|truncate)\b", "уничтожение содержимого файлов"),
    (r"(^|[\s;&|(])sudo\b", "команды от имени администратора системы"),
    (r"(^|[\s;&|(])(ssh|scp|sftp|rsync)\b",
     "доступ к серверам — изменение инфраструктуры (уровень 3)"),
    (r"(^|[\s;&|(])(docker|docker-compose|kubectl|helm|terraform|ansible|ansible-playbook|"
     r"vercel|wrangler|flyctl|heroku|yc|twc)\b",
     "инфраструктура и выкладка — только собственник (уровень 3)"),
    (r"\b(npm|pnpm|yarn)\s+publish\b", "публикация пакетов"),
    (r"\bgh\b[^;&|]*\b(pr\s+merge|repo\s+(delete|create|edit|rename|archive)|"
     r"workflow\s+run|run\s+rerun|secret|variable|release\s+create)\b",
     "необратимые операции GitHub (слияние, репозитории, запуск выкладки, секреты)"),
    (r"\bgh\b[^;&|]*\bapi\b[^;&|]*(-X|--method)\s*(POST|PUT|PATCH|DELETE)",
     "изменяющие запросы к GitHub API в обход правил"),
    (r"\bcurl\b[^;&|]*(\s(-X|--request)\s*(POST|PUT|PATCH|DELETE)|"
     r"\s(-d|--data[\w-]*|-F|--form|-T|--upload-file)(\s|=))",
     "отправка данных во внешние сервисы — внешняя коммуникация (уровень 3)"),
    (r"\bwget\b[^;&|]*--post", "отправка данных во внешние сервисы (уровень 3)"),
    (r"\|\s*(ba|z|da)?sh\b", "запуск скачанного скрипта"),
    (r"(^|[\s;&|(])(sendmail|mailx?)\b", "отправка писем — внешняя коммуникация (уровень 3)"),
    (r"(^|[\s;&|(])(printenv|env|set)\s*($|[;&|])",
     "вывод переменных окружения раскрывает ключи доступа"),
    (r"(\.env(?!\.example)(\.[\w-]+)?\b|\.pem\b|\bid_(rsa|ed25519|ecdsa)\b)",
     "работа с файлами секретов"),
]

# Команды, которые что-то меняют на диске (кроме перенаправления вывода — оно ниже отдельно).
WRITE_OPS_RE = (r"(sed|perl)\s+-i|\btee\b|(^|[\s;&|(])(mv|cp|rm|ln|chmod|chown|install|truncate|mkdir|touch)\s|"
                r"python3?\s+-c|\bgit\b[^;&|]*\b(checkout|restore|apply|commit|push|mv|rm|reset|switch)\b")
# Цель перенаправления «> файл» / «>> файл»; «2>&1» и «>/dev/null» сюда не попадают.
REDIRECT_RE = re.compile(r"(?<![0-9&>])>>?\s*([^\s&;|<>]+)")
ABS_PATH_RE = re.compile(r"(?<![\w.~-])(/[\w.\-]+(?:/[\w.\-]*)*)")
HARMLESS_PATHS = ("/dev/null", "/dev/stdout", "/dev/stderr")


def allowed_outside_root(path, payload):
    """Куда агенту можно писать вне репозитория: временные папки и свой черновик."""
    p = os.path.realpath(path)
    roots = ["/tmp", "/dev/null", "/private/tmp", "/var/folders"]
    if payload.get("scratchpad_dir"):
        roots.append(os.path.realpath(payload["scratchpad_dir"]))
    return any(p == r or p.startswith(r.rstrip("/") + "/") for r in roots)


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_bash(payload):
    cmd = " ".join((payload.get("tool_input") or {}).get("command", "").split())
    for pattern, reason in BASH_DENY:
        if re.search(pattern, cmd):
            deny(payload, reason, cmd)

    writes = bool(re.search(WRITE_OPS_RE, cmd))
    redirects = [t for t in REDIRECT_RE.findall(cmd) if t not in HARMLESS_PATHS]

    # Замки и права агент не трогает и через терминал.
    if re.search(GUARDED_RE, cmd) and (writes or any(re.search(GUARDED_RE, t) for t in redirects)):
        deny(payload, "изменение замков и прав (.claude/settings.json, .claude/hooks) — только собственник", cmd)

    # Пишущая команда с путём за пределами управляющего репозитория:
    # репозитории продуктов меняются только через согласованный PR.
    root = project_dir()
    cwd = os.path.realpath(payload.get("cwd") or root)
    targets = list(redirects) + (ABS_PATH_RE.findall(cmd) if writes else [])
    for path in targets:
        real = os.path.realpath(os.path.join(cwd, path))
        if path in HARMLESS_PATHS or real == root or real.startswith(root + "/") \
                or allowed_outside_root(real, payload):
            continue
        deny(payload, "запись за пределами управляющего репозитория (" + path +
             ") — репозитории продуктов меняются только через согласованный PR", cmd)
    # Пишущая команда, запущенная из папки другого репозитория (cd ... && git commit).
    if writes and not (cwd == root or cwd.startswith(root + "/") or allowed_outside_root(cwd, payload)):
        deny(payload, "изменения выполняются из папки вне управляющего репозитория (" + cwd + ")", cmd)

    # «git push» без указания ветки, стоя на main, тоже пишет в main.
    if re.search(r"\bgit\b[^;&|]*\bpush\b", cmd):
        cwd = payload.get("cwd") or project_dir()
        if current_branch(cwd) in PROTECTED_BRANCHES:
            deny(payload, "git push с ветки main/master — работайте в отдельной ветке", cmd)


# ---------------------------------------------------------------- MCP-инструменты

GITHUB_DENY = {
    "merge_pull_request": "слияние PR — только собственник",
    "enable_pr_auto_merge": "автослияние PR — только собственник",
    "delete_file": "удаление файлов в репозиториях",
    "create_repository": "создание репозиториев — только собственник",
    "fork_repository": "создание репозиториев — только собственник",
    "actions_run_trigger": "запуск GitHub Actions может выкатить код в прод",
}
# Меняют код или ветки: в управляющем репозитории — можно, в репозитории продукта — спросить.
GITHUB_CODE_WRITE = {
    "create_or_update_file", "push_files", "create_branch", "create_pull_request",
    "update_pull_request", "update_pull_request_branch", "pull_request_review_write",
    "add_comment_to_pending_review", "add_reply_to_pull_request_comment",
    "resolve_review_thread", "unresolve_review_thread", "request_copilot_review",
    "disable_pr_auto_merge",
}
# Задачи и комментарии — уровень 2, разрешены во всех репозиториях портфеля.
GITHUB_ISSUE_WRITE = {"issue_write", "add_issue_comment", "update_issue_comment", "sub_issue_write"}

READ_ACTION_RE = re.compile(
    r"^(get|list|search|read|query|describe|whoami|status|fetch|download|guide|export|usage|profiles)",
    re.IGNORECASE)


def check_mcp(payload):
    name = payload.get("tool_name", "")
    parts = name.split("__")
    server = parts[1] if len(parts) > 2 else ""
    action = "__".join(parts[2:]) if len(parts) > 2 else name
    ti = payload.get("tool_input") or {}

    if server == "github":
        repo = str(ti.get("repo", "")).lower()
        target = "%s/%s %s" % (ti.get("owner", ""), ti.get("repo", ""), action)
        if action in GITHUB_DENY:
            deny(payload, GITHUB_DENY[action], target)
        branch = str(ti.get("branch", ""))
        if action in ("push_files", "create_or_update_file") and branch in PROTECTED_BRANCHES:
            deny(payload, "запись в основную ветку main/master — только через PR", target)
        if action == "create_branch" and branch in PROTECTED_BRANCHES:
            deny(payload, "пересоздание основной ветки", target)
        if action in GITHUB_CODE_WRITE:
            if repo == HOME_REPO:
                allow("Уровень 2: изменения управляющего репозитория в отдельной ветке")
            ask(payload, "изменение кода репозитория продукта «%s»" % ti.get("repo", "?"), target)
        if action in GITHUB_ISSUE_WRITE:
            allow("Уровень 2: задачи и комментарии в репозиториях портфеля")
        if READ_ACTION_RE.match(action):
            return
        ask(payload, "неизвестное действие GitHub «%s»" % action, target)

    # Прочие внешние сервисы: читать можно, любое изменение — с подтверждения.
    if READ_ACTION_RE.match(action):
        return
    ask(payload, "действие во внешнем сервисе «%s» (%s)" % (action, server), name)


# ---------------------------------------------------------------- запись файлов

def load_scopes():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_scopes.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("scopes", {})
    except (OSError, ValueError):
        return {}


def check_write(payload):
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path:
        return
    real = os.path.realpath(path)
    base = os.path.basename(real)
    root = project_dir()

    if re.fullmatch(r"\.env(\.[\w-]+)?", base) and base != ".env.example":
        deny(payload, "файлы .env с секретами в репозиторий не пишутся", path)
    if re.search(r"\.(pem|key|p12)$|^id_(rsa|ed25519|ecdsa)", base):
        deny(payload, "ключи и сертификаты в репозиторий не пишутся", path)

    inside = real == root or real.startswith(root + "/")
    if not inside:
        if allowed_outside_root(real, payload):
            return
        deny(payload, "запись за пределами управляющего репозитория — репозитории продуктов "
                      "меняются только через согласованный PR", path)

    rel = os.path.relpath(real, root).replace(os.sep, "/")
    if re.search(GUARDED_RE, rel):
        deny(payload, "изменение замков и прав (.claude/settings.json, .claude/hooks) — только собственник", rel)

    # Журналы: новую запись можно добавить, прежние — нельзя переписать.
    if rel.startswith(APPEND_ONLY_PREFIXES):
        tool = payload.get("tool_name")
        if tool == "Write" and os.path.exists(real):
            deny(payload, "журнал только на дописывание: перезапись существующего файла запрещена", rel)
        if tool == "Edit":
            old, new = ti.get("old_string", ""), ti.get("new_string", "")
            try:
                with open(real, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                content = ""
            # Дописывание — это правка самого хвоста файла, где старый текст остаётся целиком.
            # Иначе «D-001» → «D-001 изменено» прошло бы как дописывание, меняя прежнюю запись.
            at_end = bool(old.strip()) and content.rstrip().endswith(old.rstrip())
            if not new.startswith(old) or ti.get("replace_all") or not at_end:
                deny(payload, "журнал только на дописывание: новые записи добавляются в конец, "
                              "прежние не меняются", rel)
        if tool in ("MultiEdit", "NotebookEdit"):
            deny(payload, "журнал только на дописывание", rel)

    agent = payload.get("agent_type")
    if agent:
        # Решение собственника записывает только AI CEO со слов собственника.
        if rel.startswith("approvals/") and not rel.startswith("approvals/pending/"):
            deny(payload, "решение по согласованию фиксирует только AI CEO со слов собственника", rel)
        scopes = load_scopes()
        allowed = scopes.get(agent)
        if not allowed:
            deny(payload, "у агента «%s» нет права записи файлов" % agent, rel)
        if not any(rel.startswith(p) for p in allowed):
            deny(payload, "агент «%s» пишет только в: %s" % (agent, ", ".join(allowed)), rel)


# ---------------------------------------------------------------- точка входа

def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    if tool == "Bash":
        check_bash(payload)
    elif tool.startswith("mcp__"):
        check_mcp(payload)
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        check_write(payload)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # закрыто на ошибку: сломанный замок не пропускает действие
        sys.stderr.write("ЗАПРЕЩЕНО: замок управляющего центра не смог проверить действие (%s)\n" % exc)
        sys.exit(2)
