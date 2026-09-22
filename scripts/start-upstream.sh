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

# 检查是否已在运行（防止持久化目录残留旧 PID 造成误判）
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        if [ -d "/proc/$OLD_PID" ] && grep -q "wb2api" "/proc/$OLD_PID/cmdline" 2>/dev/null; then
            echo "workbuddy2api is already running (PID: $OLD_PID)"
            exit 0
        fi
    fi
    rm -f "$PID_FILE"
fi

# 日志轮转保护（超过 25MB 时保留上一份）
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 26214400 ]; then
        mv -f "$LOG_FILE" "${LOG_FILE}.1"
    fi
fi

mkdir -p /app/data /app/auths

# 使用 ts-logger.py 作为守护进程直接运行 wb2api，精准写入真实 PID 并输出时间戳日志
nohup python3 /app/scripts/ts-logger.py --pid-file "$PID_FILE" --run "$BIN" -config "$CONFIG_FILE" >> "$LOG_FILE" 2>&1 &

# 轮询等待 PID 文件就绪与进程存活确认 (最多 3 秒)
STARTED=0
for i in {1..15}; do
    if [ -f "$PID_FILE" ]; then
        CURR_PID=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$CURR_PID" ] && kill -0 "$CURR_PID" 2>/dev/null; then
            STARTED=1
            break
        fi
    fi
    sleep 0.2
done

if [ "$STARTED" -eq 0 ]; then
    echo "workbuddy2api failed to start. Check $LOG_FILE" >&2
    tail -n 25 "$LOG_FILE" 2>/dev/null || true
    exit 1
fi

echo "workbuddy2api started successfully (PID: $(cat "$PID_FILE"))"
exit 0
