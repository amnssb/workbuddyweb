#!/usr/bin/env python3
"""issue 回复风格检查器。

规则见 docs/release-process.md。只检查**面向用户**的公开 issue 回复：
  - 不能出现内部标识符、提交哈希、模块路径；
  - 不能是排障笔记/自我检讨式叙事；
  - 不能罗列测试与验收清单；
  - 不能带客服/AI 模板腔；
  - 篇幅与结构要克制。

例外：用户原文里出现过的字段名/路径可以引用（issue_text 参数）。
"""
from __future__ import annotations

import re


class Finding:
    def __init__(self, rule: str, token: str, line: int = 1) -> None:
        self.rule = rule
        self.token = token
        self.line = line

    def __repr__(self) -> str:
        return f'Finding(rule={self.rule!r}, token={self.token!r}, line={self.line})'


# ── 规则 1：内部标识符 ─────────────────────────────────────
# 反引号里的 snake_case / dot.path / 提交哈希 / 方法+路径，都是内部实现细节。
# 例外：全大写环境变量、纯 URL、以及 issue 原文里出现过的内容。
_BACKTICK_RE = re.compile(r'`([^`]+)`')


def _is_url(token: str) -> bool:
    return token.startswith(('http://', 'https://'))


def _is_env_var(token: str) -> bool:
    return bool(re.fullmatch(r'[A-Z][A-Z0-9_]*', token))


def _looks_internal(token: str) -> bool:
    if _is_env_var(token) or _is_url(token):
        return False
    # 提交哈希
    if re.fullmatch(r'[a-f0-9]{7,}', token):
        return True
    # 方法 + 路径，如 POST /api/accounts/refresh
    if re.search(r'^[A-Z]+\s+/', token):
        return True
    # dot.path / 文件路径
    if re.search(r'[a-z_][a-z0-9_]*\.[a-z_/]', token) or re.search(r'[a-z_/]+\.py\b', token):
        return True
    # snake_case 含下划线（下划线在中文技术写作里几乎就是内部变量）
    if re.fullmatch(r'_?[a-z]+[a-z0-9_]*', token) and '_' in token:
        return True
    return False


def _internal_id_findings(text: str, issue_text: str | None) -> list[Finding]:
    out = []
    issue = issue_text or ''
    for line_no, line in enumerate(text.splitlines(), 1):
        for token in _BACKTICK_RE.findall(line):
            if token in issue:
                continue
            if _looks_internal(token):
                out.append(Finding('内部标识符', token, line_no))
    return out


# ── 规则 2：排障笔记 / 自我检讨式叙事 ───────────────────────
_NARRATIVE_PATTERNS = [
    r'我的回复惯性',
    r'排障笔记',
    r'自我检讨',
    r'检讨式',
    r'我的疏漏',
    r'顺手把',
    r'刚写完代码',
    r'记一下',
    r'顺带发现',
    r'差点做成',
]


def _narrative_findings(text: str) -> list[Finding]:
    out = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for pat in _NARRATIVE_PATTERNS:
            if re.search(pat, line):
                out.append(Finding('检讨式叙事', pat, line_no))
    return out


# ── 规则 3：测试 / 验收清单 ─────────────────────────────────
_TEST_PATTERNS = [
    r'验证[：:]',
    r'全量\s*\d+\s*条通过',
    r'\be2e\b',
    r'浏览器验收',
    r'验收\s*(?:脚本|清单|通过)',
    r'不变量测试',
    r'反证确认',
    r'(?:回归|单元|集成)测试',
]


def _test_findings(text: str) -> list[Finding]:
    out = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for pat in _TEST_PATTERNS:
            m = re.search(pat, line)
            if m:
                out.append(Finding('测试/验收清单', m.group(0), line_no))
    return out


# ── 规则 4：AI / 客服模板腔 ─────────────────────────────────
_AI_BOILERPLATE = [
    '感谢您的反馈！已修复。',
    '希望这能帮助到您。',
    '如有任何疑问，请随时与我们联系。',
    '需要注意的是，该行为已改变。',
    '首先列出结论，其次说明步骤。',
    '给您带来不便，敬请谅解。',
]


def _ai_findings(text: str) -> list[Finding]:
    out = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for phrase in _AI_BOILERPLATE:
            if phrase in line:
                out.append(Finding('AI/客服模板腔', phrase, line_no))
    return out


# ── 规则 5：篇幅与结构 ─────────────────────────────────────
_LINE_LIMIT = 15
_HEADING_LIMIT = 2


def check_shape(text: str) -> list[Finding]:
    """检查篇幅与结构（与内容规则独立，方便单独断言）。"""
    out = []
    lines = text.splitlines()
    if len(lines) > _LINE_LIMIT:
        out.append(Finding('长度', f'共 {len(lines)} 行，建议控制在 {_LINE_LIMIT} 行以内', 1))
    headings = sum(1 for ln in lines if re.match(r'^#{2,6}\s', ln.strip()))
    if headings >= _HEADING_LIMIT:
        out.append(Finding('结构', f'使用了 {headings} 个小标题，建议直接分段', 1))
    return out


def check(text: str, issue_text: str | None = None) -> list[Finding]:
    """检查回复文本，返回发现的问题列表。"""
    return (
        _internal_id_findings(text, issue_text)
        + _narrative_findings(text)
        + _test_findings(text)
        + _ai_findings(text)
    )


if __name__ == '__main__':
    import sys

    text = sys.stdin.read()
    findings = check(text)
    for f in findings:
        print(f'{f.line}: {f.rule}: {f.token}')
    sys.exit(1 if findings else 0)
