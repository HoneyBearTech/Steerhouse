"""The `monitoring` compose profile's setup job: the Grafana database role (created, then updated
in place), the generated Prometheus and Grafana configuration, and what each one may see."""

import json
from pathlib import Path

import pytest
import yaml
from psycopg.errors import InsufficientPrivilege, ReadOnlySqlTransaction
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError

from app import analytics, cli, monitoring
from app.db import get_engine, get_sessionmaker
from tests.conftest import TEST_DATABASE_URL
from tests.test_analytics import _drop_role

ROLE = "grafana_ro_test"
PASSWORD = "a-long-test-password-for-grafana-0123"
TOKEN = "t" * 40
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def db(client):
    with get_engine().begin() as conn:
        _drop_role(conn, ROLE)
    session = get_sessionmaker()()
    yield session
    session.close()
    with get_engine().begin() as conn:
        _drop_role(conn, ROLE)
        # ensure_role revokes TEMPORARY from PUBLIC (the test database outlives this test).
        conn.execute(text(f"GRANT TEMPORARY ON DATABASE {conn.engine.url.database} TO PUBLIC"))


def _as_role(password: str = PASSWORD):
    url = make_url(TEST_DATABASE_URL).set(username=ROLE, password=password)
    return create_engine(url)


def test_the_scram_verifier_is_what_postgres_expects() -> None:
    verifier = monitoring.scram_sha256("pencil", salt=bytes(range(16)))
    assert verifier.startswith("SCRAM-SHA-256$4096:AAECAwQFBgcICQoLDA0ODw==$")
    assert verifier == monitoring.scram_sha256("pencil", salt=bytes(range(16)))
    assert verifier != monitoring.scram_sha256("pencil2", salt=bytes(range(16)))
    assert "pencil" not in verifier


def test_the_role_is_created_limited_and_can_log_in(db) -> None:
    result = monitoring.ensure_role(db, ROLE, PASSWORD)
    assert result.ok, result.problems
    assert result.warnings == []  # read-only by default, and no TEMP on the database
    flags = db.execute(
        text(
            "SELECT rolsuper, rolinherit, rolcanlogin, rolconnlimit, rolconfig "
            "FROM pg_roles WHERE rolname = :r"
        ),
        {"r": ROLE},
    ).one()
    assert flags[:4] == (False, False, True, monitoring.CONNECTION_LIMIT)
    assert set(flags[4]) == {
        "default_transaction_read_only=on",
        "statement_timeout=30s",
        "search_path=analytics",
    }
    engine = _as_role()
    try:
        with engine.connect() as conn:  # a real SCRAM login with the plain password
            assert conn.execute(text("SELECT count(*) FROM analytics.projects")).scalar_one() >= 0
            with pytest.raises(ProgrammingError) as caught:  # no privilege outside the views
                conn.execute(text("SELECT 1 FROM public.users"))
            assert isinstance(caught.value.orig, InsufficientPrivilege)
            conn.rollback()
            for sql in (  # refused by privileges or by the read-only default
                "CREATE TABLE public.sneaky (x int)",
                "INSERT INTO analytics.projects (project_id, project) VALUES (99, 'x')",
            ):
                with pytest.raises((ProgrammingError, InternalError)) as caught:
                    conn.execute(text(sql))
                assert isinstance(
                    caught.value.orig, (InsufficientPrivilege, ReadOnlySqlTransaction)
                ), sql
                conn.rollback()
    finally:
        engine.dispose()


def test_running_it_again_changes_the_password_and_nothing_else(db) -> None:
    monitoring.ensure_role(db, ROLE, PASSWORD)
    other = "another-long-password-for-grafana-4567"
    assert monitoring.ensure_role(db, ROLE, other).ok
    engine = _as_role(other)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM analytics.runs LIMIT 1"))
    finally:
        engine.dispose()
    old = _as_role(PASSWORD)
    try:
        with pytest.raises(OperationalError):
            old.connect()
    finally:
        old.dispose()


def test_it_won_t_touch_a_role_that_is_not_plain(db) -> None:
    db.execute(text(f"CREATE ROLE {ROLE} LOGIN SUPERUSER"))
    db.commit()
    with pytest.raises(monitoring.MonitoringError, match="not touching it"):
        monitoring.ensure_role(db, ROLE, PASSWORD)
    assert db.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = :r"), {"r": ROLE}
    ).scalar_one()


@pytest.mark.parametrize(
    "password", ["", "short", "has a space in it, long enough....", "naïve-password-long-enough-xx"]
)
def test_weak_or_odd_passwords_are_refused_before_any_sql(db, password) -> None:
    with pytest.raises(monitoring.MonitoringError, match="password"):
        monitoring.ensure_role(db, ROLE, password)
    assert (
        db.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": ROLE}).first() is None
    )


def test_role_names_are_plain_identifiers(db) -> None:
    for name in ("Grafana", "grafana ro", 'x"; DROP TABLE users; --', ""):
        with pytest.raises(monitoring.MonitoringError, match="role name"):
            monitoring.ensure_role(db, name, PASSWORD)


