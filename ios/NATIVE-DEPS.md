# 原生依赖核查与剩余构建工作

目标固定为 CPython 3.13 / iPhoneOS arm64 / iOS 16.0，不使用 macOS 或模拟器 wheel。以下为官方资料与锁文件的只读核查，非编译成功证据。

| 依赖 | 核查结果 |
| --- | --- |
| cffi 2.1.1 | 官方发布有 `cp313-cp313-ios_13_0_arm64_iphoneos.whl`，uv.lock 记录该产物及哈希 |
| pydantic-core 2.50.4 | 已核查的 CPython 3.13 发布清单没有 iOS wheel，需要交叉编译 |
| cryptography 50.0.2 | uv.lock 未记录 iOS wheel；官方长清单已读部分没有匹配产物，但未对全部文件做程序化穷举，不宣称绝对不存在 |

官方发布源：

- https://pypi.org/pypi/cffi/2.1.1/json
- https://pypi.org/pypi/pydantic-core/2.50.4/json
- https://pypi.org/pypi/cryptography/50.0.2/json

## 已准备的编译入口

`build_native.py` 从 uv.lock 读取原始 sdist URL、版本与 SHA256；安全解包后调用 cibuildwheel 3.4.0，选择 `cp313-ios_arm64_iphoneos`，加入 Rust 的 `aarch64-apple-ios` target，并用 `CIBW_XBUILD_TOOLS_IOS` 将 cargo/rustc/rustup 暴露给隔离环境。不会重标记桌面二进制，也不放宽依赖版本。

这是可供云端执行收集失败证据的试验入口，**尚未补齐并验证整个构建链**：

1. pydantic-core 使用 maturin（源码要求 >=1.16.0,<2），需要确认其与 cibuildwheel iOS CPython 交叉环境、PyO3 配置实际兼容。Rust 支持目标并不自动证明 Python 扩展能加载。
2. cryptography 使用 maturin（源码要求 >=1.14.1,<2）并依赖 OpenSSL。首轮云构建确认在 `openssl-sys` 查找 iPhoneOS OpenSSL 时失败。入口现下载并校验固定 OpenSSL 3.5.4（SHA256 写入脚本），使用上游 `ios64-xcrun`、最低 iOS 16.0 构建静态库，校验 arm64，并通过 `CIBW_ENVIRONMENT_IOS` 将 `OPENSSL_DIR` / `OPENSSL_STATIC=1` 传入隔离环境。此修复仍待云端验证；不会使用 macOS Homebrew OpenSSL。
3. BeeWare mobile-forge 的现代 cryptography 配方也注明未工作，不能用它作为成功依据；旧版本不能直接替换 uv.lock。
4. `resolve_wheels.py` 在以上编译成功后解析完整 wheel 集合；Toga 传递依赖仍需固化。uv 导出的条件标记还需在真实目标解析时核对，桌面解析结果本身不是完整 iOS 兼容性证明。
5. 成功 wheel 还须检查 Mach-O 架构、最低系统、依赖 install names，并进入签名 IPA 真机导入测试。cibuildwheel 不运行真机 wheel 测试，模拟器需要另外一套 wheels。

首个云端任务的实际目标是拿到两个扩展的编译日志，逐个修复上述条件；不能承诺首次运行产出 IPA。当前工作流没有上传证书或发布权限，失败保留 `native-build.log`；成功继续完整应用归档。

参考：

- https://cibuildwheel.pypa.io/en/stable/platforms/#ios
- https://doc.rust-lang.org/rustc/platform-support/apple-ios.html
- https://pyo3.rs/v0.30.1/building-and-distribution.html
- https://cryptography.io/en/50.0.2/installation/
- https://github.com/beeware/mobile-forge
- https://briefcase.beeware.org/en/v0.4.7/reference/platforms/iOS/xcode/
