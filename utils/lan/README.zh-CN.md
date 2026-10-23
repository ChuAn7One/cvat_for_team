# 本机 CVAT 局域网与自定义模型部署

## 已确认的状态（2026-10-23）

- WLAN IPv4：`192.168.110.92`，访问目标：`http://192.168.110.92:8080`。
- NVIDIA GTX 1660 Ti，6GB 显存。
- Windows 11 专业版，约 32GB 内存；WSL2 / Ubuntu 22.04 已安装。
- Docker Desktop 安装在 `%LOCALAPPDATA%\Programs\DockerDesktop`，启动脚本会自动查找。
- CVAT v2.80.0 和 Nuclio 已启动，网页与 API 验证通过，容器内 GPU 可见。
- 已创建管理员和“标注团队”组织，官方 YOLO11n 已部署，使用 GPU 推理。
- 公交车示例任务 ID 为 1：实际调用模型、保存 5 个检测框、重新读取核对均已通过。
- 验收记录见 `verification.json`。其它电脑的浏览器访问尚需从对应设备确认。

“用 Wi-Fi 作为主 IP”在这里指让 CVAT 使用这台电脑的 WLAN 局域网地址。
不需要修改 Windows 默认路由。其他电脑连接同一个路由器的可互访网络即可访问。
电脑需要保持开机，Docker 运行且不能休眠。

## 1. 安装启动环境

按 [CVAT 官方 Windows 安装说明](https://docs.cvat.ai/docs/administration/community/basics/installation/)
安装 WSL2、Ubuntu 和 Docker Desktop，使用 Linux containers / WSL2 backend。
在 Docker Desktop 的 Settings → Resources → WSL Integration 启用 Ubuntu。
若安装过程要求重启，先重启。重新打开 PowerShell 后检查：

```powershell
docker version
docker compose version
```

## 2. 启动网页和模型管理服务

新克隆仓库时，先在仓库根目录复制配置示例，再把 `CVAT_HOST` 改为服务器的 Wi-Fi IPv4 地址：

```powershell
Copy-Item .\utils\lan\cvat.env.example .\.env
notepad .env
```

已有 `.env` 的本机无需重复复制。配置示例不包含账号密码；实际 `.env`、凭据、模型权重、
下载工具和运行数据均不提交到 Git。下文“已创建”“已下载”的状态描述仅适用于当前服务器，
新克隆不会恢复 Docker 数据卷、用户或模型服务。首次启动后用 `cvat.ps1 CreateAdmin` 创建管理员。

在 PowerShell 执行：

```powershell
cd E:\workspace\annotation\cvat
powershell -ExecutionPolicy Bypass -File .\utils\lan\cvat.ps1 Start
```

首次运行会下载较大的容器镜像。脚本组合 `utils/lan` 中保存的 v2.80.0 官方发布配置、
对应 serverless 配置与根目录的局域网配置，并固定 `.env` 的 `CVAT_VERSION=v2.80.0`。
已核对下载的官方配置与当前源码配置，差异仅为默认镜像标签。
运行官方镜像，不会把本机源码修改自动打包进容器；如修改 CVAT 前后端需单独构建。
`.env` 已写入 `CVAT_HOST=192.168.110.92`，换 Wi-Fi 或地址变化后修改它并重新执行 Start。
如果终端已有 `CVAT_HOST` 环境变量，它会优先于 `.env`，请保持一致。

检查服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\utils\lan\cvat.ps1 Status
```

管理员 `admin` 已创建，随机密码保存在 `utils/lan/.credentials.json`，文件权限仅授予当前用户。
不要把凭据文件发给标注成员；让成员使用独立账号。
如需另建管理员，可执行 `cvat.ps1 CreateAdmin`，在终端输入新的用户名与密码。

登录后切换到右上角的“标注团队”，进入
[公交车示例任务](http://192.168.110.92:8080/tasks/1)，点击其中的 Job 查看检测框。
Models 页面可看到 `yolo11n-demo`，新建匹配类别的任务后可使用自动标注。

本机和其他电脑均使用 `http://192.168.110.92:8080`，当前路由配置要求该 Host，
不要用 localhost 来判断是否启动成功。数据库、图片和标注存放在 Docker volumes。
日常停止用脚本的 Stop；不要执行 `docker compose down -v`，它会删除数据卷。

## 3. 放行局域网访问

已添加 `CVAT-LAN-8080-WLAN` 入站规则：仅 WLAN、本地子网、TCP 8080。
保留现有 Windows 网络类型，不需要切换为专用网络。需要重建规则时在管理员 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\utils\lan\open-firewall.ps1
```

其他电脑访问失败时依次确认：

1. 本机能打开上述 IP 地址，Status 显示容器运行正常。
2. Windows 防火墙规则生效，网卡名称仍为 WLAN。
3. 其他电脑连接同一局域网，路由器未启用访客隔离/AP 隔离。
4. 路由器为这台电脑保留 DHCP 地址，避免 IP 变化。

仅对外开放网页端口。Nuclio 管理页面绑定 `127.0.0.1:8070`，供本机部署模型使用。

## 4. 多人协作

已创建 Organization：**标注团队**（`annotation-team`），示例任务位于该组织。
每个人在网页注册独立账号。管理员在组织中邀请成员并分配角色。
在组织内创建 Project / Task，上传图片并按需要拆分 Jobs，给每个人指派不同 Job。
同一张图不要让多人同时编辑。多人共用同一服务，任务访问权限仍受组织与角色控制。

## 5. 接入模型

模型原始文件按名称分别放在 `utils/lan/models/<模型名>/`，
现有示例位于 `utils/lan/models/yolo11n-demo/`。
后续新增权重请按[模型目录与新增步骤](models/README.zh-CN.md)操作。

详见 [自定义模型说明](../../serverless/custom-models/README.zh-CN.md)。
先验证一个小 YOLO 模型，再验证一个 SAM 模型。6GB 显存按需部署，
每个 GPU 函数只有一个 worker，但不同函数仍会同时占显存；这不是全局排队限制。
不要一次部署全部 GPU 模型，SAM3 是否能在此设备运行必须单独实测。

官方 YOLO11n 示例的部署入口是 `utils/lan/deploy-demo.sh`（Ubuntu / WSL 中运行）。
它使用项目内的 Nuclio 1.16.3 工具和独立 Docker 客户端配置，避免 Windows 凭据助手兼容问题。
项目内已下载权重、COCO 类别表和官方公交车图片，分别位于 `models/yolo11n-demo/` 的对应子目录。部署后运行：

```powershell
python utils/lan/verify-demo.py
```

验收会在示例任务中调用 YOLO、保存检测框并重新读取核对，输出 `utils/lan/verification.json`。
该脚本仅用于部署验收，会更新示例任务的标注，请勿把它用于生产任务。
Docker 已启用登录后自动启动；容器的 restart 策略会恢复服务，电脑休眠时仍不可访问。
模型构建需要访问 Docker Hub、PyTorch 和 Python 包源。
Docker 单独使用 `127.0.0.1:10808` 的已有代理访问镜像站，Debian / PyTorch / PyPI 设为直连；
未修改 Windows 全局代理。原 Docker 设置备份在
`%APPDATA%\Docker\settings-store.json.cvat-backup-20261023`。
若已有代理未运行，新增镜像下载仍可能失败，已经启动的本地标注服务不依赖它。

官方参考：[网络安装](https://docs.cvat.ai/docs/administration/community/basics/installation/)、
[自动标注部署](https://docs.cvat.ai/docs/administration/community/advanced/installation_automatic_annotation/)。
