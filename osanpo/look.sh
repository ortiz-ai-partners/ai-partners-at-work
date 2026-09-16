#!/bin/sh
# 手動テスト用: 画像を1枚 claude -p に見せて一言もらう
# 使い方: ./osanpo/look.sh path/to/photo.jpg
set -e
IMG="${1:-$(dirname "$0")/latest.jpg}"
exec claude -p "$IMG を見て、何が見えるか日本語で一文だけ言って。前置きも説明も不要。" --allowedTools Read
