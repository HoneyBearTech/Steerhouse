"""What each host did in each task (GET /api/runs/{id}/hosts), read from a run's events."""

import json

from app.host_results import (
    CHANGED,
    FAILED,
    IGNORED,
    MAX_HOSTS,
    MAX_TASKS,
    OK,
    SKIPPED,
    UNREACHABLE,
    host_results,
    parse_events,
)
from tests.conftest import make_user_client
from tests.test_runs import (
    _create_credential,
    _create_inventory_with_two_hosts,
    _create_playbook,
    _login,
    _wait_for_completion,
)

EMPTY_PLAYBOOK = "- hosts: all\n  gather_facts: false\n  tasks: []\n"


def _lines(*events: dict) -> list[bytes]:
    return [(json.dumps(e) + "\n").encode() for e in events]


def _play(name: str = "play") -> dict:
    return {"event": "playbook_on_play_start", "event_data": {"name": name}}


def _task(uuid: str, name: str, role: str | None = None, handler: bool = False) -> dict:
    data = {"task": name, "task_uuid": uuid}
    if role:
        data["role"] = role
    kind = "playbook_on_handler_task_start" if handler else "playbook_on_task_start"
    return {"event": kind, "event_data": data}


def _result(kind: str, uuid: str, host: str, res: dict | None = None, **data) -> dict:
    return {
        "event": kind,
        "event_data": {"task_uuid": uuid, "host": host, "res": res or {}, **data},
    }


def test_every_kind_of_result_is_told_apart() -> None:
    found = parse_events(
        _lines(
            _play(),
            _task("t1", "ping"),
            _result("runner_on_ok", "t1", "a"),
            _result("runner_on_ok", "t1", "b", {"changed": True, "msg": "wrote it"}),
            _result("runner_on_skipped", "t1", "c", {"skip_reason": "x"}),
            _result("runner_on_failed", "t1", "d", {"msg": "boom"}),
            _result("runner_on_failed", "t1", "e", {"msg": "meh"}, ignore_errors=True),
            _result("runner_on_unreachable", "t1", "f", {"msg": "no route"}),
        )
    )
    assert found.hosts == ["a", "b", "c", "d", "e", "f"]  # sorted
    (row,) = found.tasks
    assert {h: (r.status, r.msg) for h, r in row.results.items()} == {
        "a": (OK, None),
        "b": (CHANGED, "wrote it"),
        "c": (SKIPPED, None),
        "d": (FAILED, "boom"),
        "e": (IGNORED, "meh"),
        "f": (UNREACHABLE, "no route"),
    }
    assert row.results["b"].changed and not row.results["a"].changed


def test_only_the_short_message_leaves_the_result() -> None:
    found = parse_events(
        _lines(
            _task("t", "x"),
            _result("runner_on_failed", "t", "a", {"stderr": "e" * 900, "cmd": ["secretish"]}),
            _result("runner_on_ok", "t", "b", {"msg": ["a", "list"], "stdout": "out"}),
        )
    )
    a, b = found.tasks[0].results["a"], found.tasks[0].results["b"]
    assert a.msg == "e" * 500
    assert b.msg is None
    assert not hasattr(a, "cmd")


def test_a_loop_is_one_result_and_a_retry_replaces_the_earlier_one() -> None:
    found = parse_events(
        _lines(
            _task("t", "loop"),
            _result("runner_item_on_ok", "t", "a", {"item": 1}),
            _result("runner_item_on_failed", "t", "a", {"item": 2}),
            _result("runner_on_failed", "t", "a", {"msg": "one item failed"}),
            _task("u", "until"),
            _result("runner_on_failed", "u", "a", {"msg": "first try"}),
            _result("runner_on_ok", "u", "a", {"msg": "second try"}),
        )
    )
    assert [r.name for r in found.tasks] == ["loop", "until"]
    assert found.tasks[0].results["a"].status == FAILED
    assert found.tasks[1].results["a"].status == OK
    assert found.tasks[1].results["a"].msg == "second try"


def test_rows_are_matched_by_play_role_name_and_occurrence_not_by_uuid() -> None:
    def run(prefix: str) -> list[str]:
        events = [_play("one"), _task(prefix + "1", "same"), _task(prefix + "2", "same")]
        events += [_play("two"), _task(prefix + "3", "same", role="web")]
        events += [_result("runner_on_ok", prefix + str(n), "a") for n in (1, 2, 3)]
        return [t.key for t in parse_events(_lines(*events)).tasks]

    first, second = run("x"), run("y")
    assert first == second and len(set(first)) == 3


def test_handlers_and_tasks_without_results_and_unknown_task_starts() -> None:
    found = parse_events(
        _lines(
            _task("a", "no hosts matched"),
            _task("h", "restart", handler=True),
            _result("runner_on_ok", "h", "a"),
            # a result whose task start was lost still gets a row
            _result("runner_on_ok", "late", "a", task="late task"),
        )
    )
    assert [(t.name, t.handler) for t in found.tasks] == [("restart", True), ("late task", False)]


