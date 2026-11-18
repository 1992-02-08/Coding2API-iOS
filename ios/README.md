# 实验性完整本地 iOS 移植（未构建、未验收）

完整 `src/` 后端、全部渠道与构建后的 `web/dist/` 随 IPA 打包。云端仅用于编译；运行时服务都在手机上，上游渠道仍需联网。

## 两种运行模式

启动页明确选择，不自动回退、不共享数据库：

- **内嵌 :8000**：首次创建管理员，随机 APP_SECRET、SQLite 与配置保存在应用私有 data 目录；App 挂起或终止可能使 API 不可用。
- **越狱常驻 :8001**：IPA 仅探测固定 `127.0.0.1:8001/_coding2api/identity`，验证应用/协议/daemon 标志后打开该服务的完整管理台，使用常驻服务自己的账号。不会读取服务密钥、容器外文件或启动第二个后端。识别标志用于防误连，不是本机恶意进程的密码学认证。

WebView 上方有返回模式按钮。内嵌服务已经启动后，切换常驻模式需要完全退出并重开 App，避免遗留内嵌线程。常驻连接失败保留启动页，可重试；服务在打开管理台后中断时，返回模式页重新连接。客户端 API 地址分别为 `http://127.0.0.1:8000/v1` 和 `http://127.0.0.1:8001/v1`。

常驻服务需独立部署，见 `daemon/README.md`。IPA 不包含可直接运行的 launchd Python，也不自动部署。没有承诺普通 IPA 锁屏常驻。

## 云端 macOS 构建入口

`.github/workflows/ios.yml` 支持手动 `workflow_dispatch`，也在 main 上该工作流文件变更的推送时启动；其他源码推送不触发 IPA 构建。不创建仓库、不发布 Release、不安装设备。当前默认 `bundle_prefix` 为 `com.github.1992-02-08`，最终 ID 为 `com.github.1992-02-08.coding2api`；手动运行可指定前缀。

流程使用 macOS 15 / 完整 Xcode、CPython 3.13、Node 24、pnpm 10.18.0、Briefcase 0.4.7：

1. `uv sync --frozen`、原版 ruff 与 100% 行/分支覆盖率门槛，以及 `uv run pytest -q ios/tests`。
2. 原版前端 tsc、vitest、完整构建。
3. 可选（默认开启）`build_native.py`：从 uv.lock 获取两个原生扩展的源码与 SHA256，尝试 cibuildwheel 3.4.0 真机交叉编译。此步骤是待执行的试验配方，尚不能保证通过，尤其 OpenSSL/PyO3 构建条件。
4. `resolve_wheels.py` 从 uv.lock 导出后端固定版本，追加 Toga 0.5.7，下载 CPython 3.13/iPhoneOS arm64 或纯 Python wheels；可搜索 `ios/native-wheels/` 的自编译产物。缺失兼容 wheel 直接失败，禁止拿桌面或模拟器产物改名。
5. `prepare.py` 检查完整 wheel 清单与哈希，以 `--no-index --only-binary` 离线安装依赖并生成完整工程。
6. `build-ipa.sh` 以 generic iOS device、arm64、最低 iOS 16.0 归档；检查打包的后端、前端与宿主，生成 `Coding2API-unsigned.ipa`。归档或内容检查失败不交付假成功产物。

依赖版本受 uv.lock 约束；Toga 的传递依赖仍在首次成功解析时确定，SHA256.json 记录当次完整产物。尚未形成经验证、可重复使用的完整 iOS 锁文件；哈希清单是构建记录，不是独立可信来源证明。准备脚本拒绝覆盖已有 staging/wheels 目录，重试前需人工检查并保留有用证据。

成功时 Actions artifact 包含未签名 IPA、归档、依赖清单及日志；这不是可直接安装的签名发行包。用户自行采用其安装工具支持的签名方式安装，所有嵌入框架也须有效签名；尚未验证越狱自签兼容性。没有自动导入证书、签名身份或 provisioning profile。

## 本地 Mac 复现

先执行上面原有后端/前端质量门槛。然后在 CPython 3.13 虚拟环境：

```sh
python -m pip install briefcase==0.4.7 cibuildwheel==3.4.0
python ios/build_native.py
python ios/resolve_wheels.py
python ios/prepare.py --bundle YOUR.REVERSE.DNS --wheels ios/wheels
cd ios/staging
briefcase create iOS --no-input
cd ../..
bash ios/build-ipa.sh
```

此手机目前没有 Python、Node、uv、pnpm、Rust 或 Xcode，clang/SDK 不能替代上述环境。本轮仅实际通过 `bash -n ios/build-ipa.sh`，未执行 Python、前端或云端构建，也未生成 IPA。

## 原生依赖与验收阻碍

锁定 cffi 2.1.1 有 iOS wheel；pydantic-core 2.50.4 / cryptography 50.0.2 的 CPython 3.13 真机产物需要核查或自编译，细节见 `NATIVE-DEPS.md`。BeeWare 旧版依赖不能静默替代 uv.lock。普通 Briefcase build 默认面向模拟器，不能作为真机 IPA 证据，因此流程使用显式 Xcode 真机归档。

未测试（不能把源码整合称为可运行交付）：

- 原生启动页、两种模式、错误重试与返回：在签名 IPA 中分别连接 8000/8001 并制造端口冲突。
- 首次建号、登录、密码和数据库持久化：创建账号、重启 App 后重新登录。
- 全部管理台页面、导入导出、外部登录回跳：逐页在真机操作。
- 原生模块、TLS、SQLite/flock：真机加载扩展、重启并发锁测试。
- 各渠道刷新、探活、模型、流式/非流式 API：逐渠道使用真实授权账号验证。
- 锁屏持续 API、崩溃恢复和重越狱路径：实际签名部署独立运行时后检查，当前未部署。

官方参考：https://briefcase.beeware.org/en/stable/reference/platforms/iOS/xcode/ 、https://cibuildwheel.pypa.io/en/stable/platforms/#ios 。
