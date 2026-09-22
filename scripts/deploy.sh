#!/usr/bin/env bash
# ==============================================================================
# WorkBuddy All-in-One Linux 一键部署与启动脚本
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "================================================================="
echo "       🚀 WorkBuddy All-in-One 容器化一键部署助手               "
echo "================================================================="

# 1. 检查 Docker 环境
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker！" >&2
    echo "   官方快速安装脚本: curl -fsSL https://get.docker.com | sh" >&2
    exit 1
fi

COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未检测到 Docker Compose，请安装 Docker Compose 插件！" >&2
    exit 1
fi

# 2. 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "📝 未检测到 .env 配置文件，正在从 .env.example 复制..."
    cp .env.example .env
fi

# 3. 创建持久化数据与凭据目录
mkdir -p data auths
# 确保在 Linux 下权限正常
chmod 755 data auths 2>/dev/null || true

# 4. 构建并启动容器
echo "🔨 正在构建并拉起 WorkBuddy 融合容器..."
$COMPOSE_CMD up -d --build

echo ""
echo "⏳ 等待服务健康检查..."
sleep 3

# 5. 读取端口与状态
PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d '=' -f2 | tr -d ' ' || echo "7864")
PORT=${PORT:-7864}

echo ""
echo "================================================================="
echo " 🎉 WorkBuddy All-in-One 部署完成并已在后台运行！"
echo " 🌐 控制台访问地址: http://127.0.0.1:${PORT}"
echo " 🔑 API 反代端点:   http://127.0.0.1:${PORT}/v1"
echo " 📋 默认登录账号:   admin"
echo ""
echo " 🔍 查看首次生成的初始密码或实时日志，可运行："
echo "     $COMPOSE_CMD logs -f workbuddy"
echo "================================================================="
