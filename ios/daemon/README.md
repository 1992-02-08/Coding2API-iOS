# 越狱常驻服务准备（未部署、未运行验证）

此目录只准备独立服务，不加载 launchd、不写系统目录、不安装依赖。普通 IPA 的后台线程仍会被 iOS 挂起；此服务需要单独的 jailbreak CPython 可执行程序和全部后端依赖，不能直接将 Briefcase 的嵌入式 Python.framework 当作 python3 执行。

- `service.py`：运行完整 build_app，独占数据目录锁，监听回环 8001，保留原始数据库和渠道逻辑。与 IPA 的 8000 端口及应用私有数据隔离。
- `provision.py`：目标 Python 下以 mobile 交互创建新数据目录、管理员密码散列及随机密钥；拒绝覆盖既有目录，不打印密码或密钥。执行入口 `python3 -m ios.daemon.provision <新数据目录>`，工作目录为已部署源码根。
- `service.plist.in`：待渲染的 launchd 模板，以 mobile 运行，异常退出限速重启；不是可以直接加载的最终 plist。

打包方必须提供并签名 `/usr/libexec/coding2api/python3` 下的独立运行时（实际路径由 bootstrap 前缀决定），以及 `/usr/share/coding2api` 下的完整源码、依赖和 web/dist。Python 搜索路径、依赖 install name、OpenSSL/证书和 roothide 兼容性均待实际构建验证。尚未提供假定 runtime 已存在就能成功的安装包。

模板中的 `@PREFIX@` 用 bootstrap 的逻辑前缀渲染；`@SERVICE_DATA_REAL@` 必须使用不随随机 jbroot 变化的真实系统数据目录，建议最终部署时确定为 mobile 的 Library/Application Support 下专用目录。EnvironmentVariables 不经过 launchd 路径转换，不能放 `@ROOTFS@` 或 bootstrap shell 的虚拟路径。不要把本次随机 jbroot 的解析结果写进模板或持久配置。

后续真正部署前需确定永久包标识、数据目录及运行时包依赖，构建并审核最终 package/control、文件布局与脚本，再向用户具体说明系统将新增哪些文件以及启用哪个服务，得到针对这次修改的明确同意。IPA 保持用户自行安装。不要因“都帮我操作”而直接加载此模板。

尚未测试：运行时启动、原生模块加载、数据库初始化、完整管理台与各渠道、同机 API、锁屏持续服务、崩溃恢复、停止和卸载后的数据保留。必须在实际签名部署后逐项验证。当前服务与 IPA 的账号和数据库互不共享；IPA 已准备连接 8001 的入口及身份探测协议，但尚未真机验证。

## 与 IPA 的连接契约

服务使用同一源码中的 `ios.app.coding2api_ios.connection.DaemonIdentity` 包装完整后端，增加 `GET /_coding2api/identity`；其余 API、静态文件和 ASGI lifespan 原样转发。IPA 只访问固定回环地址，不传输系统配置文件；管理台仍按原版鉴权。不要将无账号鉴权的识别端点当作恶意本机进程防护。

## 将来部署前必须逐项批准的系统改动

以下只是待审核清单，当前没有执行：

1. 安装并签名独立的 iOS CPython、全部原生扩展及证书；逻辑位置 `/usr/libexec/coding2api/`。尚未提供这一运行时，不能拿 Briefcase framework 冒充。
2. 新增完整源码和前端到逻辑位置 `/usr/share/coding2api/`，必须包括 `ios/` 以便导入身份协议。
3. 创建用户确认的真实 mobile 数据目录，以 mobile provision 管理员和密钥；不复制 IPA 数据库，不自动迁移账号。
4. 新增逻辑 `/Library/LaunchDaemons/coding2api.service.plist`，按 bootstrap 填充 `@PREFIX@` 和最终确认的数据目录，以 mobile 运行，并明确批准启用 `coding2api.service`。卸载默认保留数据；停止与移除服务也需要单独确认。

最终路径、包标识、运行时依赖与完整安装脚本尚未确定，必须在实际部署前再次列出最终文件与启用命令，取得针对这些具体改动的用户同意。
