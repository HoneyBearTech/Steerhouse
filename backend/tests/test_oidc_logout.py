"""Logging out of Steerhouse can end the OIDC provider's session too (OIDC_PROVIDER_LOGOUT)."""

# ruff: noqa: F811 - tests take the fixtures imported below

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app import oidc
from app.config import get_settings
from app.main import app
from tests.fake_oidc import CLIENT_ID, ISSUER
from tests.test_sso import PASSWORD, _audit, _ok, _provision, _sign_in, fake, sso  # noqa: F401


def _enable(monkeypatch, value: str = "true") -> None:
    monkeypatch.setenv("OIDC_PROVIDER_LOGOUT", value)
    get_settings.cache_clear()


def _logout(browser: TestClient) -> dict:
    response = browser.post("/api/auth/logout")
    assert response.status_code == 200, response.text
    return response.json()


def test_an_oidc_session_is_sent_on_to_the_provider(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _enable(monkeypatch)
    browser, response = _sign_in(fake)
    assert _ok(response)
    body = _logout(browser)
    assert body["ok"] is True
    url = urlsplit(body["redirect"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/logout"
    query = parse_qs(url.query)
    assert query == {
        "client_id": [CLIENT_ID],
        "post_logout_redirect_uri": ["http://testserver/login"],
    }
    assert browser.get("/api/auth/me").status_code == 401  # signed out here either way
    assert _audit(admin, "auth.logout")[0]["detail"] == {"provider_logout": True}


def test_it_is_off_unless_the_owner_turns_it_on(sso) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    browser, _ = _sign_in(fake)
    assert _logout(browser) == {"ok": True, "redirect": None}
    assert _audit(admin, "auth.logout")[0]["detail"] in (None, {})


def test_a_password_session_never_goes_to_the_provider(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _sign_in(fake)  # alice is linked to the provider...
    _enable(monkeypatch)
    browser = TestClient(app)
    login = browser.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    assert login.status_code == 200, login.text
    assert _logout(browser)["redirect"] is None  # ...but this session came from her password


def test_the_admin_who_logs_in_locally_is_not_sent_away(sso, monkeypatch) -> None:
    _fake, admin = sso
    _enable(monkeypatch)
    assert _logout(admin)["redirect"] is None


@pytest.mark.parametrize(
    "endpoint",
    [None, "http://idp.test/logout", "javascript:alert(1)", "/logout", "https://idp.test/x#frag"],
)
def test_an_endpoint_it_will_not_follow_means_a_plain_logout(sso, monkeypatch, endpoint) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _enable(monkeypatch)
    fake.end_session_endpoint = endpoint
    browser, response = _sign_in(fake)
    assert _ok(response)
    assert _logout(browser)["redirect"] is None
    assert browser.get("/api/auth/me").status_code == 401


def test_an_endpoint_with_a_query_gets_the_parameters_appended(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _enable(monkeypatch)
    fake.end_session_endpoint = f"{ISSUER}/logout?tenant=t1"
    browser, _ = _sign_in(fake)
    query = parse_qs(urlsplit(_logout(browser)["redirect"]).query)
    assert query["tenant"] == ["t1"] and query["client_id"] == [CLIENT_ID]


def test_a_provider_that_cannot_be_reached_does_not_stop_the_logout(sso, monkeypatch) -> None:
    fake, admin = sso
    _provision(admin, "alice", "alice@example.com")
    _enable(monkeypatch)
    browser, _ = _sign_in(fake)
    oidc.clear_caches()  # the next metadata read goes to the (now broken) provider

    def down() -> dict:
        raise httpx.ConnectError("provider is down")

    monkeypatch.setattr(fake, "metadata", down)
    body = _logout(browser)
    assert body == {"ok": True, "redirect": None}
    assert browser.get("/api/auth/me").status_code == 401
