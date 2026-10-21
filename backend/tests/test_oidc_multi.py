"""Several OpenID Connect providers at once (OIDC_PROVIDERS): per-provider URLs, cookies, role
maps, logout and email domains; one identity per user; a token or cookie never works at another
provider; and the single-provider settings (the provider "oidc") keep their original URLs."""

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import oidc
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.main import app
from app.models import ProjectMember, User
from tests.fake_oidc import FakeOidc
from tests.test_projects import _project
from tests.test_sso import _admin, _audit, _ok, _provision, _refused

A = ("https://a.test", "client-a", "secret-a")
B = ("https://b.test", "client-b", "secret-b")


def _providers(**b_extra) -> list[dict]:
    return [
        {"slug": "keycloak", "issuer": A[0], "client_id": A[1], "client_secret": A[2],
         "button_label": "Keycloak"},
        {"slug": "google", "issuer": B[0], "client_id": B[1], "client_secret": B[2],
         "button_label": "Google", **b_extra},
    ]  # fmt: skip


@pytest.fixture
def two(monkeypatch):
    """Two providers, each backed by its own fake. Returns (fake A, fake B, set_providers)."""
    fake_a, fake_b = FakeOidc(*A), FakeOidc(*B)
    by_host = {"a.test": fake_a, "b.test": fake_b}

    def handler(request: httpx.Request) -> httpx.Response:
        return by_host[request.url.host].handle(request)

    def configure(providers: list[dict]) -> None:
        monkeypatch.setenv("OIDC_PROVIDERS", json.dumps(providers))
        get_settings.cache_clear()

    monkeypatch.setenv("PUBLIC_URL", "http://testserver")
    configure(_providers())
    monkeypatch.setattr(
        oidc, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    oidc.clear_caches()
    fake_a.configure, fake_b.configure = configure, configure
    return fake_a, fake_b


@pytest.fixture
def multi(two, client: TestClient):
    fake_a, fake_b = two
    return fake_a, fake_b, _admin(client)


def _sign_in(fake: FakeOidc, slug: str, browser: TestClient | None = None, **identity):
    browser = browser or TestClient(app)
    start = browser.get(f"/api/auth/oidc/{slug}/login", follow_redirects=False)
    assert start.status_code == 302, start.text
    location = start.headers["location"]
    code = fake.authorize(location, **identity)
    state = parse_qs(urlparse(location).query)["state"][0]
    response = browser.get(
        f"/api/auth/oidc/{slug}/callback",
        params={"code": code, "state": state},
        follow_redirects=False,
    )
    return browser, response


def _members(project_id: int) -> dict[str, tuple[str, str | None]]:
    db = get_sessionmaker()()
    try:
        rows = (
            db.query(User.username, ProjectMember.role, ProjectMember.granted_by)
            .join(User, User.id == ProjectMember.user_id)
            .filter(ProjectMember.project_id == project_id)
            .all()
        )
        return {name: (role, by) for name, role, by in rows}
    finally:
        db.close()


# --------------------------------------------------------------------- configuration

BASE = {"public_url": "http://x"}


def _settings(providers, **more) -> Settings:
    return Settings(**BASE, oidc_providers=providers, **more)


def test_each_provider_names_its_own_verified_email_claim(two, client: TestClient) -> None:
    fake_a, fake_b = two
    fake_a.configure([_providers()[0], {**_providers()[1], "email_verified_claim": "xms_edov"}])
    admin = _admin(client)
    _provision(admin, "alice", "alice@example.com")
    _provision(admin, "bob", "bob@example.com")
    # Provider B (named claim) accepts xms_edov and ignores email_verified; A is unchanged.
    assert _ok(
        _sign_in(
            fake_b, "google", sub="b", email="bob@example.com", email_verified=None,
            claims={"xms_edov": True},
        )[1]
    )  # fmt: skip
    assert _refused(
        _sign_in(fake_b, "google", sub="b", email="bob@example.com", email_verified=True)[1],
        "not_linked",
    )
    assert _refused(
        _sign_in(
            fake_a, "keycloak", sub="a", email="alice@example.com", email_verified=None,
            claims={"xms_edov": True},
        )[1],
        "not_linked",
    )  # fmt: skip
    assert _ok(_sign_in(fake_a, "keycloak", sub="a", email="alice@example.com")[1])


def test_the_providers_are_validated_and_the_secret_stays_hidden() -> None:
    settings = _settings(_providers(allowed_email_domains=[" Corp.Example ", "corp.example"]))
    assert [p.slug for p in settings.oidc_provider_list] == ["keycloak", "google"]
    assert settings.oidc_provider("google").allowed_email_domains == ["corp.example"]
    assert settings.oidc_enabled and settings.oidc_provider("nope") is None
    assert "secret-a" not in repr(settings.oidc_provider_list) and "secret-a" not in str(
        settings.oidc_providers
    )

    def one(**changes) -> list[dict]:
        return [{**_providers()[0], **changes}]

    for bad, message in (
        ([*_providers(), _providers()[0]], "same slug twice"),
        ([_providers()[0], {**_providers()[1], "issuer": A[0] + "/"}], "same issuer twice"),
        (one(slug="github"), "slug"),
        (one(slug="login"), "slug"),
        (one(slug="Has Space"), "slug"),
        (one(slug="x" * 33), "slug"),
        (one(issuer="ftp://idp"), "https"),
        (one(client_secret=""), "client_secret is empty"),
        (one(client_id=""), "client_id"),
        (one(role_map={"g": {"P": "owner"}}), "role_map"),
        (one(allowed_email_domains=["not a domain"]), "allowed_email_domains"),
        (one(allowed_email_domains=[]), "allowed_email_domains"),
        (one(typo_field=1), "typo_field"),
        (
            [dict(_providers()[0], slug=f"p{n}", issuer=f"https://i{n}.test") for n in range(9)],
            "more than 8",
        ),
    ):
        with pytest.raises(ValidationError, match=message) as raised:
            _settings(bad)
        assert "secret-a" not in str(raised.value)  # rejected values stay out of the logs


def test_the_list_replaces_the_single_provider_settings_and_needs_public_url() -> None:
    with pytest.raises(ValidationError, match="replaces OIDC_ISSUER"):
        _settings(_providers(), oidc_issuer="https://x", oidc_client_id="c", oidc_client_secret="s")
    with pytest.raises(ValidationError, match="replaces OIDC_ISSUER"):
        _settings(_providers(), oidc_role_map={"g": {"P": "viewer"}})
    with pytest.raises(ValidationError, match="PUBLIC_URL"):
        Settings(oidc_providers=_providers())
    with pytest.raises(ValidationError, match="requires https"):
        Settings(
            oidc_providers=[{**_providers()[0], "issuer": "http://a.test"}],
            public_url="https://x.example",
            environment="production",
            auth_secret_key="a-real-secret-value-of-32-characters",
            admin_password="a-real-admin-password",
        )


def test_the_single_provider_settings_are_a_provider_called_oidc() -> None:
    settings = Settings(
        **BASE, oidc_issuer="https://i.test", oidc_client_id="c", oidc_client_secret="s",
        oidc_button_label="Acme", oidc_role_map={"g": {"P": "viewer"}}, oidc_provider_logout=True,
    )  # fmt: skip
    (only,) = settings.oidc_provider_list
    assert (only.slug, only.legacy, only.button_label, only.provider_logout) == (
        "oidc",
        True,
        "Acme",
        True,
    )
    assert only.role_map == {"g": {"P": "viewer"}} and only.client_secret.get_secret_value() == "s"


def test_the_settings_are_read_as_json_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_URL", "http://x")
    monkeypatch.setenv("OIDC_PROVIDERS", json.dumps(_providers()))
    assert [p.slug for p in Settings(_env_file=None).oidc_provider_list] == ["keycloak", "google"]


# ------------------------------------------------------------------------ signing in


def test_the_login_page_lists_the_providers_without_secrets(multi, client: TestClient) -> None:
    body = TestClient(app).get("/api/auth/providers").json()
    assert body["oidc_providers"] == [
        {"slug": "keycloak", "label": "Keycloak"},
        {"slug": "google", "label": "Google"},
    ]
    assert body["oidc"] == {"enabled": True, "label": "Keycloak"}
    assert "secret-a" not in json.dumps(body) and "client-a" not in json.dumps(body)


def test_each_provider_signs_in_its_own_users_with_its_own_redirect_uri(multi) -> None:
    fake_a, fake_b, admin = multi
    _provision(admin, "alice", "alice@example.com")
    _provision(admin, "bob", "bob@example.com")
    browser = TestClient(app)
    start = browser.get("/api/auth/oidc/google/login", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert start.headers["location"].startswith("https://b.test/authorize?")
    assert query["client_id"] == ["client-b"]
    assert query["redirect_uri"] == ["http://testserver/api/auth/oidc/google/callback"]
    cookie = start.headers["set-cookie"].lower()
    assert "steerhouse_oidc_google=" in cookie and "path=/api/auth/oidc/google" in cookie

    _, in_a = _sign_in(fake_a, "keycloak", sub="a-1", email="alice@example.com")
    _, in_b = _sign_in(fake_b, "google", sub="b-1", email="bob@example.com")
    assert _ok(in_a) and _ok(in_b)
    db = get_sessionmaker()()
    try:
        linked = {u.username: (u.sso_issuer, u.sso_subject) for u in db.query(User)}
    finally:
        db.close()
    assert linked["alice"] == (A[0], "a-1") and linked["bob"] == (B[0], "b-1")
    shown = {u["username"]: u["sso_provider"] for u in admin.get("/api/users").json()}
    assert (shown["alice"], shown["bob"]) == ("Keycloak", "Google")  # the Users page names it


def test_a_user_linked_to_one_provider_is_refused_by_the_other(multi) -> None:
    fake_a, fake_b, admin = multi
    _provision(admin, "alice", "alice@example.com")
    assert _ok(_sign_in(fake_a, "keycloak", sub="a-1", email="alice@example.com")[1])
    browser, refused = _sign_in(fake_b, "google", sub="b-1", email="alice@example.com")
    assert _refused(refused, "not_linked")
    assert browser.get("/api/auth/me").status_code == 401
    db = get_sessionmaker()()
    try:
        alice = db.query(User).filter(User.username == "alice").one()
        assert (alice.sso_issuer, alice.sso_subject) == (A[0], "a-1")  # not re-linked
    finally:
        db.close()
    # Unlinking frees the account for whichever provider comes first.
    alice_id = _admin_user_id(admin, "alice")
    assert admin.delete(f"/api/users/{alice_id}/sso-link").status_code == 204
    assert _ok(_sign_in(fake_b, "google", sub="b-1", email="alice@example.com")[1])


def _admin_user_id(admin: TestClient, username: str) -> int:
    return next(u["id"] for u in admin.get("/api/users").json() if u["username"] == username)


def test_a_state_cookie_from_one_provider_is_useless_at_another(multi) -> None:
    _fake_a, fake_b, admin = multi
    _provision(admin, "alice", "alice@example.com")
    victim = TestClient(app)
    start = victim.get("/api/auth/oidc/keycloak/login", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    stolen = victim.cookies["steerhouse_oidc_keycloak"]
    # A code from the other provider (any browser can get one)...
    bystander = TestClient(app)
    other_login = bystander.get("/api/auth/oidc/google/login", follow_redirects=False)
    code = fake_b.authorize(other_login.headers["location"])
    # ...played at its callback with the first provider's cookie and state, set last.
    attacker = TestClient(app)
    attacker.cookies.set("steerhouse_oidc_google", stolen, path="/api/auth/oidc/google")
    response = attacker.get(
        "/api/auth/oidc/google/callback",
        params={"code": code, "state": state},
        follow_redirects=False,
    )
    assert _refused(response, "failed")
    assert fake_b.token_requests == 0  # it never got as far as asking the provider
    reason = next(e for e in _audit(admin, "auth.sso") if e["outcome"] == "failure")["detail"][
        "reason"
    ]
    assert "state cookie" in reason


def test_an_id_token_issued_for_another_provider_is_refused(multi) -> None:
    fake_a, _fake_b, admin = multi
    _provision(admin, "alice", "alice@example.com")
    forged = lambda claims: fake_a.sign({**claims, "iss": B[0]})  # noqa: E731
    _, response = _sign_in(fake_a, "keycloak", email="alice@example.com", forge=forged)
    assert _refused(response, "failed")
    wrong_audience = lambda claims: fake_a.sign({**claims, "aud": B[1]})  # noqa: E731
    assert _refused(
        _sign_in(fake_a, "keycloak", email="alice@example.com", forge=wrong_audience)[1], "failed"
    )


def test_an_unknown_provider_is_a_404_like_sso_that_is_off(multi) -> None:
    client = TestClient(app)
    for path in ("nope/login", "nope/callback", "oidc/login", "oidc/callback"):
        assert client.get(f"/api/auth/oidc/{path}", follow_redirects=False).status_code == 404


def test_the_audit_log_names_the_provider(multi) -> None:
    fake_a, fake_b, admin = multi
    _provision(admin, "alice", "alice@example.com")
    assert _ok(_sign_in(fake_b, "google", sub="b-1", email="alice@example.com")[1])
    login = _audit(admin, "auth.login")[0]
    assert login["detail"]["provider"] == "google" and login["detail"]["method"] == "sso"
    assert _audit(admin, "auth.sso_link")[0]["detail"]["provider"] == "google"
    _sign_in(fake_a, "keycloak", sub="x", email="nobody@example.com")
    failure = next(e for e in _audit(admin, "auth.sso") if e["outcome"] == "failure")
    assert failure["detail"]["provider"] == "keycloak"


# ------------------------------------------------------- per-provider role maps, logout


def test_each_provider_has_its_own_role_map_and_groups_claim(two, client: TestClient) -> None:
    fake_a, fake_b = two
    fake_a.configure(
        [
            {**_providers()[0], "role_map": {"ops": {"Ops": "viewer"}}},
            {**_providers()[1], "role_map": {"ops": {"Ops": "admin"}}, "groups_claim": "roles"},
        ]
    )
    admin = _admin(client)
    _provision(admin, "alice", "alice@example.com")
    _provision(admin, "bob", "bob@example.com")
    ops = _project(admin, "Ops")
    claims = {"groups": ["ops"], "roles": ["ops"]}
    assert _ok(_sign_in(fake_a, "keycloak", sub="a", email="alice@example.com", claims=claims)[1])
    assert _members(ops)["alice"] == ("viewer", "oidc")
    assert _ok(_sign_in(fake_b, "google", sub="b", email="bob@example.com", claims=claims)[1])
    assert _members(ops)["bob"] == ("admin", "oidc")
    # A claim the provider doesn't read doesn't count.
    assert _ok(
        _sign_in(fake_b, "google", sub="b", email="bob@example.com", claims={"groups": ["ops"]})[1]
    )
    assert "bob" not in _members(ops)
    added = {
        e["actor_username"]: e["detail"]["via"]
        for e in _audit(admin, "project.member_add")
        if "via" in e["detail"]
    }
    assert added == {
        "(oidc:keycloak group sync)": "oidc:keycloak group ops",
        "(oidc:google group sync)": "oidc:google group ops",
    }


def test_logout_goes_to_the_provider_the_user_signed_in_through(two, client: TestClient) -> None:
    fake_a, fake_b = two
    fake_a.configure([_providers()[0], {**_providers()[1], "provider_logout": True}])
    admin = _admin(client)
    _provision(admin, "alice", "alice@example.com")
    _provision(admin, "bob", "bob@example.com")
    browser_a, _ = _sign_in(fake_a, "keycloak", sub="a", email="alice@example.com")
    assert browser_a.post("/api/auth/logout").json()["redirect"] is None  # off for this one
    browser_b, _ = _sign_in(fake_b, "google", sub="b", email="bob@example.com")
    redirect = browser_b.post("/api/auth/logout").json()["redirect"]
    assert redirect.startswith("https://b.test/logout?") and "client_id=client-b" in redirect


# ---------------------------------------------------------------------- email domains


def test_a_providers_domains_narrow_the_global_list_and_never_widen_it(
    two, client: TestClient, monkeypatch
) -> None:
    fake_a, fake_b = two
    fake_a.configure(
        [
            _providers()[0],
            {**_providers()[1], "allowed_email_domains": ["corp.example", "evil.example"]},
        ]
    )
    admin = _admin(client)
    _provision(admin, "carol", "carol@corp.example")
    _provision(admin, "dave", "dave@evil.example")
    _provision(admin, "erin", "erin@example.com")
    # Only the provider's list: corp and evil sign in through it, example.com does not.
    assert _refused(_sign_in(fake_b, "google", sub="e", email="erin@example.com")[1], "not_linked")
    assert _ok(_sign_in(fake_b, "google", sub="c", email="carol@corp.example")[1])
    # Provider A has no list of its own: everything is allowed there.
    assert _ok(_sign_in(fake_a, "keycloak", sub="e2", email="erin@example.com")[1])
    # With a global list too, the provider gets the overlap only.
    monkeypatch.setenv("SSO_ALLOWED_EMAIL_DOMAINS", '["corp.example"]')
    get_settings.cache_clear()
    assert _refused(_sign_in(fake_b, "google", sub="d", email="dave@evil.example")[1], "not_linked")


# ------------------------------------------------------ the original, single-provider URLs


def test_the_provider_called_oidc_keeps_the_original_urls_and_cookie(
    two, client: TestClient
) -> None:
    fake_a, _fake_b = two
    fake_a.configure([{**_providers()[0], "slug": "oidc"}, _providers()[1]])
    admin = _admin(client)
    _provision(admin, "alice", "alice@example.com")
    browser = TestClient(app)
    start = browser.get("/api/auth/oidc/login", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["redirect_uri"] == ["http://testserver/api/auth/oidc/callback"]  # as registered
    assert (
        "steerhouse_oidc=" in start.headers["set-cookie"]
        and "path=/api/auth/oidc;" in start.headers["set-cookie"].lower()
    )
    code = fake_a.authorize(start.headers["location"], email="alice@example.com")
    response = browser.get(
        "/api/auth/oidc/callback",
        params={"code": code, "state": query["state"][0]},
        follow_redirects=False,
    )
    assert _ok(response)
    assert _audit(admin, "auth.login")[0]["detail"] == {
        "method": "sso"
    }  # no provider tag: unchanged
    # And the new-style URL reaches the same provider.
    assert _ok(_sign_in(fake_a, "oidc", sub="user-1", email="alice@example.com")[1])