def _setup(tmp_path: Path, **overrides):
    prometheus, grafana = tmp_path / "prometheus", tmp_path / "grafana"
    arguments = {
        "role": ROLE,
        "password": PASSWORD,
        "token": TOKEN,
        "prometheus_dir": prometheus,
        "grafana_dir": grafana,
    }
    arguments.update(overrides)
    return monitoring.setup(TEST_DATABASE_URL, **arguments), prometheus, grafana


def test_the_config_names_the_scrape_target_data_sources_and_dashboards(db, tmp_path) -> None:
    result, prometheus, grafana = _setup(tmp_path)
    assert result.ok
    scrape = yaml.safe_load((prometheus / "prometheus.yml").read_text())
    job = scrape["scrape_configs"][0]
    assert job["job_name"] == "steerhouse"
    assert job["static_configs"] == [{"targets": ["backend:8002"]}]
    assert job["authorization"] == {"type": "Bearer", "credentials": TOKEN}
    sources = yaml.safe_load((grafana / "datasources" / "steerhouse.yaml").read_text())[
        "datasources"
    ]
    assert {s["uid"] for s in sources} == {monitoring.PROMETHEUS_UID, monitoring.DATABASE_UID}
    database = next(s for s in sources if s["uid"] == monitoring.DATABASE_UID)
    assert database["user"] == ROLE and database["url"] == "postgres:5432"
    assert database["secureJsonData"]["password"] == "$__file{/run/secrets/grafana_db_password}"
    provider = yaml.safe_load((grafana / "dashboards" / "steerhouse.yaml").read_text())[
        "providers"
    ][0]
    assert provider["allowUiUpdates"] is False
    assert provider["options"]["path"] == "/provisioning/steerhouse-dashboards"
    for name in monitoring.DASHBOARD_FILES:
        copied = (grafana / "steerhouse-dashboards" / f"{name}.json").read_bytes()
        assert copied == (REPO / "grafana" / "dashboards" / f"{name}.json").read_bytes()
        json.loads(copied)


def test_the_metrics_token_stays_out_of_what_grafana_reads(db, tmp_path) -> None:
    _, prometheus, grafana = _setup(tmp_path)
    assert TOKEN in (prometheus / "prometheus.yml").read_text()
    for path in grafana.rglob("*"):
        if path.is_file():
            assert TOKEN not in path.read_text(errors="ignore"), path
            assert PASSWORD not in path.read_text(errors="ignore"), path
    assert not (grafana / "prometheus.yml").exists()


def test_a_second_run_replaces_stale_dashboards(db, tmp_path) -> None:
    _, _, grafana = _setup(tmp_path)
    stale = grafana / "steerhouse-dashboards" / "removed-upstream.json"
    stale.write_text("{}")
    _setup(tmp_path)
    assert not stale.exists()
    assert len(list((grafana / "steerhouse-dashboards").glob("*.json"))) == 3


def test_it_needs_a_real_metrics_token_before_it_does_anything(db, tmp_path) -> None:
    for token in ("", "short", "has a space " * 5):
        with pytest.raises(monitoring.MonitoringError, match="METRICS_TOKEN"):
            _setup(tmp_path, token=token)
    assert (
        db.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": ROLE}).first() is None
    )
    assert not (tmp_path / "prometheus").exists()


def test_missing_dashboards_stop_it_before_writing_anything(db, tmp_path, monkeypatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("GRAFANA_DASHBOARDS_DIR", str(empty))
    with pytest.raises(monitoring.MonitoringError, match="dashboards are missing"):
        _setup(tmp_path)
    assert not (tmp_path / "prometheus" / "prometheus.yml").exists()


def test_the_command_reads_the_secret_files_and_reports(db, tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "database_url").write_text(TEST_DATABASE_URL + "\n")
    (tmp_path / "grafana_db_password").write_text(PASSWORD + "\n")
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    code = cli.main(
        [
            "monitoring-setup",
            "--role", ROLE,
            "--database-url-file", str(tmp_path / "database_url"),
            "--password-file", str(tmp_path / "grafana_db_password"),
            "--prometheus-dir", str(tmp_path / "p"),
            "--grafana-dir", str(tmp_path / "g"),
        ]
    )  # fmt: skip
    out = capsys.readouterr()
    assert code == 0, out.err
    assert "configuration written" in out.out
    assert PASSWORD not in out.out + out.err and TOKEN not in out.out + out.err
    assert (tmp_path / "p" / "prometheus.yml").is_file()
    monkeypatch.setenv("METRICS_TOKEN", "")
    assert cli.main(["monitoring-setup", "--database-url-file", str(tmp_path / "database_url"),
                     "--password-file", str(tmp_path / "grafana_db_password")]) == 1  # fmt: skip
    assert "METRICS_TOKEN" in capsys.readouterr().err
    assert analytics.check(db, ROLE).ok
