#!/usr/bin/env python3
"""内省: その子が日記を読み返して、memory.md（覚えたこと）を書き直す。

散歩の終わりや夜に1回走らせる。Claude Code 経由なので写真ごとの課金はない。
  python3 osanpo/reflect.py            # 前回の内省以降の日記を読む
  python3 osanpo/reflect.py --all      # 日記を最初から全部読み直す
サーバ経由: POST /reflect（合言葉つき）でも同じことが起きる。

memory.md はその子の長期記憶。server.py が写真を見るたびに渡す。
手で直してもよい（ゆうころが「これは違うよ」と書き換えるのも育て方のひとつ）。
"""
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from claude_cli import claude_command  # noqa: E402
DIARY_JSONL = os.path.join(HERE, 'diary.jsonl')
MEMORY = os.path.join(HERE, 'memory.md')
STATE = os.path.join(HERE, '.reflect_state')   # 最後に読んだ行数
PERSONA_NAME = os.environ.get('OSANPO_PERSONA', 'osanpo')
PERSONA = os.path.join(HERE, 'personas', PERSONA_NAME + '.md')
DISPLAY = {'osanpo': 'おさんぽの子', 'vert': 'ヴェルティ', 'ortiz': 'オルティス', 'yukoro': 'ゆうころ'}
MEMORY_MAX = int(os.environ.get('OSANPO_MEMORY_MAX', '3000'))  # 文字数の上限（渡すたびに読むので短く）

TEMPLATE = """# 覚えていること

## 自分について
（名前の候補、好きなもの、口ぐせ など。まだ無ければ空）

## よく見るもの・場所
（何度も見たもの。「〇〇の近くの赤い橋」のように、場所は特定せず特徴で）

## ゆうころ・はるくんについて
（教えてもらったこと、好きなもの、よく言うこと）

## 覚えたこと
（散歩で学んだこと。植物、生き物、季節、天気、街のこと）

## 気になっていること
（まだ答えを知らない疑問。次に聞きたいこと）
"""


def load(path, default=''):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return default


def new_entries(read_all):
    lines = load(DIARY_JSONL).splitlines()
    start = 0 if read_all else int(load(STATE, '0').strip() or 0)
    out = []
    for line in lines[start:]:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if str(e.get('text', '')).startswith(('(claude', '(頭脳省略', '(openai', '(無言)')):
            continue  # 失敗の跡は教材にしない
        who = DISPLAY.get(e.get('role'), e.get('role'))
        people = f"（映っていた人: {', '.join(e['people'])}）" if e.get('people') else ''
        out.append(f"{e.get('ts', '')} {who}: {e.get('text', '')}{people}")
    return out, len(lines)


def reflect(read_all=False):
    entries, total = new_entries(read_all)
    if not entries:
        print('新しい日記がない。内省は不要')
        return 0
    memory = load(MEMORY, TEMPLATE)
    prompt = f"""あなた自身の長期記憶「覚えていること」を、新しい日記を読んで書き直す作業です。

いまの「覚えていること」:
---
{memory}
---

新しい日記（{len(entries)}行）:
---
{chr(10).join(entries)}
---

やること:
- 新しく分かったこと・気づいたことを、該当する見出しの下に足す
- 前に書いたことと矛盾したら、新しい方に直す
- 何度も出てくるもの・人・場所は「よく見るもの」にまとめる
- 答えが分かった疑問は「気になっていること」から消して「覚えたこと」へ移す
- 自分の名前についてのやりとりがあれば「自分について」に残す
- 全体で{MEMORY_MAX}文字以内に収める。古くて重要でないことは削ってよい
- 場所の特定や、登録されていない人物の名前・特徴は書かない

出力は、書き直した「覚えていること」の全文だけ。前置きも説明も不要。見出し構成は保つ。"""
    base = claude_command()
    if not base:
        print('claude コマンドが見つからない')
        return 1
    cmd = base + ['-p', prompt]
    if os.path.exists(PERSONA):
        cmd += ['--append-system-prompt-file', PERSONA]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=300)
    text = r.stdout.strip()
    if not text.startswith('#'):
        print('内省の出力が想定外。memory.md は変更しない:\n' + (text or r.stderr)[:500])
        return 1
    if os.path.exists(MEMORY):
        os.replace(MEMORY, MEMORY + '.bak')
    with open(MEMORY, 'w', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n')
    with open(STATE, 'w') as f:
        f.write(str(total))
    print(f'[{datetime.now():%Y-%m-%d %H:%M}] 内省完了: 日記{len(entries)}行 → memory.md {len(text)}文字')
    return 0


if __name__ == '__main__':
    sys.exit(reflect('--all' in sys.argv))
