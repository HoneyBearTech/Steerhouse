"""Server-side maintenance commands, run inside the backend container:

    uv run python -m app.cli <command> ...    # dev image
    python -m app.cli <command> ...           # production (runtime) image

    migrate                          bring the database schema to the latest revision
                                     (the app also does this at startup)
    import-sqlite <path> [--check]   one-time import of a pre-Postgres steerhouse.db
    reset-2fa <username>             turn off a user's two-factor login (TOTP, passkeys
                                     and recovery codes; reset-totp is the old name)
    reencrypt-secrets                re-encrypt stored secrets under the first
                                     CREDENTIAL_ENCRYPTION_KEY (a key rotation)
    wrap-key                         encrypt the Fernet key list on stdin with the secret
                                     store's Transit key (CREDENTIAL_ENCRYPTION_KEY_WRAPPED);
                                     needs BAO_TOKEN with transit/encrypt
    rewrap-key                       move CREDENTIAL_ENCRYPTION_KEY_WRAPPED to the Transit
                                     key's latest version; needs BAO_TOKEN with transit/rewrap
    analytics-grant <role>           let a (Grafana) database role read the analytics views
    analytics-check <role>           check such a role can read nothing else
    analytics-revoke <role>          take that access away again

reset-2fa is the break-glass for a user who lost their authenticator, passkeys and recovery
codes when no other admin can reset it from the Users page.
"""

import argparse
import os
import sys
from pathlib import Path

from app import analytics, audit, crypto, secret_store, totp
from app.config import get_settings
from app.db import get_sessionmaker, init_db
from app.key_rotation import RotationFailed, reencrypt_all
from app.models import User
from app.sqlite_import import ImportFailed, import_sqlite


def reset_two_factor(username: str) -> int:
    init_db()
    db = get_sessionmaker()()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(f"No user named {username!r}.", file=sys.stderr)
            return 1
        had = totp.clear_all(user)
        if had is None:
            print(f"{username} has no two-factor login; nothing to do.")
            return 0
        user.session_version += 1
        db.commit()
        audit.record(
            db,
            "user.two_factor_reset",
            actor_username="(server cli)",
            target_type="user",
            target_id=user.id,
            target_name=user.username,
            detail=had,
        )
        print(f"Two-factor login turned off for {username}; their sessions were signed out.")
        return 0
    finally:
        db.close()


def reencrypt_secrets() -> int:
    init_db()
    if not crypto.unlock():
        print(
            "The credential encryption key is wrapped and the secret store has not unwrapped it "
            f"({crypto.key_state()['key_error'] or 'unknown error'}). Nothing was changed.",
            file=sys.stderr,
        )
        return 1
    old_keys = len(crypto.encryption_keys()) - 1
    db = get_sessionmaker()()
    try:
        try:
            result = reencrypt_all(db)
        except RotationFailed as exc:
            db.rollback()
            print(f"Nothing was changed. {exc}.", file=sys.stderr)
            return 1
        db.commit()
        if result.reencrypted:
            audit.record(
                db,
                "secrets.reencrypt",
                actor_username="(server cli)",
                detail={"reencrypted": result.reencrypted},
            )
        print(
            f"Re-encrypted {result.reencrypted} secret(s) under the current key; "
            f"{result.current} already were."
        )
        if old_keys:
            setting = (
                "CREDENTIAL_ENCRYPTION_KEY_WRAPPED (wrap the list again without them: "
                "`python -m app.cli wrap-key`)"
                if get_settings().credential_encryption_key_wrapped
                else "CREDENTIAL_ENCRYPTION_KEY"
            )
            print(
                f"{setting} still lists {old_keys} old key(s) after the first: "
                "remove them and restart the API."
            )
        return 0
    finally:
        db.close()


def _operator_token() -> str | None:
    """The token of the person running wrap-key or rewrap-key (as for the bao/vault CLI):
    Steerhouse's own login is only allowed to decrypt."""
    return os.environ.get("BAO_TOKEN") or os.environ.get("VAULT_TOKEN") or None


def wrap_key() -> int:
    """Prints the Fernet key list read from stdin, encrypted by the Transit key, for
    CREDENTIAL_ENCRYPTION_KEY_WRAPPED."""
    token = _operator_token()
    if token is None or not get_settings().secrets_store_enabled:
        print(
            "Set SECRETS_STORE_URL and BAO_TOKEN (or VAULT_TOKEN): a token that may use "
            "transit/encrypt on the key.",
            file=sys.stderr,
        )
        return 1
    text = sys.stdin.read().strip()
    try:
        crypto.parse_keys(text)
        print(secret_store.transit_encrypt(text, token))
    except secret_store.SecretStoreError as exc:
        print(f"Nothing was wrapped: {exc}.", file=sys.stderr)
        return 1
    return 0


