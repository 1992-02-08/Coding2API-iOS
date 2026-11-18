"""Native launcher for the complete on-device backend or local jailbreak daemon."""
from __future__ import annotations

import asyncio

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .connection import probe_daemon
from .runtime import LocalService


class Coding2API(toga.App):
    def startup(self):
        self.service = LocalService(self.paths.data / "service")
        self.busy = False
        self.main_window = toga.MainWindow(title="Coding2API")
        self.status = toga.Label("选择手机本地运行模式；两种模式的账号和数据库独立。",
                                 style=Pack(margin=12))
        self.username = toga.TextInput(placeholder="内嵌模式管理员用户名", style=Pack(margin=8))
        self.password = toga.PasswordInput(placeholder="密码（至少 12 字符）", style=Pack(margin=8))
        self.local_button = toga.Button("启动内嵌服务 :8000", on_press=self.launch_local,
                                        style=Pack(margin=8))
        self.daemon_button = toga.Button("连接越狱常驻服务 :8001", on_press=self.launch_daemon,
                                         style=Pack(margin=8))
        self.show_launcher()
        self.main_window.show()

    def show_launcher(self, widget=None, **kwargs):
        children = [self.status]
        if self.service.needs_setup:
            children += [self.username, self.password]
        children += [self.local_button, self.daemon_button]
        self.main_window.content = toga.Box(children=children, style=Pack(direction=COLUMN))

    def set_busy(self, value):
        self.busy = value
        self.local_button.enabled = not value
        self.daemon_button.enabled = not value

    def show_web(self, url, label):
        self.status.text = label
        self.webview = toga.WebView(url=url, style=Pack(flex=1))
        self.main_window.content = toga.Box(children=[
            toga.Button("返回运行模式", on_press=self.show_launcher, style=Pack(margin=8)),
            self.webview,
        ], style=Pack(direction=COLUMN, flex=1))

    async def launch_daemon(self, widget, **kwargs):
        if self.busy:
            return
        # If both runtimes were used, returning to daemon mode must not leave an
        # embedded server paused mid-write in the background. Stop it first.
        if self.service.thread is not None and self.service.thread.is_alive():
            self.status.text = "内嵌服务仍在运行；请完全关闭并重开 App 后选择常驻模式。"
            return
        self.set_busy(True)
        self.status.text = "正在检测手机上的常驻服务……"
        try:
            url = await asyncio.to_thread(probe_daemon)
            self.show_web(url, "常驻模式 :8001；使用常驻服务的管理员账号。")
        except Exception as error:
            self.status.text = f"常驻连接失败：{error}。确认已部署并启动后重试。"
        finally:
            self.set_busy(False)

    async def launch_local(self, widget, **kwargs):
        if self.busy:
            return
        self.set_busy(True)
        try:
            if self.service.needs_setup:
                await asyncio.to_thread(self.service.configure,
                                        self.username.value.strip(), self.password.value)
                self.password.value = ""
            if self.service.thread is None:
                self.service.start()
            self.status.text = "正在启动内嵌后端；App 被挂起时服务可能暂停……"
            for _ in range(600):
                if self.service.error:
                    raise RuntimeError(self.service.error)
                if self.service.ready:
                    self.show_web(self.service.url, "内嵌模式 :8000；后台运行受 iOS 限制。")
                    return
                await asyncio.sleep(0.1)
            self.service.stop()
            raise TimeoutError("启动超过 60 秒，请重新打开 App 并查看设备日志")
        except Exception as error:
            self.status.text = f"内嵌启动失败：{error}"
        finally:
            self.set_busy(False)


def main():
    return Coding2API()
