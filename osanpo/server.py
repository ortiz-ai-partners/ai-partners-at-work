#!/usr/bin/env python3
"""お散歩Claude 受信サーバ（依存パッケージなし・Python標準ライブラリのみ）

StackChan（や、テスト用のスマホ/curl）が POST /upload でJPEGを送ってくると、
  1. osanpo/shots/YYYYmmdd-HHMMSS.jpg として保存
  2. osanpo/latest.jpg を上書き
  3. バックグラウンドで `claude -p` に見せて一言を latest.txt に書く
     （persona.md の人格で、diary.jsonl の直近の会話を踏まえて答える）
  4. diary.jsonl（機械用）と diary.log（人間用）に追記

ゆうころは POST /reply（本文=返事）で会話を返せる。index.html に入力欄がある。
StackChanは GET /latest.txt でコメントを取りに来て、喋ればいい。

diary.jsonl の1行: {"ts": "...", "role": "vert" | "yukoro", "text": "...", "photo": "shots/....jpg" | null}
これは将来「ご自宅LLM」を育てる教材になるので、消さないこと。

使い方:
  python3 osanpo/server.py                # 通常
  OSANPO_NO_CLAUDE=1 python3 osanpo/server.py   # claudeを呼ばず保存だけ（配線テスト用）
  OSANPO_TOKEN=合言葉 python3 osanpo/server.py   # 外に公開するときは必須。合言葉なしの荷物は拒否する
テスト:
  curl -X POST -H 'Content-Type: image/jpeg' -H 'X-Osanpo-Token: 合言葉' \
       --data-binary @photo.jpg http://localhost:5072/upload
ブラウザ: http://localhost:5072/?token=合言葉
"""
import json
import os
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, 'shots')
LATEST_JPG = os.path.join(HERE, 'latest.jpg')
LATEST_TXT = os.path.join(HERE, 'latest.txt')
DIARY = os.path.join(HERE, 'diary.log')
DIARY_JSONL = os.path.join(HERE, 'diary.jsonl')
PERSONA = os.path.join(HERE, 'persona.md')
PORT = int(os.environ.get('OSANPO_PORT', '5072'))
NO_CLAUDE = os.environ.get('OSANPO_NO_CLAUDE') == '1'
TOKEN = os.environ.get('OSANPO_TOKEN', '')   # 空なら家の中限定の無防備モード
PROMPT = os.environ.get(
    'OSANPO_PROMPT',
    '{path} を見て、いま何が見えるかを言って。',
)
CONTEXT_TURNS = int(os.environ.get('OSANPO_CONTEXT_TURNS', '8'))  # 直近何発言を渡すか
MAX_BYTES = 4 * 1024 * 1024

lock = threading.Lock()


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def diary_append(role, text, photo=None):
    """双方の発言を時系列で残す。lock を取った上で呼ぶ。"""
    entry = {'ts': now(), 'role': role, 'text': text, 'photo': photo}
    with open(DIARY_JSONL, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    name = {'vert': 'ヴェルティ', 'yukoro': 'ゆうころ'}.get(role, role)
    with open(DIARY, 'a', encoding='utf-8') as f:
        f.write(f"{entry['ts']}\t{name}\t{text}\n")


def recent_dialogue(n):
    """直近n発言を「名前: 発言」の形で返す。無ければ空文字。"""
    try:
        with open(DIARY_JSONL, encoding='utf-8') as f:
            lines = f.readlines()[-n:]
    except FileNotFoundError:
        return ''
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        name = {'vert': 'ヴェルティ', 'yukoro': 'ゆうころ'}.get(e.get('role'), e.get('role'))
        out.append(f"{name}: {e.get('text', '')}")
    return '\n'.join(out)


def ask_claude(path):
    """claude -p に画像を見せて、ヴェルティとして一言もらう。失敗しても落とさない。"""
    if NO_CLAUDE:
        return '(claude省略: OSANPO_NO_CLAUDE=1)'
    prompt = PROMPT.format(path=path)
    ctx = recent_dialogue(CONTEXT_TURNS)
    if ctx:
        prompt = f'これまでの散歩の会話:\n{ctx}\n\n{prompt}'
    cmd = ['claude', '-p', prompt, '--allowedTools', 'Read']
    try:
        with open(PERSONA, encoding='utf-8') as f:
            cmd += ['--append-system-prompt', f.read()]
    except FileNotFoundError:
        pass
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return (r.stdout.strip() or r.stderr.strip() or '(無言)').replace('\n', ' ')
    except FileNotFoundError:
        return '(claude コマンドが見つからない)'
    except subprocess.TimeoutExpired:
        return '(claude タイムアウト)'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 標準のアクセスログは静かに
        pass

    def authorized(self):
        """合言葉チェック。ヘッダ X-Osanpo-Token か ?token= のどちらかで受ける。"""
        if not TOKEN:
            return True
        given = self.headers.get('X-Osanpo-Token', '')
        if not given and '?' in self.path:
            for kv in self.path.split('?', 1)[1].split('&'):
                if kv.startswith('token='):
                    given = kv[6:]
        return given == TOKEN

    def do_POST(self):
        route = self.path.split('?')[0]
        if not self.authorized():
            return self.send_error(403, 'bad token')
        if route == '/reply':
            return self.reply()
        if route != '/upload':
            return self.send_error(404)
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0 or n > MAX_BYTES:
            return self.send_error(413, 'bad size')
        body = self.rfile.read(n)
        if not body.startswith(b'\xff\xd8'):
            return self.send_error(400, 'not a JPEG')
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        shot = os.path.join(SHOTS, ts + '.jpg')
        with lock:
            os.makedirs(SHOTS, exist_ok=True)
            with open(shot, 'wb') as f:
                f.write(body)
            with open(LATEST_JPG, 'wb') as f:
                f.write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok\n')
        print(f'[{ts}] 受信 {n} bytes', flush=True)
        threading.Thread(target=self.look, args=(ts, shot), daemon=True).start()

    def look(self, ts, shot):
        text = ask_claude(LATEST_JPG)
        with lock:
            with open(LATEST_TXT, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            diary_append('vert', text, os.path.relpath(shot, HERE))
        print(f'[{ts}] ヴェルティ: {text}', flush=True)

    def reply(self):
        """ゆうころの返事を日記に残す。本文はUTF-8のプレーンテキスト。"""
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0 or n > 4096:
            return self.send_error(413, 'bad size')
        text = self.rfile.read(n).decode('utf-8', 'replace').strip()
        if not text:
            return self.send_error(400, 'empty')
        with lock:
            diary_append('yukoro', text)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok\n')
        print(f'[{now()}] ゆうころ: {text}', flush=True)

    def do_GET(self):
        if not self.authorized():
            return self.send_error(403, 'bad token')
        route = self.path.split('?')[0]
        if route == '/latest.txt':
            return self.send_file(LATEST_TXT, 'text/plain; charset=utf-8')
        if route == '/latest.jpg':
            return self.send_file(LATEST_JPG, 'image/jpeg')
        if route == '/diary.txt':
            return self.send_file(DIARY, 'text/plain; charset=utf-8')
        if route == '/':
            return self.send_file(os.path.join(HERE, 'index.html'), 'text/html; charset=utf-8')
        self.send_error(404)

    def send_file(self, path, ctype):
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except FileNotFoundError:
            return self.send_error(404, 'not yet')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    print(f'osanpo server on http://0.0.0.0:{PORT}  (claude: {"OFF" if NO_CLAUDE else "ON"}, token: {"SET" if TOKEN else "NONE - 家の中限定"})')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
