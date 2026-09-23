#!/usr/bin/env bash
# 手动校验发布包签名（与 deploy/update.py 的自动验签同一信任锚）。
#
# 用法：
#   ./verify-release.sh <发布包.tar.gz> [签名文件.tar.gz.sig]
#
# 退出码：0 = 校验通过；2 = 签名校验失败；3 = 缺签名文件/公钥未配置。
# 校验未通过时请勿解压安装。
set -euo pipefail

SIGNER_ID="release-signing"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUB_FILE="$SCRIPT_DIR/release-signing-key.pub"

PKG="${1:-}"
SIG="${2:-}"

if [ -z "$PKG" ] || [ ! -f "$PKG" ]; then
    echo "用法: $0 <发布包.tar.gz> [签名文件.sig]" >&2
    exit 2
fi
if [ -z "$SIG" ]; then
    SIG="$PKG.sig"
fi
if [ ! -f "$SIG" ]; then
    echo "❌ 缺签名文件：$SIG —— 请勿解压安装" >&2
    exit 3
fi
if [ ! -f "$PUB_FILE" ]; then
    echo "❌ 公钥文件不存在：$PUB_FILE —— 请勿解压安装" >&2
    exit 3
fi
PUBKEY="$(head -n 1 "$PUB_FILE" | awk '{print $1" "$2}')"
if echo "$PUBKEY" | grep -q 'AAAA_REPLACE_ME'; then
    echo "❌ 公钥未配置（仍是占位值）—— 请勿解压安装" >&2
    exit 3
fi

ALLOWED="$(mktemp)"
trap 'rm -f "$ALLOWED"' EXIT
echo "$SIGNER_ID $PUBKEY" > "$ALLOWED"

if ssh-keygen -Y verify -f "$ALLOWED" -I "$SIGNER_ID" -n file -s "$SIG" < "$PKG"; then
    echo "✅ 签名校验通过，可以解压安装"
    exit 0
else
    echo "❌ 签名校验失败 —— 请勿解压安装" >&2
    exit 2
fi
