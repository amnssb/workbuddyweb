#!/usr/bin/env bash
set -e

PID_FILE="/app/data/wb2api.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
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
fi

# 兜底清理任何残留的 wb2api 进程
pkill -f "wb2api" 2>/dev/null || true
echo "workbuddy2api stopped"
exit 0
