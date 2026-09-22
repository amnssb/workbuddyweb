# syntax=docker/dockerfile:1
# ==============================================================================
# WorkBuddy All-in-One 融合一键部署镜像
# 融合组件：
#   - Upstream Gateway: workbuddy2api (Go 1.23+ 账号调度引擎与 OpenAI 兼容代理)
#   - Management Console: workbuddy-manager (FastAPI 后端 + Next.js 静态控制台)
# ==============================================================================

# ── 阶段 1：构建上游 Go 二进制 ─────────────────────────────────
FROM golang:1.23-alpine AS upstream-builder

ARG GOPROXY=""
ENV GOPROXY=${GOPROXY:-https://proxy.golang.org,direct}

WORKDIR /src
COPY upstream/go.mod upstream/go.sum ./
RUN go mod download

COPY upstream/ .
RUN mkdir -p /out \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/wb2api ./cmd/server \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/signin_bin ./cmd/signin \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/login ./cmd/login \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/credit ./cmd/credit \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/trial_bin ./cmd/trial \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/activity_bin ./cmd/activity

# ── 阶段 2：运行容器 ───────────────────────────────────────────
FROM python:3.12-slim AS runtime

ARG DEBIAN_MIRROR=""
ARG PIP_INDEX_URL=""

RUN set -eu; \
    if [ -n "${DEBIAN_MIRROR}" ]; then \
        sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
        sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list 2>/dev/null || true; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tzdata \
        procps \
        bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY server/requirements.txt /tmp/requirements.txt
RUN set -eu; \
    pip_install() { \
        pip install --no-cache-dir ${1:+--index-url="$1"} -r /tmp/requirements.txt; \
    }; \
    if [ -n "${PIP_INDEX_URL}" ]; then \
        pip_install "${PIP_INDEX_URL}"; \
    elif ! pip_install ""; then \
        echo "官方 PyPI 源连接缓慢或超时，自动切换清华大学镜像重试..."; \
        pip_install "https://pypi.tuna.tsinghua.edu.cn/simple"; \
    fi; \
    rm -f /tmp/requirements.txt

# 注入 Go 二进制组件
COPY --from=upstream-builder /out/* /app/bin/

# 注入管理端后端与静态前端资源
COPY server/ /app/server/
COPY web/out/ /app/web/out/

# 注入配置与启停脚本
COPY config.default.json /app/config.default.json
COPY scripts/ /app/scripts/
COPY entrypoint.sh /app/entrypoint.sh

# 统一换行符并添加可执行权限
RUN set -eu; \
    sed -i 's/\r$//' /app/entrypoint.sh /app/scripts/*.sh /app/scripts/*.py 2>/dev/null || true; \
    chmod +x /app/entrypoint.sh /app/scripts/*.sh /app/scripts/*.py /app/bin/*; \
    mkdir -p /app/data /app/auths

# 默认运行环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    WB_RUN_MODE=docker \
    WB2API_MODE=native \
    WB2API_BASE=http://127.0.0.1:7863 \
    WB_MANAGER_HOST=0.0.0.0 \
    WB_MANAGER_PORT=7864 \
    WB_INSTALL_DIR=/app \
    WB_DATA_DIR=/app/data \
    WB_STATIC_DIR=/app/web/out \
    WB_AUTH_DIR=/app/auths \
    WB_UPSTREAM_CONFIG=/app/data/config.json \
    WB_UPSTREAM_DIR=/app/data \
    WB2API_START_SCRIPT=/app/scripts/start-upstream.sh \
    WB2API_STOP_SCRIPT=/app/scripts/stop-upstream.sh \
    WB2API_LOG_FILE=/app/data/server.err.log \
    PATH="/app/bin:$PATH"

VOLUME ["/app/data", "/app/auths"]

EXPOSE 7864

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:7864/api/healthz || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
