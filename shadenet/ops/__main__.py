"""Operator account management. Shell-only by design: there is no web path to
create an operator, so taking over the console requires the server itself.

    python -m shadenet.ops add-operator operator
    python -m shadenet.ops reset-totp operator
    python -m shadenet.ops set-password operator
    python -m shadenet.ops disable operator | enable operator
    python -m shadenet.ops list
    python -m shadenet.ops verify-audit
"""

from __future__ import annotations

import argparse
import getpass
import sys

from shadenet.ops import audit, auth


def _password() -> str:
    pw = getpass.getpass("New operator password (14+ chars): ")
    if pw != getpass.getpass("Again: "):
        sys.exit("passwords didn't match")
    return pw


def _show_totp(info: dict) -> None:
    print(f"\nAdd this to your authenticator app (shown once):\n  secret: {info['totp_secret']}\n  uri:    {info['totp_uri']}")
    try:
        import qrcode  # optional
        qr = qrcode.QRCode()
        qr.add_data(info["totp_uri"])
        qr.print_ascii(invert=True)
    except ImportError:
        print("  (pip install qrcode to get a scannable QR here)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m shadenet.ops")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("add-operator", "reset-totp", "set-password", "disable", "enable"):
        sub.add_parser(name).add_argument("username")
    sub.add_parser("list")
    sub.add_parser("verify-audit")
    a = p.parse_args(argv)

    if a.cmd == "add-operator":
        info = auth.add_operator(a.username, _password())
        audit.record("shell", "operator.add", target=a.username)
        _show_totp(info)
    elif a.cmd == "reset-totp":
        info = auth.reset_totp(a.username)
        audit.record("shell", "operator.reset_totp", target=a.username)
        _show_totp(info)
    elif a.cmd == "set-password":
        auth.set_password(a.username, _password())
        audit.record("shell", "operator.set_password", target=a.username)
        print("password updated; existing sessions signed out")
    elif a.cmd in ("disable", "enable"):
        auth.set_disabled(a.username, a.cmd == "disable")
        audit.record("shell", f"operator.{a.cmd}", target=a.username)
        print(f"{a.username} {a.cmd}d")
    elif a.cmd == "list":
        for o in auth.list_operators():
            print(f"{o['username']:<16} {'DISABLED' if o['disabled'] else 'active':<9} since {o['created_at']}")
    elif a.cmd == "verify-audit":
        print(audit.verify())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
