#!/usr/bin/env python3
"""前端产物构建分支自检。

历史 issue #38 的原始场景是：git clone 后没有 web/out，Dockerfile 里必须有
Node 阶段在容器内构建。当前仓库改为把 web/out 预构建产物提交进仓库/发布包，
因此分支逻辑简化为「产物存在则直接用；不存在则构建镜像会失败并提示」。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_INDEX = ROOT / 'web' / 'out' / 'index.html'
DF = ROOT / 'Dockerfile'


def main() -> int:
    errors: list[str] = []
    if not OUT_INDEX.is_file():
        errors.append('web/out/index.html 不存在：当前仓库采用预构建产物策略，'
                      '请先构建前端（cd web && npm install && npm run build）后再提交。')

    df_text = DF.read_text(encoding='utf-8')
    if 'COPY web/out/ /app/web/out/' not in df_text and \
       'COPY --from=frontend' not in df_text and \
       'COPY --from=node' not in df_text:
        errors.append('Dockerfile 没有把前端产物拷到 /app/web/out')

    if errors:
        for e in errors:
            print(f'ERROR: {e}', file=sys.stderr)
        return 1

    print('OK: 前端产物存在且 Dockerfile 会正确 COPY')
    return 0


if __name__ == '__main__':
    sys.exit(main())
