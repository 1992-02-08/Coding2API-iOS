"""One-time interactive provisioning; run as mobile using the target Python runtime."""
from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
from pathlib import Path


def main():
    from src.auth.users import FORBIDDEN_USERNAME_CHARS, create_password_hash

    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("run as mobile, not root")
    username = input("Administrator username: ").strip()
    if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username)
            or any(c in username for c in FORBIDDEN_USERNAME_CHARS)):
        parser.error("invalid administrator username")
    password = getpass.getpass("Password (12+ characters): ")
    if len(password) < 12 or password != getpass.getpass("Confirm password: "):
        parser.error("password too short or confirmation differs")
    # Reserve a new directory; never overwrite an existing installation or key.
    args.data.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(args.data, 0o700)
    for name, value in (
        ("users.txt", f"{username}:{create_password_hash(password)}\n"),
        ("service.env", f"APP_SECRET={secrets.token_urlsafe(48)}\nADMIN_USERNAMES={username}\n"),
    ):
        path = args.data / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
    print("Provisioned. Secrets were not printed. launchd remains disabled.")


if __name__ == "__main__":
    main()
