"""The credential encryption key wrapped by the secret store's Transit engine
(CREDENTIAL_ENCRYPTION_KEY_WRAPPED): unwrapped into memory, a locked key while the store is
away, the maintenance commands, and nothing of the key in logs or errors."""

# ruff: noqa: F811 - tests take the `store` fixture imported below

import base64
import io
import logging

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import crypto, secret_store
from app.cli import main as cli
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.main import _probe_secret_store
from app.models import Credential
from app.secret_store import KeyLocked
from tests.test_runs import _generate_key_pem, _login
from tests.test_secret_store import ROOT, store  # noqa: F401

DECRYPT = "/v1/transit/decrypt/steerhouse"
NEW_KEY, OLD_KEY = Fernet.generate_key().decode(), Fernet.generate_key().decode()


def _wrap(keys: str, version: int = 1) -> str:
    return f"vault:v{version}:{base64.b64encode(keys.encode()).decode()}"


@pytest.fixture
def wrapped(store, monkeypatch):
    """The store, with the Fernet key held only as a Transit ciphertext."""
    ciphertext = _wrap(NEW_KEY)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", ciphertext)
    monkeypatch.setattr(crypto, "UNLOCK_RETRY_SECONDS", 0.0)
    get_settings.cache_clear()
    secret_store.reset()
    store["wrapped"] = ciphertext
    return store


def _decrypt_calls(store: dict) -> int:
    return sum(1 for request in store["requests"] if request.url.raw_path.decode() == DECRYPT)


# --------------------------------------------------------------------- configuration


