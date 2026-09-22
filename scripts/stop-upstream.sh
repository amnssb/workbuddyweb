#!/usr/bin/env bash
set -e

PID_FILE="/app/data/wb2api.pid"

if [ ! -f "$PID_FILE" ]; then
    # 若无 PID 文件，兜底尝试通过进程名关闭
    pkill -f "wb2api" 2>/dev/null || true
    exit 0
fi

PID=$(cat "$PID_FILE" 2>/dev/null || true)
if [ -z "$PID" ]; then
    rm -f "$PID_FILE"
    exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping workbuddy2api (PID $PID)..."
    kill -15 "$PID" 2>/dev/null || true
    for i in {1..25}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "Force killing workbuddy2api (PID $PID)..."
        kill -9 "$PID" 2>/dev/null || true
    fi
fi

rm -f "$PID_FILE"
echo "workbuddy2api stopped"
exit 0
