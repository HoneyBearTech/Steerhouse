"""Project memberships managed from OpenID Connect groups (OIDC_ROLE_MAP, OIDC_GROUPS_CLAIM)."""

# ruff: noqa: F811 - tests take the fixtures imported below

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.models import ProjectMember, User
from tests.fake_oidc import FakeOidc
from tests.test_projects import _project
from tests.test_sso import _audit, _ok, _provision, _refused, _sign_in, fake, sso  # noqa: F401

BASE = {
    "oidc_issuer": "https://idp.test",
    "oidc_client_id": "c",
    "oidc_client_secret": "s",
    "public_url": "http://x",
}


def _map(monkeypatch, role_map: dict, **more: str) -> None:
    monkeypatch.setenv("OIDC_ROLE_MAP", json.dumps(role_map))
    for name, value in more.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def _members(project_id: int) -> dict[str, tuple[str, str | None]]:
    db = get_sessionmaker()()
    try:
        rows = (
            db.query(User.username, ProjectMember.role, ProjectMember.granted_by)
            .join(User, User.id == ProjectMember.user_id)
            .filter(ProjectMember.project_id == project_id)
            .all()
        )
        return {name: (role, granted_by) for name, role, granted_by in rows}
    finally:
        db.close()


def _groups(*groups: str) -> dict:
    return {"claims": {"groups": list(groups)}}


# --------------------------------------------------------------------- configuration


def test_the_map_is_normalised_and_bad_values_refused() -> None:
    settings = Settings(**BASE, oidc_role_map={" ops ": {" Default ": "operator"}})
    assert settings.oidc_role_map == {"ops": {"Default": "operator"}}
    assert settings.oidc_groups_claim == "groups"
    # Group names are the provider's own spelling (paths, GUIDs, mixed case): kept exactly.
    kept = Settings(**BASE, oidc_role_map={"/Org/Ops": {"P": "viewer"}, "OPS": {"P": "viewer"}})
    assert set(kept.oidc_role_map) == {"/Org/Ops", "OPS"}

    for bad in [
        {"": {"P": "viewer"}},
        {"ops": {}},
        {"ops": {"": "viewer"}},
        {"ops": {"P": "owner"}},
        {"ops": {"P": "superuser"}},
        {" ops": {"P": "viewer"}, "ops ": {"P": "viewer"}},
        {"a\nb": {"P": "viewer"}},
        {"x" * 300: {"P": "viewer"}},
    ]:
        with pytest.raises(ValueError, match="OIDC_ROLE_MAP"):
            Settings(**BASE, oidc_role_map=bad)
    with pytest.raises(ValueError, match="maps more than"):
        Settings(**BASE, oidc_role_map={f"g{n}": {"P": "viewer"} for n in range(101)})
    for claim in ["", "  ", "a" * 101]:
        with pytest.raises(ValueError, match="OIDC_GROUPS_CLAIM"):
            Settings(**BASE, oidc_groups_claim=claim)


def test_the_map_needs_oidc_sign_in() -> None:
    with pytest.raises(ValueError, match="OIDC_ROLE_MAP needs OIDC"):
        Settings(oidc_role_map={"ops": {"P": "viewer"}})


# ------------------------------------------------------------------------- the mapping