def test_events_without_details_are_counted_not_guessed() -> None:
    found = parse_events(
        [
            *_lines(
                _task("t", "x"),
                {"event": "runner_on_ok", "stdout": "[Steerhouse: event truncated]"},
                {"event": "redaction_error"},
                {"event": "verbose", "stdout": "noise"},
                {"event": "steerhouse_status", "stdout": "status"},
            ),
            b"not json\n",
            b"[1]\n",
        ]
    )
    assert found.lost_events == 2 and found.tasks == []


def test_the_grid_is_capped() -> None:
    events = [_task(f"t{n}", f"task {n}") for n in range(MAX_TASKS + 3)]
    events += [_result("runner_on_ok", f"t{n}", "a") for n in range(MAX_TASKS + 3)]
    found = parse_events(_lines(*events))
    assert len(found.tasks) == MAX_TASKS and found.truncated

    events = [_task("t", "x")] + [
        _result("runner_on_ok", "t", f"h{n}") for n in range(MAX_HOSTS + 2)
    ]
    found = parse_events(_lines(*events))
    assert len(found.hosts) == MAX_HOSTS and found.truncated


def test_only_the_committed_part_of_the_log_is_read(client, tmp_path) -> None:
    from app.storage import run_log_path

    first = _lines(_task("t", "x"), _result("runner_on_ok", "t", "a"))
    second = _lines(_result("runner_on_failed", "t", "b"))
    run_log_path(987).write_bytes(b"".join(first + second))
    committed = sum(len(line) for line in first)
    assert host_results(987, committed).hosts == ["a"]
    assert host_results(987, committed + len(second[0])).hosts == ["a", "b"]
    assert host_results(986, 100).tasks == []  # no log yet


def test_a_real_run_has_a_result_for_each_host_and_task(client, tmp_path) -> None:
    _login(client)
    inventory_id, host_a, host_b = _create_inventory_with_two_hosts(
        client, str(tmp_path / "a"), str(tmp_path / "b")
    )
    playbook = """\
- hosts: all
  connection: local
  gather_facts: false
  tasks:
    - name: write the marker
      ansible.builtin.copy:
        content: "x"
        dest: "{{ marker_path }}"
    - name: a task that breaks on one host
      ansible.builtin.fail:
        msg: "only b breaks"
      when: inventory_hostname == "HOST_B"
      ignore_errors: true
    - name: loop
      ansible.builtin.debug:
        msg: "{{ item }}"
      loop: [1, 2]
""".replace("HOST_B", host_b)
    run = client.post(
        "/api/runs",
        json={
            "playbook_id": _create_playbook(client, playbook, name="hosts.yml"),
            "inventory_id": inventory_id,
            "credential_id": _create_credential(client),
        },
    )
    assert run.status_code == 201, run.text
    done = _wait_for_completion(client, run.json()["id"], timeout=60)
    assert done["status"] == "success", done["status_reason"]

    out = client.get(f"/api/runs/{done['id']}/hosts")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["complete"] and not body["truncated"] and body["lost_events"] == 0
    assert body["hosts"] == [host_a, host_b]
    by_name = {t["name"]: t for t in body["tasks"]}
    status = lambda task, host: by_name[task]["results"][host]["status"]  # noqa: E731
    assert status("write the marker", host_a) == status("write the marker", host_b) == "changed"
    assert status("a task that breaks on one host", host_a) == "skipped"
    assert status("a task that breaks on one host", host_b) == "ignored"
    assert by_name["a task that breaks on one host"]["results"][host_b]["msg"] == "only b breaks"
    assert status("loop", host_a) == status("loop", host_b) == "ok"

    viewer = make_user_client("viewer1", "viewer")
    assert viewer.get(f"/api/runs/{done['id']}/hosts").json() == body
    assert client.get("/api/runs/999999/hosts").status_code == 404


def test_the_run_list_filters_by_playbook_and_inventory(client, tmp_path) -> None:
    _login(client)
    inventory_id, _, _ = _create_inventory_with_two_hosts(
        client, str(tmp_path / "a"), str(tmp_path / "b")
    )
    credential = _create_credential(client)
    ids = []
    for name in ("one.yml", "two.yml"):
        playbook = _create_playbook(client, EMPTY_PLAYBOOK, name=name)
        r = client.post(
            "/api/runs",
            json={
                "playbook_id": playbook,
                "inventory_id": inventory_id,
                "credential_id": credential,
            },
        )
        assert r.status_code == 201, r.text
        ids.append((playbook, r.json()["id"]))
    for playbook, run_id in ids:
        listed = client.get("/api/runs", params={"playbook_id": playbook}).json()
        assert [r["id"] for r in listed] == [run_id]
    both = client.get("/api/runs", params={"inventory_id": inventory_id}).json()
    assert len(both) == 2
    assert client.get("/api/runs", params={"inventory_id": 424242}).json() == []
    for _, run_id in ids:
        _wait_for_completion(client, run_id, timeout=60)
