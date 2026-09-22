#!/usr/bin/env python3
"""ts-logger.py - 为日志添加 RFC3339 时间戳，并支持守护进程与 PID 留痕。"""
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone


def _now_iso() -> str:
    now_iso = datetime.now(timezone.utc).isoformat()
    if now_iso.endswith('+00:00'):
        now_iso = now_iso[:-6] + 'Z'
    return now_iso


def _write_line(line: str) -> None:
    iso = _now_iso()
    sys.stdout.write(f"{iso} {line}")
    sys.stdout.flush()


def run_process(cmd: list[str], pid_file: str | None = None) -> int:
    """直接拉起子进程守护运行，实时转发日志并记录真实 PID。"""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        _write_line(f"[ts-logger] 启动命令失败 {cmd}: {exc}\n")
        return 1

    if pid_file:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(pid_file)), exist_ok=True)
            with open(pid_file, 'w', encoding='utf-8') as f:
                f.write(str(proc.pid))
        except Exception as exc:
            _write_line(f"[ts-logger] 写入 PID 文件 {pid_file} 失败: {exc}\n")

    def _sig_handler(signum, frame):
        try:
            proc.send_signal(signum)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    try:
        if proc.stdout:
            for line in proc.stdout:
                _write_line(line)
    except (KeyboardInterrupt, BrokenPipeError):
        pass

    returncode = proc.wait()
    if pid_file and os.path.isfile(pid_file):
        try:
            # 只有 PID 依然是当前进程时才删除
            with open(pid_file, 'r', encoding='utf-8') as f:
                saved = f.read().strip()
            if saved == str(proc.pid):
                os.remove(pid_file)
        except Exception:
            pass

    return returncode


def run_stdin() -> None:
    """兼容旧有的管道输入模式。"""
    try:
        for line in sys.stdin:
            _write_line(line)
    except (KeyboardInterrupt, BrokenPipeError):
        pass


def main():
    args = sys.argv[1:]
    pid_file = None

    if '--pid-file' in args:
        idx = args.index('--pid-file')
        if idx + 1 < len(args):
            pid_file = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if '--run' in args:
        idx = args.index('--run')
        cmd = args[idx + 1:]
        if not cmd:
            sys.stderr.write("Error: --run requires a command to execute\n")
            sys.exit(1)
        sys.exit(run_process(cmd, pid_file))

    run_stdin()


if __name__ == '__main__':
    main()
