"""Ansible Vault encrypt/decrypt helpers.

Never import ansible.cli / ansible.cli.vault here — importing them crashes with
"Ansible requires blocking IO on stdin/stdout/stderr" outside a real terminal.
ansible.parsing.vault is safe; the YAML-block formatter is hand-rolled below.
"""

import json
from typing import Any

from ansible.errors import AnsibleError
from ansible.parsing.vault import VaultLib, VaultSecret

_YAML_BLOCK_INDENT = 10
VAULT_PREFIX = "$ANSIBLE_VAULT;"
# Ansible's JSON encoding of a vaulted value: {"__ansible_vault": "$ANSIBLE_VAULT;..."}
VAULT_JSON_KEY = "__ansible_vault"


class VaultError(Exception):
    pass


def _lib(password: str) -> tuple[VaultLib, VaultSecret]:
    try:
        secret = VaultSecret(password.encode())
    except UnicodeEncodeError as exc:
        raise VaultError("Vault password is not valid Unicode text") from exc
    return VaultLib(secrets=[("default", secret)]), secret


def encrypt_to_vault_envelope(plaintext: str, password: str) -> str:
    vault, secret = _lib(password)
    try:
        return vault.encrypt(plaintext, secret=secret).decode()
    except AnsibleError as exc:
        raise VaultError(str(exc)) from exc
    except UnicodeEncodeError as exc:
        raise VaultError("Plaintext is not valid Unicode text") from exc


def to_json_value(envelope: str, var_name: str | None = None) -> str:
    """Ansible's JSON form of a vaulted value (extra vars, a host's vars): a value, or with a
    name a `"name": {...}` member to paste into an object."""
    value = json.dumps({VAULT_JSON_KEY: envelope})
    return f"{json.dumps(var_name)}: {value}" if var_name else value


def _envelope_text(vaulted_text: str) -> str:
    lines = [line.strip() for line in vaulted_text.strip().splitlines()]
    if lines and "!vault" in lines[0]:
        lines = lines[1:]
    return "\n".join(line for line in lines if line)


def vault_envelope(value: Any) -> str | None:
    """The Ansible Vault envelope a JSON var holds, or None: Ansible's JSON form
    {"__ansible_vault": "$ANSIBLE_VAULT;..."} or a plain `$ANSIBLE_VAULT;...` string (a pasted
    `!vault |` block too). Ansible decrypts the JSON form only where it parses JSON (extra vars)
    and a plain string nowhere, so runs re-encode both (app.jobs, app.inventory_render)."""
    if isinstance(value, dict) and len(value) == 1:
        value = value.get(VAULT_JSON_KEY)
    if not isinstance(value, str):
        return None
    envelope = _envelope_text(value)
    return envelope if envelope.startswith(VAULT_PREFIX) else None


def to_yaml_block(envelope: str, var_name: str | None = None) -> str:
    header = f"{var_name}: !vault |" if var_name else "!vault |"
    indent = " " * _YAML_BLOCK_INDENT
    return "\n".join([header, *(f"{indent}{line}" for line in envelope.splitlines())])


def decrypt_vault_text(vaulted_text: str, password: str) -> str:
    envelope = _envelope_text(vaulted_text)
    vault, _ = _lib(password)
    try:
        return vault.decrypt(envelope.encode()).decode()
    except AnsibleError as exc:
        raise VaultError(str(exc)) from exc
    except UnicodeEncodeError as exc:
        raise VaultError("Vault text is not valid Unicode text") from exc
    except UnicodeDecodeError as exc:
        raise VaultError("Decrypted content is not valid UTF-8 text") from exc