def test_groups_add_change_and_remove_memberships(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops, web = _project(admin, "Ops"), _project(admin, "Web")
    _map(
        monkeypatch,
        {"ops": {"Ops": "operator", "Web": "viewer"}, "leads": {"Ops": "admin"}},
    )
    assert _ok(_sign_in(fake, **_groups("ops", "unrelated"))[1])
    assert _members(ops)["alice"] == ("operator", "oidc")
    assert _members(web)["alice"] == ("viewer", "oidc")
    added = [e for e in _audit(admin, "project.member_add") if "via" in e["detail"]]
    assert {(e["project_id"], e["detail"]["via"]) for e in added} == {
        (ops, "oidc group ops"),
        (web, "oidc group ops"),
    }
    assert {e["actor_username"] for e in added} == {"(oidc group sync)"}

    # Joined a second group: the higher role wins.
    assert _ok(_sign_in(fake, **_groups("ops", "leads"))[1])
    assert _members(ops)["alice"] == ("admin", "oidc")
    change = _audit(admin, "project.member_role_change")[0]
    assert change["detail"] == {
        "via": "oidc group leads",
        "role": "admin",
        "previous_role": "operator",
    }

    # Left both: both memberships go.
    assert _ok(_sign_in(fake, **_groups())[1])
    assert "alice" not in _members(ops) and "alice" not in _members(web)
    assert len(_audit(admin, "project.member_remove")) == 2
    # The global role was never touched.
    assert admin.get("/api/users").json()[-1]["role"] == "operator"


def test_a_missing_claim_means_no_groups(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert _members(ops)["alice"] == ("operator", "oidc")
    assert _ok(_sign_in(fake)[1])  # Keycloak leaves the claim out for a user in no group
    assert "alice" not in _members(ops)


def test_the_claim_name_is_configurable(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "viewer"}}, OIDC_GROUPS_CLAIM="roles")
    assert _ok(_sign_in(fake, **_groups("ops"))[1])  # "groups" is not the claim now
    assert "alice" not in _members(ops)
    assert _ok(_sign_in(fake, claims={"roles": ["ops"]})[1])
    assert _members(ops)["alice"] == ("viewer", "oidc")


def test_groups_are_compared_exactly(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"/Org/Ops": {"Ops": "operator"}})
    for near in ["/org/ops", "Ops", "/Org/Ops/", "/Org/Ops "]:
        assert _ok(_sign_in(fake, **_groups(near))[1])
        assert "alice" not in _members(ops), near
    assert _ok(_sign_in(fake, **_groups("/Org/Ops"))[1])
    assert _members(ops)["alice"] == ("operator", "oidc")


