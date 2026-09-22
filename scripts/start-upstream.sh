#!/usr/bin/env bash
set -e

PID_FILE="/app/data/wb2api.pid"
CONFIG_FILE="/app/data/config.json"
LOG_FILE="/app/data/server.err.log"
BIN="/app/bin/wb2api"

if [ ! -x "$BIN" ]; then
    if [ -x "/usr/local/bin/wb2api" ]; then
        BIN="/usr/local/bin/wb2api"
    else
        echo "Error: wb2api binary not found" >&2
        exit 1
    fi
fi

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "workbuddy2api is already running (PID: $OLD_PID)"
        exit 0
    fi
fi

# 日志轮转保护（超过 25MB 时保留上一份）
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 26214400 ]; then
        mv -f "$LOG_FILE" "${LOG_FILE}.1"
    fi
fi

mkdir -p /app/data /app/auths

# 后台启动并通过 ts-logger.py 格式化时间戳写入日志文件
nohup "$BIN" -config "$CONFIG_FILE" 2>&1 | python3 /app/scripts/ts-logger.py >> "$LOG_FILE" &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

# 快速检测进程存活
sleep 0.4
if ! kill -0 "$NEW_PID" 2>/dev/null; then
    echo "workbuddy2api failed to start. Check $LOG_FILE" >&2
    exit 1
fi

echo "workbuddy2api started successfully (PID: $NEW_PID)"
exit 0