def rewrap_key() -> int:
    """Prints CREDENTIAL_ENCRYPTION_KEY_WRAPPED under the Transit key's latest version (after
    a rotation of that key), without the store showing the keys."""
    token = _operator_token()
    wrapped = get_settings().credential_encryption_key_wrapped
    if token is None or not wrapped:
        print(
            "Needs CREDENTIAL_ENCRYPTION_KEY_WRAPPED and BAO_TOKEN (or VAULT_TOKEN): a token "
            "that may use transit/rewrap on the key.",
            file=sys.stderr,
        )
        return 1
    try:
        print(secret_store.transit_rewrap(wrapped, token))
    except secret_store.SecretStoreError as exc:
        print(f"Nothing was rewrapped: {exc}.", file=sys.stderr)
        return 1
    return 0


def migrate() -> int:
    init_db()
    print("The database schema is up to date.")
    return 0


def import_legacy(path: str, check: bool) -> int:
    try:
        counts = import_sqlite(Path(path), check=check)
    except ImportFailed as exc:
        print(f"Import stopped, nothing was written:\n{exc}", file=sys.stderr)
        return 1
    width = max(map(len, counts))
    for table, rows in counts.items():
        print(f"  {table:<{width}}  {rows}")
    if check:
        print("Check passed: everything above would be imported. Nothing was written.")
    else:
        print(f"Imported {sum(counts.values())} rows. {path} was not changed; keep it as a backup.")
    return 0


def _report(role: str, result: analytics.CheckResult) -> int:
    for warning in result.warnings:
        print(f"warning: {warning}")
    for problem in result.problems:
        print(f"problem: {problem}", file=sys.stderr)
    if not result.ok:
        print(f"{role} is not limited to reading the analytics views.", file=sys.stderr)
        return 1
    print(f"{role} can read the analytics views and nothing else.")
    return 0


def analytics_command(command: str, role: str) -> int:
    init_db()
    db = get_sessionmaker()()
    try:
        if command == "analytics-grant":
            return _report(role, analytics.grant(db, role))
        if command == "analytics-check":
            return _report(role, analytics.check(db, role))
        analytics.revoke(db, role)
        print(f"{role} can no longer read the analytics views.")
        return 0
    except analytics.AnalyticsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Steerhouse maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="bring the database schema to the latest revision")
    importer = commands.add_parser("import-sqlite", help="import a pre-Postgres steerhouse.db once")
    importer.add_argument("path")
    importer.add_argument(
        "--check", action="store_true", help="run the whole import, then roll it back"
    )
    reset = commands.add_parser(
        "reset-2fa", aliases=["reset-totp"], help="turn off a user's two-factor login"
    )
    reset.add_argument("username")
    commands.add_parser(
        "reencrypt-secrets",
        help="re-encrypt stored secrets under the first CREDENTIAL_ENCRYPTION_KEY (key rotation)",
    )
    commands.add_parser(
        "wrap-key",
        help="encrypt the Fernet key list on stdin with the secret store's Transit key "
        "(CREDENTIAL_ENCRYPTION_KEY_WRAPPED)",
    )
    commands.add_parser(
        "rewrap-key",
        help="move CREDENTIAL_ENCRYPTION_KEY_WRAPPED to the Transit key's latest version",
    )
    for name, about in (
        ("analytics-grant", "let a database role read the analytics views (for Grafana)"),
        ("analytics-check", "check a role can read the analytics views and nothing else"),
        ("analytics-revoke", "take a role's access to the analytics views away"),
    ):
        commands.add_parser(name, help=about).add_argument("role")
    args = parser.parse_args(argv)
    if args.command.startswith("analytics-"):
        return analytics_command(args.command, args.role)
    if args.command == "migrate":
        return migrate()
    if args.command == "import-sqlite":
        return import_legacy(args.path, args.check)
    if args.command == "reencrypt-secrets":
        return reencrypt_secrets()
    if args.command == "wrap-key":
        return wrap_key()
    if args.command == "rewrap-key":
        return rewrap_key()
    return reset_two_factor(args.username)


if __name__ == "__main__":
    sys.exit(main())
