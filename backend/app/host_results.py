"""What each host did in each task of a run, read from the run's stored events.

The log was scrubbed before it was written, and only task-level results are used (a loop's
items are already folded into its task's result by ansible). Only the status and a short
message leave this module: nothing else of a result's `res`.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.storage import run_log_path

MAX_TASKS = 5000
MAX_HOSTS = 1000
MAX_MESSAGE_CHARS = 500

# Status of one host in one task.
OK = "ok"
CHANGED = "changed"
FAILED = "failed"
IGNORED = "ignored"  # failed, but the task said ignore_errors
SKIPPED = "skipped"
UNREACHABLE = "unreachable"

_RESULT_STATUS = {
    "runner_on_ok": OK,
    "runner_on_failed": FAILED,
    "runner_on_skipped": SKIPPED,
    "runner_on_unreachable": UNREACHABLE,
}
_TASK_START = ("playbook_on_task_start", "playbook_on_handler_task_start")
# Events that carry a result or name a task: without their event_data (a truncated event) the
# grid has a hole, which is reported rather than guessed.
_NEEDS_DATA = (*_RESULT_STATUS, *_TASK_START, "playbook_on_play_start")


@dataclass
class HostResult:
    status: str
    changed: bool
    msg: str | None


@dataclass
class TaskRow:
    key: str
    play: str
    role: str | None
    name: str
    handler: bool
    results: dict[str, HostResult] = field(default_factory=dict)


@dataclass
class HostResults:
    hosts: list[str]
    tasks: list[TaskRow]
    lost_events: int
    truncated: bool


def _message(res: object) -> str | None:
    if not isinstance(res, dict):
        return None
    for name in ("msg", "stderr", "reason"):
        value = res.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_MESSAGE_CHARS]
    return None


def _committed_lines(path: Path, length: int):
    try:
        log = path.open("rb")
    except FileNotFoundError:  # a queued run has no log yet
        return
    with log:
        remaining = length
        while remaining > 0 and (line := log.readline(remaining)):
            remaining -= len(line)
            yield line


def parse_events(lines) -> HostResults:
    hosts: dict[str, None] = {}
    rows: dict[str, TaskRow] = {}  # task uuid -> row, in the order the tasks started
    seen: dict[tuple[str, str | None, str], int] = {}
    play = ""
    lost = 0
    truncated = False

    def open_row(uuid: str, data: dict, handler: bool) -> TaskRow | None:
        nonlocal truncated
        if len(rows) >= MAX_TASKS:
            truncated = True
            return None
        name = str(data.get("task") or data.get("name") or "?")
        role = data.get("role") if isinstance(data.get("role"), str) else None
        occurrence = seen.get((play, role, name), 0) + 1
        seen[(play, role, name)] = occurrence
        row = TaskRow(
            key=json.dumps([play, role, name, occurrence]),
            play=play,
            role=role,
            name=name,
            handler=handler,
        )
        rows[uuid] = row
        return row

    for raw in lines:
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("event")
        if kind == "redaction_error":
            lost += 1
            continue
        if kind not in _NEEDS_DATA:
            continue
        data = event.get("event_data")
        if not isinstance(data, dict):
            lost += 1
            continue
        if kind == "playbook_on_play_start":
            play = str(data.get("name") or data.get("play") or "")
        elif kind in _TASK_START:
            uuid = str(data.get("task_uuid") or event.get("uuid") or "")
            if uuid and uuid not in rows:
                open_row(uuid, data, kind == "playbook_on_handler_task_start")
        else:
            host = data.get("host")
            if not isinstance(host, str) or not host:
                continue
            uuid = str(data.get("task_uuid") or "")
            row = rows.get(uuid) or (open_row(uuid, data, False) if uuid else None)
            if row is None:
                continue
            if host not in hosts:
                if len(hosts) >= MAX_HOSTS:
                    truncated = True
                    continue
                hosts[host] = None
            res = data.get("res")
            status = _RESULT_STATUS[kind]
            if kind == "runner_on_failed" and data.get("ignore_errors"):
                status = IGNORED
            changed = bool(data.get("changed") or (isinstance(res, dict) and res.get("changed")))
            if status == OK and changed:
                status = CHANGED
            row.results[host] = HostResult(status, changed and status != FAILED, _message(res))
    return HostResults(
        hosts=sorted(hosts),  # arrival order differs from run to run; columns must not
        tasks=[row for row in rows.values() if row.results],
        lost_events=lost,
        truncated=truncated,
    )


@lru_cache(maxsize=16)
def _parse(path: str, length: int, mtime_ns: int) -> HostResults:  # noqa: ARG001 - a cache key
    return parse_events(_committed_lines(Path(path), length))


def host_results(run_id: int, log_bytes: int) -> HostResults:
    """The committed part of the run's log, parsed once per change of the file (a running
    run's page asks every few seconds). The result is shared: callers must not change it."""
    path = run_log_path(run_id)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except FileNotFoundError:
        return HostResults([], [], 0, False)
    return _parse(str(path), log_bytes, mtime_ns)
