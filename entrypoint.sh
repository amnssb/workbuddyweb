#!/usr/bin/env bash
set -e

umask 0022

echo "================================================================="
echo "       🚀 启动 WorkBuddy All-in-One 融合一键部署容器             "
echo "================================================================="

mkdir -p /app/data /app/auths /app/scripts

# 1. 检查并初始化上游配置文件
CONFIG_FILE="/app/data/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "📦 未检测到现有配置，正在从模板生成 /app/data/config.json..."
    cp /app/config.default.json "$CONFIG_FILE"
    
    # 生成安全的随机上游 API Key
    RAND_KEY=$(python3 -c "import secrets; print('wbk_' + secrets.token_hex(16))")
    python3 -c "
import json
with open('$CONFIG_FILE', 'r', encoding='utf-8') as f:
    cfg = json.load(f)
cfg['api_key'] = '$RAND_KEY'
cfg['auth_dir'] = '/app/auths'
cfg['state_file'] = '/app/data/state.json'
with open('$CONFIG_FILE', 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
    echo "🔑 已自动生成上游内部 API Key: $RAND_KEY"
else
    echo "✅ 载入现有配置: $CONFIG_FILE"
fi

# 2. 导出上游 API Key 供 Manager 服务读取
UPSTREAM_KEY=$(python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r', encoding='utf-8') as f:
        print(json.load(f).get('api_key', ''))
except Exception:
    print('')
")
export WB2API_KEY="$UPSTREAM_KEY"

# 3. 启动上游引擎 workbuddy2api
echo "🔄 正在启动上游网关核心 (workbuddy2api)..."
/app/scripts/start-upstream.sh

# 等待上游健康检查响应 (最多 10 秒)
READY=0
for i in {1..20}; do
    if curl -s -f http://127.0.0.1:7863/healthz >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ "$READY" -eq 1 ]; then
    echo "✅ 上游网关已就绪 (127.0.0.1:7863)"
else
    echo "⚠️ 上游网关启动较慢或异常，请检查 /app/data/server.err.log"
fi

# 4. 信号优雅停机处理
cleanup() {
    echo ""
    echo "🛑 收到终止信号，正在优雅关闭所有服务..."
    /app/scripts/stop-upstream.sh || true
    if [ -n "$UVICORN_PID" ]; then
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
    echo "👋 服务已完全停止"
    exit 0
}
trap cleanup SIGTERM SIGINT

PORT="${WB_MANAGER_PORT:-7864}"
HOST="${WB_MANAGER_HOST:-0.0.0.0}"

echo "================================================================="
echo " 🎉 WorkBuddy 融合版服务已成功运行！"
echo " 🌐 控制台 Web 界面与 API 端口: http://${HOST}:${PORT}"
echo " 📂 凭证目录 (账号存储): /app/auths"
echo " 💾 数据目录 (数据库/日志): /app/data"
echo "================================================================="

# 5. 启动 WorkBuddy Manager 管理面板与反代网关
exec uvicorn server.main:app --host "$HOST" --port "$PORT"
