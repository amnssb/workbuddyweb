#!/usr/bin/env bash
# WorkBuddy 宿主机安装脚本
# 用法：curl -fsSL .../install.sh | bash
set -euo pipefail

INSTALL_DIR="${WB_INSTALL_DIR:-/opt/workbuddyweb}"
REPO="${WB_REPO:-amnssb/workbuddyweb}"
REF="${WB_REF:-main}"

log() { echo "[workbuddy-install] $*"; }

die() { echo "[workbuddy-install] ERROR: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "请先安装 git"
command -v docker >/dev/null 2>&1 || die "请先安装 docker"

if [ -d "$INSTALL_DIR/.git" ]; then
    log "目录已存在，更新到 $REF"
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "$REF"
    git pull
else
    log "克隆仓库到 $INSTALL_DIR"
    git clone "https://github.com/$REPO.git" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    git checkout "$REF"
fi

# 复制双语文档到安装目录，确保用户能同时看到中文版和英文版
log "同步文档"
for doc in README.md README.en.md CHANGELOG.md; do
    if [ -f "$doc" ]; then
        cp -f "$doc" "$INSTALL_DIR/$doc"
    fi
done

# 默认目录权限
cd "$INSTALL_DIR"
mkdir -p data auths
chmod 755 data auths

log "启动服务（docker compose）"
if docker compose version >/dev/null 2>&1; then
    docker compose up -d --build
elif docker-compose version >/dev/null 2>&1; then
    docker-compose up -d --build
else
    die "未找到 docker compose 或 docker-compose"
fi

log "安装完成。Web 控制台：http://<服务器IP>:7864"
