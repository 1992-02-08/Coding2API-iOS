"""Embedded service; no remote backend and no subprocesses."""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
from pathlib import Path


class LocalService:
    def __init__(self, data: Path):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data, 0o700)
        self.config_path = self.data / "ios-config.json"
        self.server = None
        self.error = None
        self.thread = None
        self.url = "http://127.0.0.1:8000"

    @property
    def needs_setup(self):
        return not self.config_path.exists()

    def configure(self, username: str, password: str):
        from src.auth.users import FORBIDDEN_USERNAME_CHARS, create_password_hash

        if self.config_path.exists():
            raise ValueError("已配置，不能覆盖原有密钥")
        if (not username.strip() or username != username.strip() or "," in username
                or any(c in username for c in FORBIDDEN_USERNAME_CHARS)):
            raise ValueError("用户名不能为空或包含逗号、冒号、换行及首尾空白")
        if len(password) < 12:
            raise ValueError("管理员密码至少需要 12 个字符")
        users = self.data / "users.txt"
        with users.open("w", encoding="utf-8") as stream:
            os.chmod(users, 0o600)
            stream.write(f"{username}:{create_password_hash(password)}\n")
        payload = {"app_secret": secrets.token_urlsafe(48), "admin": username}
        with self.config_path.open("x", encoding="utf-8") as stream:
            os.chmod(self.config_path, 0o600)
            json.dump(payload, stream)

    def start(self):
        if self.thread is not None:
            raise RuntimeError("服务已启动，请重新打开 App 查看故障日志")
        self.thread = threading.Thread(target=self._run, name="Coding2API", daemon=True)
        self.thread.start()

    def _run(self):
        listener = None
        lock = None
        try:
            import uvicorn
            from src.config import Settings
            from src.instance_lock import hold_instance_lock
            from src.main import GRACEFUL_SHUTDOWN_SECONDS, build_app

            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            # The bundle stays read-only. All SQLite, backups and secrets use data.
            settings = Settings(
                _env_file=None, app_secret=config["app_secret"],
                admin_usernames=config["admin"], data_dir=str(self.data),
                users_file=str(self.data / "users.txt"), host="127.0.0.1", port=8000,
                public_base_url=self.url, allowed_hosts="127.0.0.1,localhost",
                trust_proxy=False,
            )
            lock = hold_instance_lock(self.data)
            # Reserve before building the app: never display another service's UI.
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 8000))
            listener.listen(128)
            self.server = uvicorn.Server(uvicorn.Config(
                build_app(settings), host="127.0.0.1", port=8000,
                loop="asyncio", http="h11", ws="none", workers=1,
                access_log=False, proxy_headers=False,
                timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
            ))
            self.server.run(sockets=[listener])
            self.error = "本地服务已停止，请重新打开 App"
        except BaseException as error:
            import traceback
            traceback.print_exc()
            self.error = f"{type(error).__name__}: {error}"
        finally:
            if listener is not None:
                listener.close()
            if lock is not None:
                lock.release()

    @property
    def ready(self):
        return self.error is None and self.server is not None and self.server.started

    def stop(self):
        if self.server is not None:
            self.server.should_exit = True
