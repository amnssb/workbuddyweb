#!/usr/bin/env python3
"""Dockerfile 结构自检：不跑 docker build，但检查指令拼写 / 阶段引用 / shell 配平。

适合在本地和 CI 快速拦截常见错误（阶段名写错、FROM 拼错、shell 引号不配平等）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DF = ROOT / 'Dockerfile'

ERRORS: list[str] = []


def error(msg: str) -> None:
    ERRORS.append(msg)
    print(f'ERROR: {msg}', file=sys.stderr)


def main() -> int:
    if not DF.is_file():
        error(f'Dockerfile 不存在: {DF}')
        return 1

    text = DF.read_text(encoding='utf-8')
    lines = text.splitlines()

    if not lines or not lines[0].strip():
        error('Dockerfile 为空')
        return 1

    # 必须有 FROM
    froms = [ln for ln in lines if re.match(r'^FROM\s+', ln.strip(), re.I)]
    if not froms:
        error('缺少 FROM 指令')

    stages: set[str] = set()
    for ln in froms:
        m = re.search(r'\sAS\s+(\S+)', ln, re.I)
        if m:
            stages.add(m.group(1).lower())

    # COPY --from= 引用的阶段必须存在
    for i, ln in enumerate(lines, 1):
        m = re.search(r'COPY\s+--from=(\S+)', ln, re.I)
        if m:
            stage = m.group(1).lower()
            if stage not in stages and not stage.startswith('0'):
                error(f'第 {i} 行引用了未声明的阶段: {m.group(1)}')

    # 基础 shell 引号检查（粗略）：偶数个未转义单双引号
    for i, ln in enumerate(lines, 1):
        stripped = ln.split('#', 1)[0]
        if not stripped.strip().startswith('RUN'):
            continue
        # 去掉转义引号后统计
        simplified = re.sub(r'\\[\"\']', '', stripped)
        if simplified.count('"') % 2 != 0:
            error(f'第 {i} 行 RUN 中双引号可能未配平')
        if simplified.count("'") % 2 != 0:
            error(f'第 {i} 行 RUN 中单引号可能未配平')

    # 必须有 USER 非 root 与 HEALTHCHECK
    if not re.search(r'^USER\s+\S+', text, re.M | re.I):
        error('缺少 USER 指令 —— 容器不应以 root 运行')
    if not re.search(r'^HEALTHCHECK', text, re.M | re.I):
        error('缺少 HEALTHCHECK')

    # 容器形态标识
    if 'WB_RUN_MODE=docker' not in text:
        error('缺少 WB_RUN_MODE=docker 环境变量')

    return 1 if ERRORS else 0


if __name__ == '__main__':
    sys.exit(main())
