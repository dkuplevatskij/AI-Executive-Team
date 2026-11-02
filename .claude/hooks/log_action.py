#!/usr/bin/env python3
"""Журнал действий агентов (хук PostToolUse).

После каждого изменяющего действия дописывает строку в logs/actions.jsonl:
когда, кто (AI CEO или имя директора), каким инструментом, над чем.
Чтение файлов и запросы «получить/показать» не пишутся — иначе журнал утонет в шуме.
Ключи и пароли в журнал не попадают: они заменяются на «[скрыто]».
Сбой журнала действие не отменяет (оно уже выполнено), но пишется в stderr.
"""
import datetime
import json
import os
import re
import sys

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "WebSearch", "WebFetch", "TodoWrite",
              "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "ToolSearch", "Skill"}
READ_MCP_RE = re.compile(r"__(get|list|search|read|query|describe|whoami|status|fetch|download|guide)")
READ_BASH_RE = re.compile(
    r"^\s*(ls|cat|head|tail|grep|rg|find|wc|pwd|echo|date|which|tree|stat|du|df|"
    r"git\s+(status|log|diff|show|branch|remote|rev-parse|ls-files|blame))\b")
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|"
    r"((token|key|secret|password|passwd)\s*[=:]\s*)\S+)", re.IGNORECASE)


def target_of(tool, ti):
    if tool == "Bash":
        return ti.get("command", "")
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return ti.get("file_path") or ti.get("notebook_path") or ""
    if tool.startswith("mcp__"):
        bits = [str(ti.get(k)) for k in ("owner", "repo", "branch", "pullNumber", "issue_number", "title")
                if ti.get(k) not in (None, "")]
        return " ".join(bits)
    if tool == "Agent":
        return "%s: %s" % (ti.get("subagent_type", "general-purpose"), ti.get("description", ""))
    return ""


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if tool in READ_TOOLS or (tool.startswith("mcp__") and READ_MCP_RE.search(tool)):
        return
    if tool == "Bash" and READ_BASH_RE.match(ti.get("command", "")) and ">" not in ti.get("command", ""):
        return
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    target = target_of(tool, ti)
    if tool in ("Edit", "Write", "MultiEdit") and target.startswith(project):
        target = os.path.relpath(target, project)
    entry = {
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "who": payload.get("agent_type") or "ceo",
        "tool": tool,
        "target": SECRET_RE.sub("[скрыто]", target)[:300],
        "decision": "done",
    }
    log_dir = os.environ.get("AET_LOG_DIR") or os.path.join(project, "logs")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "actions.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write("Журнал действий не записан: %s\n" % exc)
