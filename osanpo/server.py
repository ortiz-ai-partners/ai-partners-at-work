#!/usr/bin/env python3
"""お散歩Claude 受信サーバ（依存パッケージなし・Python標準ライブラリのみ）

StackChan（や、テスト用のスマホ/curl）が POST /upload でJPEGを送ってくると、
  1. osanpo/shots/YYYYmmdd-HHMMSS.jpg として保存
  2. osanpo/latest.jpg を上書き
  3. バックグラウンドで頭脳（claude -p か OpenAI API）に見せて一言を latest.txt に書く
     （personas/<名前>.md の人格で、diary.jsonl の直近の会話を踏まえて答える）
  4. diary.jsonl（機械用）と diary.log（人間用）に追記

ゆうころは POST /reply（本文=返事）で会話を返せる。index.html に入力欄がある。
StackChanは GET /latest.txt でコメントを取りに来て、喋ればいい。

人格と頭脳の切り替え:
  OSANPO_PERSONA=osanpo|vert|ortiz   （personas/ の md ファイル名。既定 osanpo = おさんぽの子）
  OSANPO_BRAIN=claude|openai  （既定 claude。openai は OPENAI_API_KEY と OSANPO_OPENAI_MODEL が必要）

diary.jsonl の1行: {"ts": "...", "role": "osanpo" | "vert" | "ortiz" | "yukoro", "text": "...", "photo": "shots/....jpg" | null}
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
import base64
import json
import os
import subprocess
import sys
import urllib.request
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'faces'))
try:
    import faces  # 家族の顔照合（ミニPC内で完結）。opencvが無ければ黙って無効
except Exception:  # noqa: BLE001
    faces = None
SHOTS = os.path.join(HERE, 'shots')
LATEST_JPG = os.path.join(HERE, 'latest.jpg')
LATEST_TXT = os.path.join(HERE, 'latest.txt')
DIARY = os.path.join(HERE, 'diary.log')
DIARY_JSONL = os.path.join(HERE, 'diary.jsonl')
MEMORY = os.path.join(HERE, 'memory.md')       # 長期記憶（reflect.py が書く）
PERSONA_NAME = os.environ.get('OSANPO_PERSONA', 'osanpo')
PERSONA = os.path.join(HERE, 'personas', PERSONA_NAME + '.md')
BRAIN = os.environ.get('OSANPO_BRAIN', 'claude')          # claude | openai
OPENAI_MODEL = os.environ.get('OSANPO_OPENAI_MODEL', 'gpt-4o-mini')  # 手元で最新の画像対応モデル名に
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')
DISPLAY = {'osanpo': 'おさんぽの子', 'vert': 'ヴェルティ', 'ortiz': 'オルティス', 'yukoro': 'ゆうころ'}  # 名前が決まったら osanpo の表示名を変える
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


def diary_append(role, text, photo=None, people=None):
    """双方の発言を時系列で残す。lock を取った上で呼ぶ。"""
    entry = {'ts': now(), 'role': role, 'text': text, 'photo': photo}
    if people:
        entry['people'] = people
    with open(DIARY_JSONL, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    name = DISPLAY.get(role, role)
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
        name = DISPLAY.get(e.get('role'), e.get('role'))
        out.append(f"{name}: {e.get('text', '')}")
    return '\n'.join(out)


def who_is_there(path):
    """ローカルの顔照合。(登録済みの名前リスト, 知らない顔の数)。無効なら ([], 0)。"""
    if faces is None:
        return [], 0
    try:
        return faces.who(path)
    except Exception as e:  # noqa: BLE001
        print(f'顔照合エラー: {e}', flush=True)
        return [], 0


def load_memory():
    try:
        with open(MEMORY, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


def build_prompt(path, people):
    prompt = PROMPT.format(path=path)
    if people:
        prompt = f'この写真に映っているのは: {", ".join(people)}（家のカメラで照合済み）\n{prompt}'
    ctx = recent_dialogue(CONTEXT_TURNS)
    if ctx:
        prompt = f'これまでの散歩の会話:\n{ctx}\n\n{prompt}'
    mem = load_memory()
    if mem:
        prompt = f'あなたが覚えていること:\n{mem}\n\n{prompt}'
    return prompt


def load_persona():
    try:
        with open(PERSONA, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def ask_claude(path, people=None):
    """claude -p に画像を見せて、人格で一言もらう。失敗しても落とさない。"""
    cmd = ['claude', '-p', build_prompt(path, people), '--allowedTools', 'Read']
    persona = load_persona()
    if persona:
        cmd += ['--append-system-prompt', persona]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return (r.stdout.strip() or r.stderr.strip() or '(無言)').replace('\n', ' ')
    except FileNotFoundError:
        return '(claude コマンドが見つからない)'
    except subprocess.TimeoutExpired:
        return '(claude タイムアウト)'


def ask_openai(path, people=None):
    """OpenAI Chat Completions に画像を base64 で渡して一言もらう。依存パッケージなし。"""
    if not OPENAI_KEY:
        return '(OPENAI_API_KEY が未設定)'
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    prompt = build_prompt('この画像', people)
    body = {
        'model': OPENAI_MODEL,
        'max_tokens': 200,
        'messages': [
            {'role': 'system', 'content': load_persona() or 'あなたは散歩の同行者。写真を見て日本語で一文だけ言う。'},
            {'role': 'user', 'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
            ]},
        ],
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            j = json.load(resp)
        return j['choices'][0]['message']['content'].strip().replace('\n', ' ')
    except Exception as e:  # noqa: BLE001
        return f'(openai 失敗: {e})'


def ask_brain(path, people=None):
    if NO_CLAUDE:
        return f'(頭脳省略: OSANPO_NO_CLAUDE=1 / persona={PERSONA_NAME})'
    return ask_openai(path, people) if BRAIN == 'openai' else ask_claude(path, people)


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
        if route == '/reflect':
            threading.Thread(target=self.reflect, daemon=True).start()
            self.send_response(202)
            self.end_headers()
            return self.wfile.write(b'reflecting\n')
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
        people, unknown = who_is_there(shot)
        if people or unknown:
            print(f'[{ts}] 映っている人: {people or "-"} / 知らない顔: {unknown}', flush=True)
        text = ask_brain(LATEST_JPG, people)
        with lock:
            with open(LATEST_TXT, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            diary_append(PERSONA_NAME, text, os.path.relpath(shot, HERE), people)
        print(f'[{ts}] {DISPLAY.get(PERSONA_NAME, PERSONA_NAME)}: {text}', flush=True)

    def reflect(self):
        """内省を別プロセスで走らせる（reflect.py）。"""
        r = subprocess.run([sys.executable, os.path.join(HERE, 'reflect.py')], capture_output=True, text=True)
        print((r.stdout or r.stderr).strip(), flush=True)

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
        if route == '/memory.md':
            return self.send_file(MEMORY, 'text/plain; charset=utf-8')
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
    face_state = 'ON' if (faces and faces.available() and os.path.exists(faces.DB)) else 'OFF'
    brain = 'OFF' if NO_CLAUDE else f'{BRAIN}' + (f':{OPENAI_MODEL}' if BRAIN == 'openai' else '')
    print(f'osanpo server on http://0.0.0.0:{PORT}  (persona: {DISPLAY.get(PERSONA_NAME, PERSONA_NAME)}, brain: {brain}, token: {"SET" if TOKEN else "NONE - 家の中限定"}, faces: {face_state})')
    if not os.path.exists(PERSONA):
        print(f'注意: 人格ファイルがない {PERSONA}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