def test_memberships_set_by_hand_or_by_github_are_never_touched(sso, monkeypatch) -> None:
    fake, admin = sso
    alice = _provision(admin, "alice", "alice@example.com")
    by_hand, by_github = _project(admin, "ByHand"), _project(admin, "ByGithub")
    assert admin.put(f"/api/projects/{by_hand}/members/{alice}", json={"role": "viewer"}).is_success
    db = get_sessionmaker()()
    db.add(ProjectMember(project_id=by_github, user_id=alice, role="viewer", granted_by="github"))
    db.commit()
    db.close()
    _map(monkeypatch, {"ops": {"ByHand": "admin", "ByGithub": "admin"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert _members(by_hand)["alice"] == ("viewer", None)
    assert _members(by_github)["alice"] == ("viewer", "github")
    assert sorted(_audit(admin, "auth.login")[0]["detail"]["kept_manual"]) == sorted(
        [by_hand, by_github]
    )
    assert _ok(_sign_in(fake, **_groups())[1])
    assert _members(by_hand)["alice"] == ("viewer", None)
    assert _members(by_github)["alice"] == ("viewer", "github")


def test_unknown_project_names_are_skipped_and_audited(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _map(monkeypatch, {"ops": {"Gone": "viewer", "Also gone": "admin"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert _audit(admin, "auth.login")[0]["detail"]["unknown_projects"] == ["Also gone", "Gone"]


def test_removing_the_map_removes_what_it_granted_at_the_next_sign_in(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert _members(ops)["alice"] == ("operator", "oidc")
    monkeypatch.delenv("OIDC_ROLE_MAP")
    get_settings.cache_clear()
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert "alice" not in _members(ops)


def test_without_a_map_the_groups_claim_is_not_even_read(sso) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    assert _ok(_sign_in(fake, claims={"groups": {"not": "a list"}})[1])


# ------------------------------------------------------------------ claims it can't trust


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"groups": "ops"}, "not a short list of strings"),
        ({"groups": {"ops": True}}, "not a short list of strings"),
        ({"groups": ["ops", 7]}, "not a short list of strings"),
        ({"groups": [f"g{n}" for n in range(1001)]}, "not a short list of strings"),
        # Entra: too many groups for the token, so it names a lookup instead of listing them.
        ({"_claim_names": {"groups": "src1"}, "_claim_sources": {}}, "overage"),
    ],
)
def test_a_claim_it_cannot_read_refuses_sign_in_and_keeps_access(
    sso, monkeypatch, claims, reason
) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    browser, response = _sign_in(fake, claims=claims)
    assert _refused(response, "failed")
    assert browser.get("/api/auth/me").status_code == 401
    assert _members(ops)["alice"] == ("operator", "oidc")  # a refusal changes nothing
    failure = next(e for e in _audit(admin, "auth.sso") if e["outcome"] == "failure")
    assert reason in failure["detail"]["reason"]


def test_a_refused_claim_does_not_link_a_new_identity(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})
    assert _refused(_sign_in(fake, claims={"groups": "ops"})[1], "failed")
    assert not _audit(admin, "auth.sso_link")


def test_a_failed_sync_ends_without_a_session(sso, monkeypatch) -> None:
    from sqlalchemy.exc import OperationalError

    from app.routers import sso as sso_router

    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})

    def broken(*_args, **_kwargs):
        raise OperationalError("UPDATE", {}, Exception("database went away"))

    monkeypatch.setattr(sso_router, "sync_managed_memberships", broken)
    browser, response = _sign_in(fake, **_groups("ops"))
    assert _refused(response, "failed")
    assert browser.get("/api/auth/me").status_code == 401


# --------------------------------------------------- password sign-ins, edits, unlinking


def _oidc_operator(admin: TestClient, fake: FakeOidc, monkeypatch) -> tuple[int, int]:
    alice = _provision(admin, "alice", "alice@example.com")
    ops = _project(admin, "Ops")
    _map(monkeypatch, {"ops": {"Ops": "operator"}})
    assert _ok(_sign_in(fake, **_groups("ops"))[1])
    assert _members(ops)["alice"] == ("operator", "oidc")
    return alice, ops


def test_a_password_sign_in_drops_oidc_granted_memberships(sso, monkeypatch) -> None:
    fake, admin = sso
    _alice, ops = _oidc_operator(admin, fake, monkeypatch)
    login = TestClient(admin.app).post(
        "/api/auth/login", json={"username": "alice", "password": "a-long-test-password-1"}
    )
    assert login.status_code == 200, login.text
    assert "alice" not in _members(ops)
    removed = _audit(admin, "project.member_remove")[0]
    assert removed["actor_username"] == "alice" and removed["detail"]["via"] == "password sign-in"
    assert _ok(_sign_in(fake, **_groups("ops"))[1])  # and back at the next SSO sign-in
    assert _members(ops)["alice"] == ("operator", "oidc")


def test_setting_a_managed_membership_by_hand_makes_it_manual(sso, monkeypatch) -> None:
    fake, admin = sso
    alice, ops = _oidc_operator(admin, fake, monkeypatch)
    members = admin.get(f"/api/projects/{ops}/members").json()
    assert [m["granted_by"] for m in members if m["username"] == "alice"] == ["oidc"]
    same = admin.put(f"/api/projects/{ops}/members/{alice}", json={"role": "operator"})
    assert same.status_code == 200 and same.json()["granted_by"] is None
    assert _ok(_sign_in(fake, **_groups())[1])
    assert _members(ops)["alice"] == ("operator", None)


def test_unlinking_the_identity_drops_what_it_granted(sso, monkeypatch) -> None:
    fake, admin = sso
    alice, ops = _oidc_operator(admin, fake, monkeypatch)
    assert admin.delete(f"/api/users/{alice}/sso-link").status_code == 204
    assert "alice" not in _members(ops)
