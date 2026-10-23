"""GET /api/stats: run and worker counts for dashboards (a Heimdall tile), and the `stats` API
key preset that may read those counts and nothing else."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.db import get_sessionmaker
from app.main import app
from app.models import AuditEvent, Run, Worker
from tests.test_api_keys import _create_key, _key_client, _run_body
from tests.test_projects import _admin, _member, _populate, _project

FIELDS = {"queued", "running", "succeeded_24h", "failed_24h", "workers_online"}


@pytest.fixture
def world(client: TestClient):
    admin = _admin(client)
    a, b = _project(admin, "Team A"), _project(admin, "Team B")
    world = {"admin": admin, "a": _populate(admin, a, "a"), "b": _populate(admin, b, "b")}
    # _populate's runs have finished; from here on, the only workers are the ones a test adds.
    admin.worker.stop()
    db = get_sessionmaker()()
    db.query(Worker).delete()
    db.commit()
    db.close()
    world["before"] = {p: admin.get("/api/stats", params={"project_id": p}).json() for p in (a, b)}
    return world


def _add_runs(project_id: int, *rows: tuple[str, timedelta | None]) -> None:
    """Runs in `project_id`, each (status, finished how long ago, or None if unfinished)."""
    now = datetime.now(UTC)
    db = get_sessionmaker()()
    for status, age in rows:
        finished = now - age if age is not None else None
        db.add(
            Run(
                project_id=project_id,
                playbook_name="site-zq.yml",
                inventory_name="prod-zq",
                credential_name="deploy-key-zq",
                limit="secret-host-zq",
                extra_vars={"api_token": "sentinel-zq"},
                playbook_snapshot="- hosts: all",
                playbook_sha256="0" * 64,
                status=status,
                triggered_by="admin",
                queued_at=(finished or now) - timedelta(minutes=1),
                started_at=(finished or now) - timedelta(seconds=30),
                finished_at=finished,
            )
        )
    db.commit()
    db.close()


def _add_worker(worker_id: str, seen_ago: timedelta) -> None:
    db = get_sessionmaker()()
    db.add(Worker(id=worker_id, slots=2, last_seen_at=datetime.now(UTC) - seen_ago))
    db.commit()
    db.close()


def _seed(world) -> None:
    hour, two_days = timedelta(hours=1), timedelta(days=2)
    a, b = world["a"]["project"], world["b"]["project"]
    _add_runs(
        a,
        ("running", None),
        ("success", hour),
        ("success", hour),
        ("failed", hour),
        ("timed_out", hour),
        ("cancelled", hour),  # neither a success nor a failure
        ("failed", two_days),  # too old
        ("success", two_days),
    )
    _add_runs(b, ("running", None), ("running", None), ("failed", hour))
    _add_worker("host-zq:1", timedelta(seconds=5))
    _add_worker("host-zq:2", timedelta(seconds=5))
    _add_worker("host-zq:3", timedelta(minutes=10))  # offline


def _added(world, after: dict, *projects: int) -> dict:
    """What changed since the fixture's counts (workers: the count itself, it started at 0)."""
    added = {
        field: after[field] - sum(world["before"][p][field] for p in projects)
        for field in FIELDS - {"workers_online"}
    }
    return added | {"workers_online": after["workers_online"]}


def test_counts_cover_the_last_day_and_the_callers_projects(world) -> None:
    a, b = world["a"]["project"], world["b"]["project"]
    assert all(world["before"][p]["workers_online"] == 0 for p in (a, b))
    _seed(world)
    admin = world["admin"]

    everything = admin.get("/api/stats")
    assert everything.status_code == 200
    assert _added(world, everything.json(), a, b) == {
        "queued": 0,
        "running": 3,
        "succeeded_24h": 2,
        "failed_24h": 3,
        "workers_online": 2,
    }
    assert _added(world, admin.get("/api/stats", params={"project_id": a}).json(), a) == {
        "queued": 0,
        "running": 1,
        "succeeded_24h": 2,
        "failed_24h": 2,  # failed + timed out
        "workers_online": 2,
    }
    assert _added(world, admin.get("/api/stats", params={"project_id": b}).json(), b) == {
        "queued": 0,
        "running": 2,
        "succeeded_24h": 0,
        "failed_24h": 1,
        "workers_online": 2,
    }
    _add_runs(a, ("queued", None))
    assert admin.get("/api/stats", params={"project_id": a}).json()["queued"] == (
        world["before"][a]["queued"] + 1
    )


