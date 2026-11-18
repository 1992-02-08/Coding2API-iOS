"""Standalone jailbreak service entry. Requires a separately provisioned Python runtime.

Run from the installed source root. No app-container sharing and no secret generation
at daemon startup: provisioning must happen once, as mobile, before enabling launchd.
"""
from __future__ import annotations

import os
from pathlib import Path


def main():
    import uvicorn

    from ios.app.coding2api_ios.connection import DaemonIdentity
    from src.config import Settings
    from src.instance_lock import AlreadyRunning, hold_instance_lock
    from src.main import GRACEFUL_SHUTDOWN_SECONDS, build_app, configure_logging

    data = Path(os.environ["CODING2API_SERVICE_DATA"])
    config = data / "service.env"
    if not config.is_file():
        raise SystemExit("Missing service.env: provision secrets and users before enabling launchd")
    if not (Path.cwd() / "web/dist/index.html").is_file():
        raise SystemExit("Missing complete web/dist; refuse a backend-only deployment")
    # Use a distinct port and data directory: never start two writers against IPA data.
    settings = Settings(
        _env_file=str(config), data_dir=str(data), users_file=str(data / "users.txt"),
        host="127.0.0.1", port=8001, public_base_url="http://127.0.0.1:8001",
        allowed_hosts="127.0.0.1,localhost", trust_proxy=False,
    )
    configure_logging(settings.log_level)
    try:
        lock = hold_instance_lock(data)
    except AlreadyRunning:
        return
    try:
        uvicorn.run(
            DaemonIdentity(build_app(settings)), host="127.0.0.1", port=8001,
            loop="asyncio", http="h11", ws="none", workers=1,
            access_log=False, proxy_headers=False,
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
        )
    finally:
        lock.release()


if __name__ == "__main__":
    main()