def test_exactly_one_key_source_is_required(store, monkeypatch) -> None:
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY")  # the suite's own
    base = {"secrets_store_url": ROOT, "secrets_store_token_file": __file__}
    plain = Fernet.generate_key().decode()
    assert Settings(**base, credential_encryption_key=plain).credential_encryption_keys == [plain]
    wrapped = Settings(**base, credential_encryption_key_wrapped=_wrap(NEW_KEY))
    assert wrapped.credential_encryption_keys == []  # app.crypto.encryption_keys() unwraps them
    for bad, message in (
        ({}, "exactly one"),
        (
            {
                "credential_encryption_key": plain,
                "credential_encryption_key_wrapped": _wrap(NEW_KEY),
            },
            "exactly one",
        ),
        ({"credential_encryption_key_wrapped": "not-a-ciphertext"}, "Transit ciphertext"),
        ({"credential_encryption_key_wrapped": "vault:v1:"}, "Transit ciphertext"),
        (
            {
                "credential_encryption_key_wrapped": _wrap(NEW_KEY),
                "secrets_store_transit_key": "a/b",
            },
            "TRANSIT_KEY",
        ),
        (
            {
                "credential_encryption_key_wrapped": _wrap(NEW_KEY),
                "secrets_store_transit_mount": "..",
            },
            "TRANSIT_MOUNT",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            Settings(**base, **bad)
    monkeypatch.delenv("SECRETS_STORE_URL")
    with pytest.raises(ValidationError, match="needs SECRETS_STORE_URL"):
        Settings(credential_encryption_key_wrapped=_wrap(NEW_KEY))


# ------------------------------------------------------------------------ unwrapping


def test_the_keys_are_unwrapped_once_and_kept_in_memory(wrapped) -> None:
    assert crypto.encryption_keys() == [NEW_KEY]
    token = crypto.encrypt_secret(b"hello")
    assert Fernet(NEW_KEY).decrypt(token) == b"hello"
    crypto.encryption_keys()
    assert _decrypt_calls(wrapped) == 1
    assert crypto.key_state() == {"key_wrapped": True, "key_locked": False, "key_error": None}


def test_a_list_of_keys_keeps_its_order_for_rotation(wrapped, monkeypatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", _wrap(f"{NEW_KEY},{OLD_KEY}"))
    get_settings.cache_clear()
    assert crypto.encryption_keys() == [NEW_KEY, OLD_KEY]
    old = Fernet(OLD_KEY).encrypt(b"from before")
    assert crypto.decrypt_secret(old) == b"from before"  # an old key still decrypts
    assert Fernet(NEW_KEY).decrypt(crypto.encrypt_secret(b"x")) == b"x"  # the first encrypts


def test_a_changed_wrapped_value_is_unwrapped_again(wrapped, monkeypatch) -> None:
    assert crypto.encryption_keys() == [NEW_KEY]
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", _wrap(OLD_KEY))
    get_settings.cache_clear()
    assert crypto.encryption_keys() == [OLD_KEY]


def test_the_login_needs_only_decrypt_on_the_key(wrapped) -> None:
    crypto.encryption_keys()
    assert wrapped["transit_calls"] == [("decrypt", "tok-sentinel-1")]


# ------------------------------------------------------------------- a locked key


def test_a_store_that_is_away_locks_the_key_and_recovery_unlocks_it(wrapped) -> None:
    wrapped["status"][DECRYPT] = (503, {"errors": ["Vault is sealed"]})
    with pytest.raises(KeyLocked) as locked:
        crypto.encrypt_secret(b"x")
    assert locked.value.kind == "key_locked" and locked.value.reason == "sealed"
    assert crypto.key_state() == {"key_wrapped": True, "key_locked": True, "key_error": "sealed"}
    assert crypto.unlock() is False
    del wrapped["status"][DECRYPT]
    assert crypto.unlock() is True
    assert Fernet(NEW_KEY).decrypt(crypto.encrypt_secret(b"x")) == b"x"
    assert crypto.key_state()["key_locked"] is False


def test_a_request_that_needs_a_locked_key_retries_at_most_every_few_seconds(
    wrapped, monkeypatch
) -> None:
    monkeypatch.setattr(crypto, "UNLOCK_RETRY_SECONDS", 3600.0)
    wrapped["status"][DECRYPT] = (503, {"errors": ["down"]})
    for _ in range(5):
        with pytest.raises(KeyLocked):
            crypto.encryption_keys()
    assert _decrypt_calls(wrapped) == 1


@pytest.mark.parametrize(
    ("answer", "reason"),
    [((403, {"errors": ["permission denied"]}), "denied"), ((404, {}), "not_found")],
)
def test_a_store_that_refuses_says_why(wrapped, answer, reason) -> None:
    wrapped["status"][DECRYPT] = answer
    with pytest.raises(KeyLocked) as locked:
        crypto.encryption_keys()
    assert locked.value.reason == reason


@pytest.mark.parametrize(
    "plaintext", ["not a fernet key", f"{NEW_KEY},{NEW_KEY}", "", NEW_KEY[:-2]]
)
def test_something_that_is_not_a_key_list_never_unlocks_and_is_never_shown(
    wrapped, monkeypatch, caplog, plaintext
) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", _wrap(plaintext or " "))
    get_settings.cache_clear()
    with caplog.at_level(logging.DEBUG), pytest.raises(KeyLocked) as locked:
        crypto.encryption_keys()
    assert locked.value.reason == "bad_response"
    for text in (plaintext, NEW_KEY[:20]):
        if text:
            assert text not in caplog.text and text not in str(locked.value)


def test_the_unwrapped_key_never_reaches_a_log(wrapped, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        crypto.encryption_keys()
        crypto.encryption_keys()
    assert NEW_KEY not in caplog.text and NEW_KEY[:20] not in caplog.text


# ------------------------------------------------------------------------ the API


def test_the_api_works_around_a_locked_key_and_recovers(wrapped, client: TestClient) -> None:
    _login(client)  # signing in with a password needs no key
    wrapped["status"][DECRYPT] = (503, {"errors": ["Vault is sealed"]})
    refused = client.post(
        "/api/credentials", json={"name": "k", "private_key": _generate_key_pem()}
    )
    assert refused.status_code == 503
    assert "locked" in refused.json()["detail"] and refused.headers["retry-after"] == "10"
    assert NEW_KEY not in refused.text
    del wrapped["status"][DECRYPT]
    created = client.post(
        "/api/credentials", json={"name": "k", "private_key": _generate_key_pem()}
    )
    assert created.status_code == 201, created.text
    db = get_sessionmaker()()
    try:
        row = db.get(Credential, created.json()["id"])
        assert Fernet(NEW_KEY).decrypt(row.encrypted_private_key).startswith(b"-----BEGIN")
    finally:
        db.close()


def test_the_status_api_says_whether_the_key_is_unwrapped(wrapped, client: TestClient) -> None:
    _login(client)
    wrapped["status"][DECRYPT] = (403, {"errors": ["permission denied"]})
    with pytest.raises(KeyLocked):
        crypto.encryption_keys()
    status = client.get("/api/secret-store/status").json()
    assert (status["key_wrapped"], status["key_locked"], status["key_error"]) == (
        True,
        True,
        "denied",
    )
    del wrapped["status"][DECRYPT]
    crypto.encryption_keys()
    status = client.get("/api/secret-store/status").json()
    assert (status["key_wrapped"], status["key_locked"], status["key_error"]) == (True, False, None)


def test_a_plaintext_key_reports_nothing_wrapped(store, client: TestClient) -> None:
    _login(client)
    status = client.get("/api/secret-store/status").json()
    assert (status["key_wrapped"], status["key_locked"], status["key_error"]) == (False, None, None)


def test_the_probe_keeps_trying_and_records_a_locked_key_as_an_outage(wrapped, client) -> None:
    from app import store_outage

    wrapped["status"]["/v1/sys/health"] = (200, {"sealed": False, "version": "2.7.1"})
    wrapped["status"]["/v1/auth/token/lookup-self"] = (200, {"data": {"ttl": 1200}})
    wrapped["status"][DECRYPT] = (503, {"errors": ["down"]})
    assert _probe_secret_store() is False
    db = get_sessionmaker()()
    try:
        assert store_outage.current(db).kind == "key_locked"
    finally:
        db.close()
    del wrapped["status"][DECRYPT]
    assert _probe_secret_store() is True
    assert crypto.key_state()["key_locked"] is False


# ------------------------------------------------------------------ the commands


def _stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_wrap_key_prints_a_ciphertext_that_unlocks(store, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BAO_TOKEN", "operator-token")
    _stdin(monkeypatch, f"{NEW_KEY},{OLD_KEY}\n")
    assert cli(["wrap-key"]) == 0
    ciphertext = capsys.readouterr().out.strip()
    assert ciphertext.startswith("vault:v1:") and NEW_KEY not in ciphertext
    assert store["transit_calls"] == [
        ("encrypt", "operator-token")
    ]  # its own token, not Steerhouse's
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", ciphertext)
    get_settings.cache_clear()
    assert crypto.encryption_keys() == [NEW_KEY, OLD_KEY]


def test_wrap_key_refuses_without_a_token_or_with_something_that_is_not_keys(
    store, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("BAO_TOKEN", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    _stdin(monkeypatch, NEW_KEY)
    assert cli(["wrap-key"]) == 1 and "BAO_TOKEN" in capsys.readouterr().err
    monkeypatch.setenv("VAULT_TOKEN", "operator-token")
    _stdin(monkeypatch, "definitely not a key")
    assert cli(["wrap-key"]) == 1
    err = capsys.readouterr().err
    assert "Nothing was wrapped" in err and "definitely" not in err
    assert "transit_calls" not in store  # nothing was sent


def test_rewrap_key_moves_to_the_latest_key_version(wrapped, monkeypatch, capsys) -> None:
    wrapped["transit_version"] = 2  # the Transit key was rotated
    monkeypatch.setenv("BAO_TOKEN", "operator-token")
    assert cli(["rewrap-key"]) == 0
    rewrapped = capsys.readouterr().out.strip()
    assert rewrapped.startswith("vault:v2:") and NEW_KEY not in rewrapped
    assert wrapped["transit_calls"][-1] == ("rewrap", "operator-token")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", rewrapped)
    get_settings.cache_clear()
    assert crypto.encryption_keys() == [NEW_KEY]


def test_reencrypt_secrets_works_on_wrapped_keys_and_refuses_while_locked(
    wrapped, client: TestClient, monkeypatch, capsys
) -> None:
    _login(client)
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", _wrap(OLD_KEY))
    get_settings.cache_clear()
    created = client.post(
        "/api/credentials", json={"name": "k", "private_key": _generate_key_pem()}
    )
    assert created.status_code == 201, created.text
    # Rotation: the new key first, the old one after it, wrapped together.
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_WRAPPED", _wrap(f"{NEW_KEY},{OLD_KEY}"))
    get_settings.cache_clear()
    wrapped["status"][DECRYPT] = (503, {"errors": ["down"]})
    assert cli(["reencrypt-secrets"]) == 1
    assert "Nothing was changed" in capsys.readouterr().err
    del wrapped["status"][DECRYPT]
    assert cli(["reencrypt-secrets"]) == 0
    out = capsys.readouterr().out
    assert "Re-encrypted 1" in out and "wrap-key" in out
    db = get_sessionmaker()()
    try:
        row = db.get(Credential, created.json()["id"])
        assert Fernet(NEW_KEY).decrypt(row.encrypted_private_key).startswith(b"-----BEGIN")
    finally:
        db.close()