def test_members_see_their_projects_only(world) -> None:
    _seed(world)
    admin, a, b = world["admin"], world["a"]["project"], world["b"]["project"]
    viewer = _member(admin, "stats-viewer", {a: "viewer"})
    assert _added(world, viewer.get("/api/stats").json(), a)["running"] == 1

    assert (
        viewer.get("/api/stats").json() == admin.get("/api/stats", params={"project_id": a}).json()
    )
    assert viewer.get("/api/stats", params={"project_id": b}).status_code == 404
    nobody = _member(admin, "stats-nobody", {})
    assert nobody.get("/api/stats").status_code == 403


@pytest.mark.parametrize("preset", ["stats", "read-only", "trigger"])
def test_every_key_reads_its_own_projects_counts(world, preset: str) -> None:
    _seed(world)
    admin, a, b = world["admin"], world["a"]["project"], world["b"]["project"]
    key = _key_client(_create_key(admin, a, name=f"dash-{preset}", preset=preset)["token"])

    own = key.get("/api/stats")
    assert own.status_code == 200
    assert _added(world, own.json(), a)["running"] == 1  # project b's two aren't in it
    assert own.json() == admin.get("/api/stats", params={"project_id": a}).json()
    assert key.get("/api/stats", params={"project_id": a}).json() == own.json()
    assert key.get("/api/stats", params={"project_id": b}).status_code == 404


def test_the_answer_is_counts_only(world) -> None:
    _seed(world)
    admin, a = world["admin"], world["a"]["project"]
    key = _key_client(_create_key(admin, a, name="dash", preset="stats")["token"])
    response = key.get("/api/stats")
    body = response.json()
    assert set(body) == FIELDS
    assert all(type(value) is int for value in body.values())
    assert "zq" not in response.text  # no names, hosts, vars or worker ids


def test_a_stats_key_can_read_nothing_else(world) -> None:
    admin, a = world["admin"], world["a"]
    key = _key_client(_create_key(admin, a["project"], name="dash", preset="stats")["token"])
    calls = [
        ("GET", "/api/runs", None),
        ("GET", f"/api/runs/{a['run']}", None),
        ("GET", f"/api/runs/{a['run']}/log", None),
        ("GET", f"/api/runs/{a['run']}/hosts", None),
        ("GET", f"/api/runs/{a['run']}/artifacts", None),
        ("POST", "/api/runs", _run_body(a)),
        ("POST", f"/api/runs/{a['run']}/cancel", None),
        ("POST", "/api/run-templates/1/launch", {}),
    ]
    for method, path, body in calls:
        response = key.request(method, path, json=body)
        assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
    db = get_sessionmaker()()
    denied = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == "permission.denied", AuditEvent.actor_username == "apikey:dash"
        )
        .count()
    )
    db.close()
    assert denied == len(calls)


def test_a_stats_key_cannot_follow_a_run_over_the_websocket(world) -> None:
    admin, a = world["admin"], world["a"]
    token = _create_key(admin, a["project"], name="dash", preset="stats")["token"]
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(f"/api/runs/{a['run']}/ws") as ws,
    ):
        ws.receive_json()
    assert closed.value.code == 1008


def test_without_a_valid_key_or_session_it_is_refused(world) -> None:
    assert TestClient(app).get("/api/stats").status_code == 401
    response = _key_client("ansd_00000000_" + "x" * 43).get("/api/stats")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_the_stats_preset_is_listed_and_shown_like_the_others(world) -> None:
    admin, a = world["admin"], world["a"]["project"]
    created = _create_key(admin, a, name="dash", preset="stats")
    assert created["preset"] == "stats"
    listed = admin.get(f"/api/projects/{a}/api-keys").json()
    assert [(k["name"], k["preset"], k["status"]) for k in listed] == [("dash", "stats", "active")]
    bogus = admin.post(
        f"/api/projects/{a}/api-keys",
        json={"name": "x", "preset": "admin", "current_password": "admin"},
    )
    assert bogus.status_code == 422
