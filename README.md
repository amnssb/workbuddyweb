# WorkBuddy All-in-One 融合一键部署版

<div align="center">

**腾讯 CodeBuddy 账号池网关 (`workbuddy2api`) + Web 运营管理控制台 (`workbuddy-manager`) 一体化容器镜像**

零手动配置 · 避免跨容器权限地狱 · 告别 Docker 套接字挂载风险 · 开箱即用

[![Docker Compose](https://img.shields.io/badge/Deploy-Docker_Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Go](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go&logoColor=white)](upstream/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](server/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](web/)
[![License](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)

[简体中文](README.md) · [English](README.en.md)

</div>

---

## 🌟 为什么要做这个融合版？

官方的原版方案中，这两个项目是独立的：
1. **[workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)**：由 Go 编写的高性能上游网关，负责 OAuth 设备授权、多账号轮询调度、冷却熔断与 OpenAI 协议转换（监听 `:7863`），但没有管理界面。
2. **[workbuddy-manager](https://github.com/ithtelab/workbuddy-manager)**：由 Python FastAPI + Next.js 编写的 Web 控制台与反代网关（监听 `:7864`），提供扫码加号、用量审计、多密钥分发与可视化设置。

**以前手动部署的痛点**：
- 必须分别克隆两个仓库，手动处理目录层级结构；
- 容器间通信需要配置网络互联（如 Linux 下 `host.docker.internal` 解析问题）；
- 管理端操作上游需要挂载宿主机的 `/var/run/docker.sock`，存在极大的特权逃逸安全隐患；
- 宿主机与容器之间的 `uid 10001` 读写权限错乱（导致报 `unable to open database file` 或无法写入 `auths`）；
- 必须手动配置 `api_key` 并两端对齐。

**本项目实现真正的「一键融合」**：
- 🛠️ **全功能单容器集成**：Go 上游网关与 Python/Next.js 管理后台融合为一个容器，仅暴露一个统一端口（默认 `:7864`）；
- 🔒 **无须 Docker 套接字**：管理端通过内部守护进程管理上游引擎，秒级平滑热重启，无需挂载 `/var/run/docker.sock`；
- ⚡ **开箱即用自动初始化**：首启全自动生成内部 `config.json` 与高强度随机密钥，内置前端静态编译产物，免装 Node.js；
- 📱 **完整扫码加号与任务管理**：直接在 Web 面板微信/QQ 扫码添加账号，自动每日签到、猫猫旅行、领奖与日志持久化；
- 🔄 **单仓库一键更新**：管理端与上游均跟随本仓库（`amnssb/workbuddyweb`）发布，Web 面板内一键升级，更新包经签名验证后热替换；
- 🛡️ **非 root 运行**：容器内以 `app:10001` 用户执行，数据库与日志目录权限预置，降低特权逃逸风险。

---

## 🚀 极速一键部署

### 方式一：Docker Compose（推荐）

只需克隆本项目并一条命令运行：

```bash
# 1. 进入项目目录
cd workbuddyweb

# 2. 一键启动（会自动构建镜像并拉起服务）
docker compose up -d --build
```

启动完成后：
- 🌐 **Web 管理控制台**：`http://你的服务器IP:7864`
- 🔑 **OpenAI 兼容 API 端点**：`http://你的服务器IP:7864/v1`
- 👤 **默认管理员账号**：`admin`
- 🔐 **默认初始密码**：首启时自动生成，通过以下命令查看：
  ```bash
  docker compose logs workbuddy | grep -A 2 "初始管理员"
  ```
  *(也可在 `.env` 中预先指定 `WB_ADMIN_PASSWORD=你的强密码`)*

---

### 方式二：使用内置一键部署脚本

- **Linux / macOS**：
  ```bash
  chmod +x scripts/deploy.sh
  ./scripts/deploy.sh
  ```
- **Windows (PowerShell)**：
  ```powershell
  .\scripts\deploy.ps1
  ```

---

### 方式三：单条 Docker Run 命令部署

如果你使用群晖 NAS、Unraid、CasaOS、1Panel 等应用中心，可以直接运行单容器命令：

```bash
docker run -d \
  --name workbuddy \
  --restart unless-stopped \
  -p 7864:7864 \
  -e TZ=Asia/Shanghai \
  -e WB_ADMIN_PASSWORD=admin123456 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/auths:/app/auths \
  workbuddy-all-in-one:latest
```

---

### 方式四：双容器微服务模式（备用）

如果你坚持希望将网关与管理端拆分两个容器运行，本项目同样提供了现成的编排配置：

```bash
docker compose -f docker-compose.separate.yml up -d --build
```

---

## 📖 核心使用流程

### 1. 登录与修改密码
打开浏览器访问 `http://<服务器IP>:7864`，使用 `admin` 及初始密码登录。
> 登录后建议第一时间点击右上角「用户设置」修改密码。

### 2. 扫码纳管 CodeBuddy 账号
1. 在左侧/底栏导航进入「**账号管理**」页面；
2. 点击右上角「**添加账号**」；
3. 使用微信或 QQ 扫描弹出的授权二维码并在手机上确认；
4. 系统将自动完成鉴权、领取新手 Trial、保存凭据并自动平滑重载上游引擎，无需人工介入！

### 3. 创建与分发 API 密钥
1. 导航进入「**API 密钥**」；
2. 点击「**创建密钥**」，可为每把密钥配置：
   - 绑定的账号版本（国内版 CN / 国际版 Global）
   - IP 白名单 / 最大同时请求 IP 数
   - 模型调用白名单
   - Token 配额 / 积分额度（任一超限即拒绝）
3. 生成的 Key（形如 `wbk_xxxxxxxx`）即作为下游调用的 Bearer Token。

### 4. 版本升级
管理端与上游均跟随本仓库发布，Web 面板「系统更新」页面一键升级：
- **管理端更新**：下载 Release 更新包（tar.gz + .sig），经签名公钥验证后热替换后端与前端产物，自动重启服务；
- **上游更新**：在仓库工作区拉取最新代码，docker compose 重建容器；
- 更新包签名验证使用 `deploy/release-signing-key.pub`，私钥离线保管，未配置公钥时拒绝自动更新（默认安全）。

---

## 🔌 下游客户端接入示例

任何兼容 OpenAI 接口的工具、插件或开源客户端均可无缝对接！

### 基础参数配置
- **API Base URL / 接口代理地址**：`http://<服务器IP>:7864/v1`
- **API Key**：你在面板「API 密钥」中创建的密钥（例如 `wbk_abcdef123456`）
- **模型名称**：支持腾讯 CodeBuddy 提供的所有模型（可在管理面板「模型中心」查看实时清单与积分扣率）

### Python SDK 示例
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:7864/v1",
    api_key="wbk_xxxxxxxxxxxxxxxx",
)

response = client.chat.completions.create(
    model="deepseek-v3",
    messages=[
        {"role": "system", "content": "你是一个严谨的代码助手"},
        {"role": "user", "content": "用 Go 写一个并发安全的缓存池"},
    ],
    stream=True,
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
print()
```

### 常用工具配置建议
| 客户端 | API Host / 接口地址 | 说明 |
|---|---|---|
| **NextChat / ChatGPT-Next-Web** | `http://<IP>:7864` | 勾选自定义接口，填入对应密钥 |
| **Cherry Studio** | `http://<IP>:7864/v1` | 选择 OpenAI 兼容提供商 |
| **Chatbox** | `http://<IP>:7864/v1` | 模型提供方选 OpenAI API |
| **Cursor / Cline / Roo Code** | `http://<IP>:7864/v1` | 设置 Base URL 与 API Key |
| **One API / New API** | `http://<IP>:7864` | 渠道类型选 OpenAI，模型重定向自由配置 |

---

## 📁 目录与持久化架构

```
workbuddyweb/
├── docker-compose.yml          # ⭐ 主力推荐：All-in-One 一键部署配置
├── docker-compose.separate.yml # 备选：双容器微服务部署配置
├── Dockerfile                  # All-in-One 镜像多阶段构建文件
├── Dockerfile.manager          # 独立构建 Manager 镜像
├── Dockerfile.wb2api           # 独立构建 workbuddy2api 镜像
├── .env.example                # 环境变量配置模板
├── deploy/                     # 一键更新器与部署模板
│   ├── update.py               # 更新执行脚本（单仓库模型，管理端与上游均跟随本仓库）
│   ├── release-signing-key.pub # 发布包签名公钥（未配置时拒绝自动更新）
│   ├── verify-release.sh       # 签名验证脚本
│   └── windows-native/         # Windows 原生运行批处理模板
│       ├── start-workbuddy2api.cmd
│       └── stop-workbuddy2api.cmd
├── entrypoint.sh               # 容器引导脚本（初始化配置、启停管控）
├── scripts/
│   ├── deploy.sh               # Linux 一键脚本
│   ├── deploy.ps1              # Windows 一键脚本
│   ├── start-upstream.sh       # 上游引擎热启脚本
│   ├── stop-upstream.sh        # 上游引擎优雅停机脚本
│   └── ts-logger.py            # RFC3339 毫秒日志格式化管道
├── config.default.json         # workbuddy2api 默认配置模板
├── upstream/                   # workbuddy2api 核心 Go 代码
├── server/                     # workbuddy-manager 核心 Python 代码
├── web/                        # 前端源码与预构建 web/out 资源
├── data/                       # 📂 持久化目录（SQLite、日志、config.json）
└── auths/                      # 📂 账号凭证持久化目录（workbuddy-*.json）
```

> ⚠️ **注意**：`data/` 与 `auths/` 目录中包含敏感的账号授权凭证与管理数据库，请**不要**将其提交到公共代码仓库！
>
> Windows 用户如需原生（非 Docker）运行上游网关，可参考 `deploy/windows-native/` 下的批处理模板。

---

## ⚙️ 环境变量配置参考 (`.env`)

### 基础配置

| 变量名 | 默认值 | 作用说明 |
|---|---|---|
| `PORT` | `7864` | 对外暴露的宿主机服务端口 |
| `WB_ADMIN_PASSWORD` | *(空)* | 首次启动初始管理员密码（留空则随机生成并打印在日志中） |
| `WB_TRUST_PROXY` | `1` | 信任前置反向代理（Nginx/1Panel 等）透传的真实客户端 IP |
| `WB_ENABLE_DOCS` | `0` | 是否在生产环境暴露 `/docs` OpenAPI 接口文档 |
| `WB_SESSION_DAYS` | `1` | 会话登录有效期（天），滑动续期 |
| `TZ` | `Asia/Shanghai` | 容器时区设置 |

### 网关与审计

| 变量名 | 默认值 | 作用说明 |
|---|---|---|
| `WB_GATEWAY_MAX_BODY_MB` | `32` | 网关请求体上限（MB），足够容纳常见长上下文与附件 |
| `WB_GATEWAY_RATE_PER_MIN` | `120` | 单 IP 每分钟最大请求数（`0` = 不限制） |
| `WB_AUDIT_ALL_ACCESS` | `0` | 设为 `1` 时恢复全量访问日志记录（默认只记录异常访问） |
| `WB_UPSTREAM_TIMEOUT` | `120` | 上游请求超时（秒），长推理场景可调大 |

### 镜像构建加速

| 变量名 | 默认值 | 作用说明 |
|---|---|---|
| `GOPROXY` | *(空)* | 镜像构建时的 Go 代理，国内可设为 `https://goproxy.cn,direct` |
| `PIP_INDEX_URL` | *(空)* | 镜像构建时的 PyPI 源，国内可设为 `https://pypi.tuna.tsinghua.edu.cn/simple` |
| `DEBIAN_MIRROR` | *(空)* | 镜像构建时的 Debian 源，国内可设为 `mirrors.aliyun.com` |

---

## 🌐 反向代理与 HTTPS 配置建议 (Nginx / 1Panel)

在公网环境提供服务时，强烈建议前置配置 Nginx 或 1Panel 并开启 HTTPS：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    client_max_body_size 16m;

    location / {
        proxy_pass http://127.0.0.1:7864;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;     # 必须足够长，确保流式推理（SSE）不被截断
    }
}
```

---

## 📄 开源许可与致谢

- 本项目融合并适配了以下优秀开源项目的能力：
  - [Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api) (MIT License)
  - [ithtelab/workbuddy-manager](https://github.com/ithtelab/workbuddy-manager) (MIT License)
- 遵循 MIT License 开源协议。本工具仅供技术研究与个人合规多账号管理，请遵守腾讯 CodeBuddy 平台服务条款。
