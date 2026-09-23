# WorkBuddy All-in-One Deployment

<div align="center">

**Tencent CodeBuddy Account Pool Gateway (`workbuddy2api`) + Web Management Console (`workbuddy-manager`) in a single container image**

Zero manual configuration · No cross-container permission hell · No Docker socket mount risk · Works out of the box

[![Docker Compose](https://img.shields.io/badge/Deploy-Docker_Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Go](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go&logoColor=white)](upstream/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](server/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](web/)
[![License](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)

[简体中文](README.md) · English

</div>

---

## Why this all-in-one edition?

The original upstream projects are independent:
1. **[workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)**: the Go gateway handling OAuth device flow, multi-account scheduling, rate-limiting and OpenAI-compatible protocol conversion (port `:7863`). No web UI.
2. **workbuddy-manager**: the Python FastAPI + Next.js management console and reverse proxy (port `:7864`).

**Pain points of the old separate deployment**:
- Two repositories to clone and wire together;
- Cross-container networking (`host.docker.internal` quirks on Linux);
- `/var/run/docker.sock` privilege-escalation risk;
- `uid 10001` permission mismatch causing `unable to open database file` or failed `auths` writes;
- Manual `api_key` alignment.

**This project provides a real one-click fusion**:
- Full-featured single container: Go gateway + Python/Next.js console exposed on one port (`:7864`);
- No Docker socket required: the console manages the upstream engine via an internal supervisor;
- Auto initialization on first start, with pre-built static frontend assets;
- WeChat/QQ QR-code account onboarding and automated daily tasks.

---

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
cd workbuddyweb
docker compose up -d --build
```

After startup:
- Web console: `http://your-server-ip:7864`
- OpenAI-compatible API: `http://your-server-ip:7864/v1`
- Default admin: `admin`
- Initial password: auto-generated on first start, view with:
  ```bash
  docker compose logs workbuddy | grep -A 2 "初始管理员"
  ```
  *(Or set `WB_ADMIN_PASSWORD` in `.env` beforehand.)*

---

### Option 2: One-click deployment script

- **Linux / macOS**:
  ```bash
  chmod +x scripts/deploy.sh
  ./scripts/deploy.sh
  ```
- **Windows (PowerShell)**:
  ```powershell
  .\scripts\deploy.ps1
  ```

---

### Option 3: Single docker run command

For Synology NAS, Unraid, CasaOS, 1Panel, etc.:

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

### Option 4: Dual-container micro-service mode (optional)

```bash
docker compose -f docker-compose.separate.yml up -d --build
```

---

## Core Workflow

### 1. Login and change password
Open `http://<server-ip>:7864` and log in with `admin` and the initial password. Change the password immediately.

### 2. Add CodeBuddy account via QR code
1. Go to **Account Management**;
2. Click **Add Account**;
3. Scan the QR code with WeChat or QQ and confirm on your phone;
4. The system completes auth, trial claim, credential save and upstream engine reload automatically.

### 3. Create and distribute API keys
1. Go to **API Keys**;
2. Click **Create Key** and configure region (CN / Global), IP allow-list, model allow-list and token quota;
3. The generated `wbk_xxxxxxxx` key is the Bearer Token for downstream clients.

---

## Downstream Client Examples

### Basic parameters
- **API Base URL**: `http://<server-ip>:7864/v1`
- **API Key**: the key created in the console (e.g. `wbk_abcdef123456`)
- **Model name**: any model provided by Tencent CodeBuddy

### Python SDK example
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:7864/v1",
    api_key="wbk_xxxxxxxxxxxxxxxx",
)

response = client.chat.completions.create(
    model="deepseek-v3",
    messages=[
        {"role": "system", "content": "You are a careful coding assistant"},
        {"role": "user", "content": "Write a concurrency-safe cache pool in Go"},
    ],
    stream=True,
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
print()
```

### Common clients
| Client | API Host |
|---|---|
| **NextChat / ChatGPT-Next-Web** | `http://<IP>:7864` |
| **Cherry Studio** | `http://<IP>:7864/v1` |
| **Chatbox** | `http://<IP>:7864/v1` |
| **Cursor / Cline / Roo Code** | `http://<IP>:7864/v1` |
| **One API / New API** | `http://<IP>:7864` |

---

## Directory Layout

```
workbuddyweb/
├── docker-compose.yml          # Recommended all-in-one deployment
├── docker-compose.separate.yml # Optional dual-container mode
├── Dockerfile                  # All-in-one multi-arch image
├── Dockerfile.manager          # Standalone manager image
├── Dockerfile.wb2api           # Standalone gateway image
├── .env.example                # Environment variable template
├── deploy/                     # Updater and deployment templates
│   ├── update.py               # Update executor
│   ├── release-signing-key.pub # Release package signing public key
│   ├── verify-release.sh       # Signature verification script
│   └── windows-native/         # Windows native batch templates
│       ├── start-workbuddy2api.cmd
│       └── stop-workbuddy2api.cmd
├── entrypoint.sh               # Container bootstrap script
├── scripts/
│   ├── deploy.sh
│   ├── deploy.ps1
│   ├── start-upstream.sh
│   ├── stop-upstream.sh
│   └── ts-logger.py
├── config.default.json
├── upstream/                   # workbuddy2api Go code
├── server/                     # workbuddy-manager Python code
├── web/                        # Frontend pre-built assets
├── data/                       # SQLite, logs, config.json
└── auths/                      # Account credentials
```

> `data/` and `auths/` contain sensitive credentials. **Do not commit them to public repositories.**
>
> Windows users who want to run the upstream gateway natively (without Docker) can use the batch templates in `deploy/windows-native/`.

---

## Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PORT` | `7864` | Host port exposed to the outside |
| `WB_ADMIN_PASSWORD` | *(empty)* | Initial admin password; auto-generated if empty |
| `WB_TRUST_PROXY` | `1` | Trust real client IP forwarded by reverse proxy |
| `WB_ENABLE_DOCS` | `0` | Expose `/docs` OpenAPI docs in production |
| `TZ` | `Asia/Shanghai` | Container timezone |
| `GOPROXY` | *(empty)* | Go proxy for image build |
| `PIP_INDEX_URL` | *(empty)* | PyPI mirror for image build |

---

## Reverse Proxy / HTTPS (Nginx / 1Panel)

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
        proxy_read_timeout 300s;
    }
}
```

---

## License and Acknowledgements

This project builds on:
- [Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api) (MIT License)
- [ithtelab/workbuddy-manager](https://github.com/ithtelab/workbuddy-manager) (MIT License)

Licensed under MIT. For research and personal multi-account management only. Please comply with Tencent CodeBuddy terms of service.
