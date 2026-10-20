import logging
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, MultiFernet

from app.config import get_settings

logger = logging.getLogger(__name__)

_password_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


# --- the Fernet keys: from CREDENTIAL_ENCRYPTION_KEY, or unwrapped by the secret store's
# Transit engine (CREDENTIAL_ENCRYPTION_KEY_WRAPPED), then held in this process's memory only.

UNLOCK_RETRY_SECONDS = 5.0  # a request that needs a locked key tries again at most this often

_unlock_lock = threading.Lock()


class _KeyState:
    unwrapped: tuple[str, list[str]] | None = None  # (the wrapped value it came from, the keys)
    last_error: str | None = None  # the error kind the last attempt ended in
    last_attempt: float | None = None  # monotonic


_state = _KeyState()


def forget_unwrapped_key() -> None:
    """Drop the unwrapped keys (tests, config changes): the next use unwraps again."""
    with _unlock_lock:
        _state.unwrapped = _state.last_error = _state.last_attempt = None


def key_state() -> dict:
    """For the status API: are the keys wrapped, is the process holding them, why not."""
    wrapped = bool(get_settings().credential_encryption_key_wrapped)
    return {
        "key_wrapped": wrapped,
        "key_locked": (_current_unwrapped() is None) if wrapped else None,
        "key_error": _state.last_error if wrapped and _current_unwrapped() is None else None,
    }


def _current_unwrapped() -> list[str] | None:
    cached = _state.unwrapped
    wrapped = get_settings().credential_encryption_key_wrapped
    return list(cached[1]) if cached is not None and cached[0] == wrapped else None


def unlock() -> bool:
    """Asks the store to unwrap the keys (a no-op for a plaintext key, or once unwrapped).
    Never raises; whether the keys are available. Another thread already unwrapping counts as
    not yet."""
    wrapped = get_settings().credential_encryption_key_wrapped
    if not wrapped or _current_unwrapped() is not None:
        return True
    if not _unlock_lock.acquire(blocking=False):
        return False
    try:
        from app import secret_store  # imports this module: not at the top

        _state.last_attempt = time.monotonic()
        try:
            keys = parse_keys(secret_store.transit_decrypt(wrapped))
        except secret_store.SecretStoreError as exc:
            _state.last_error = exc.kind
            logger.warning("the credential encryption key could not be unwrapped (%s)", exc.kind)
            return False
        _state.unwrapped, _state.last_error = (wrapped, keys), None
        logger.info("the credential encryption key was unwrapped by the secret store")
        return True
    finally:
        _unlock_lock.release()


def parse_keys(text: str) -> list[str]:
    from app.secret_store import SecretStoreError  # not at the top: it imports this module

    keys = [key.strip() for key in text.split(",") if key.strip()]
    try:
        for key in keys:
            Fernet(key)
    except ValueError:
        # Not a word of the content in the message: it is the key.
        raise SecretStoreError(
            "bad_response", "the unwrapped value is not a list of Fernet keys"
        ) from None
    if not keys or len(set(keys)) != len(keys):
        raise SecretStoreError("bad_response", "the unwrapped value is not a list of Fernet keys")
    return keys


def encryption_keys() -> list[str]:
    """The Fernet keys, the current one first. KeyLocked while the store has not unwrapped
    them (it tries again, at most every UNLOCK_RETRY_SECONDS, when something needs them)."""
    settings = get_settings()
    if not settings.credential_encryption_key_wrapped:
        return settings.credential_encryption_keys
    keys = _current_unwrapped()
    if keys is None and (
        _state.last_attempt is None
        or time.monotonic() - _state.last_attempt >= UNLOCK_RETRY_SECONDS
    ):
        unlock()
        keys = _current_unwrapped()
    if keys is None:
        from app.secret_store import KeyLocked

        raise KeyLocked(_state.last_error)
    return keys


def fernet() -> MultiFernet:
    """Encrypts with the first CREDENTIAL_ENCRYPTION_KEY, decrypts with any of them."""
    return MultiFernet([Fernet(key) for key in encryption_keys()])


def encrypt_secret(plaintext: bytes) -> bytes:
    return fernet().encrypt(plaintext)


def decrypt_secret(token: bytes) -> bytes:
    return fernet().decrypt(token)
