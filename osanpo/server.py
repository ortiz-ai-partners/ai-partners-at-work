#!/usr/bin/env python3
"""お散歩Claude 受信サーバ（依存パッケージなし・Python標準ライブラリのみ）

StackChan（や、テスト用のスマホ/curl）が POST /upload でJPEGを送ってくると、
  1. osanpo/shots/YYYYmmdd-HHMMSS.jpg として保存
  2. osanpo/latest.jpg を上書き
  3. バックグラウンドで `claude -p` に見せて「何が見えるか一言」を latest.txt に書く
  4. diary.log に時刻とコメントを追記

StackChanは GET /latest.txt でコメントを取りに来て、喋ればいい。

使い方:
  python3 osanpo/server.py                # 通常
  OSANPO_NO_CLAUDE=1 python3 osanpo/server.py   # claudeを呼ばず保存だけ（配線テスト用）
  OSANPO_TOKEN=合言葉 python3 osanpo/server.py   # 外に公開するときは必須。合言葉なしの荷物は拒否する
テスト:
  curl -X POST -H 'Content-Type: image/jpeg' -H 'X-Osanpo-Token: 合言葉' \
       --data-binary @photo.jpg http://localhost:5072/upload
ブラウザ: http://localhost:5072/?token=合言葉
"""
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
PORT = int(os.environ.get('OSANPO_PORT', '5072'))
NO_CLAUDE = os.environ.get('OSANPO_NO_CLAUDE') == '1'
TOKEN = os.environ.get('OSANPO_TOKEN', '')   # 空なら家の中限定の無防備モード
PROMPT = os.environ.get(
    'OSANPO_PROMPT',
    '{path} を見て、何が見えるか日本語で一文だけ言って。前置きも説明も不要。',
)
MAX_BYTES = 4 * 1024 * 1024

lock = threading.Lock()


def ask_claude(path):
    """claude -p に画像を見せて一言もらう。失敗しても落とさない。"""
    if NO_CLAUDE:
        return '(claude省略: OSANPO_NO_CLAUDE=1)'
    cmd = ['claude', '-p', PROMPT.format(path=path), '--allowedTools', 'Read']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return (r.stdout.strip() or r.stderr.strip() or '(無言)').splitlines()[0]
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
        if self.path.split('?')[0] != '/upload':
            return self.send_error(404)
        if not self.authorized():
            return self.send_error(403, 'bad token')
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0 or n > MAX_BYTES:
            return self.send_error(413, 'bad size')
        body = self.rfile.read(n)
        if not body.startswith(b'\xff\xd8'):
            return self.send_error(400, 'not a JPEG')
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        with lock:
            os.makedirs(SHOTS, exist_ok=True)
            with open(os.path.join(SHOTS, ts + '.jpg'), 'wb') as f:
                f.write(body)
            with open(LATEST_JPG, 'wb') as f:
                f.write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok\n')
        print(f'[{ts}] 受信 {n} bytes', flush=True)
        threading.Thread(target=self.look, args=(ts,), daemon=True).start()

    def look(self, ts):
        text = ask_claude(LATEST_JPG)
        with lock:
            with open(LATEST_TXT, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            with open(DIARY, 'a', encoding='utf-8') as f:
                f.write(f'{ts}\t{text}\n')
        print(f'[{ts}] {text}', flush=True)

    def do_GET(self):
        if not self.authorized():
            return self.send_error(403, 'bad token')
        route = self.path.split('?')[0]
        if route == '/latest.txt':
            return self.send_file(LATEST_TXT, 'text/plain; charset=utf-8')
        if route == '/latest.jpg':
            return self.send_file(LATEST_JPG, 'image/jpeg')
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
