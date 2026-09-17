#!/usr/bin/env python3
"""お散歩Claude 受信サーバ（依存パッケージなし・Python標準ライブラリのみ）

写真の入り口は2つ:
  - walk.py が stackchan-mcp 常駐ゲートウェイから take_photo で取って POST /upload（本命）
  - 何かが直接 POST /upload（テスト用のスマホ/curl、または自作スケッチ）
osanpo/mcp.json があれば StackChan モードになり、その子は一言を mcp__stackchan__say で喋る。

POST /upload でJPEGが届くと、
  1. osanpo/shots/YYYYmmdd-HHMMSS.jpg として保存
  2. osanpo/latest.jpg を上書き
  3. バックグラウンドで頭脳（claude -p か OpenAI API）に見せて一言を latest.txt に書く
     （personas/<名前>.md の人格で、diary.jsonl の直近の会話を踏まえて答える）
  4. diary.jsonl（機械用）と diary.log（人間用）に追記

散歩1回＝1つのClaude会話。写真ごとに --resume で同じ会話を続けるので、その散歩で見た写真と会話を全部覚えている。
90分（OSANPO_WALK_GAP_MIN）空くか POST /newwalk で散歩が終わり、自動で内省（reflect.py）が走る。

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
import re
import os
import subprocess
import sys
import urllib.request
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'faces'))
from claude_cli import claude_command  # noqa: E402
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
WALK = os.path.join(HERE, '.walk.json')        # いまの散歩の会話ID {"session_id", "last_ts"}
MCP_JSON = os.path.join(HERE, 'mcp.json')       # あれば StackChan モード: say で喋り、表情を切り替える
STACKCHAN_TOOLS = ['mcp__stackchan__say', 'mcp__stackchan__set_avatar', 'mcp__stackchan__move_head']
WALK_GAP_MIN = int(os.environ.get('OSANPO_WALK_GAP_MIN', '90'))  # これ以上空いたら新しい散歩
PERSONA_NAME = os.environ.get('OSANPO_PERSONA', 'osanpo')
PERSONA = os.path.join(HERE, 'personas', PERSONA_NAME + '.md')
BRAIN = os.environ.get('OSANPO_BRAIN', 'claude')          # claude | openai
OPENAI_MODEL = os.environ.get('OSANPO_OPENAI_MODEL', 'gpt-4o-mini')  # 手元で最新の画像対応モデル名に
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')
DISPLAY = {'osanpo': 'おさんぽの子', 'vert': 'ヴェルティ', 'ortiz': 'オルティス', 'yukoro': 'ゆうころ', 'system': '（記録）'}  # 名前が決まったら osanpo の表示名を変える
PORT = int(os.environ.get('OSANPO_PORT', '5072'))
NO_CLAUDE = os.environ.get('OSANPO_NO_CLAUDE') == '1'
TOKEN = os.environ.get('OSANPO_TOKEN', '')   # 空なら家の中限定の無防備モード
PROMPT = os.environ.get(
    'OSANPO_PROMPT',
    '{path} を見て、いま何が見えるかを言って。',
)
CONTEXT_TURNS = int(os.environ.get('OSANPO_CONTEXT_TURNS', '8'))  # 新しい散歩の最初に、前回までの直近何発言を渡すか
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
    """ローカルの顔照合。(登録済みの名前, 知らない顔の数, 聞くべき候補ID)。無効なら ([], 0, [])。"""
    if faces is None:
        return [], 0, []
    try:
        return faces.observe(path)
    except Exception as e:  # noqa: BLE001
        print(f'顔照合エラー: {e}', flush=True)
        return [], 0, []


ASK_RE = re.compile(r'^\s*#(\d+)\s*[=:：は]?\s*(.+?)\s*$')
DISMISS_WORDS = {'だめ', 'ダメ', '覚えないで', 'おぼえないで', 'いや', 'no', 'x', '×', '消して'}


def handle_face_answer(text):
    """「#3 はけんちゃんだよ」→ 登録、「#3 だめ」→ 消す。該当しなければ None。"""
    if faces is None:
        return None
    m = ASK_RE.match(text)
    if not m:
        return None
    cid, name = m.group(1), m.group(2)
    name = re.sub(r'(だよ|です|だね|だ|ね|よ|。|！|!)+$', '', name).strip()
    if name in DISMISS_WORDS or not name:
        return f'#{cid} は覚えないことにした' if faces.dismiss_candidate(cid) else f'#{cid} は候補にない'
    return f'#{cid} を「{name}」として覚えた' if faces.enroll_candidate(cid, name) else f'#{cid} は候補にない'


def load_walk():
    try:
        with open(WALK, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_walk(session_id):
    with open(WALK, 'w', encoding='utf-8') as f:
        json.dump({'session_id': session_id, 'last_ts': time.time()}, f)


def current_walk_session():
    """続きの散歩なら会話IDを返す。空白が長ければ None（新しい散歩）。"""
    w = load_walk()
    if not w.get('session_id'):
        return None
    if time.time() - w.get('last_ts', 0) > WALK_GAP_MIN * 60:
        return None
    return w['session_id']


def end_walk():
    """散歩を終える。会話IDを捨て、日記があれば内省を走らせる。"""
    had = bool(load_walk().get('session_id'))
    try:
        os.remove(WALK)
    except FileNotFoundError:
        pass
    if had:
        threading.Thread(target=run_reflect, daemon=True).start()


def run_reflect():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'reflect.py')], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip(), flush=True)


def unseen_replies():
    """前回その子が喋ってから後の、ゆうころの返事だけ。"""
    try:
        with open(DIARY_JSONL, encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    out = []
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('role') == 'yukoro':
            out.append(e.get('text', ''))
        else:
            break
    return list(reversed(out))


def load_persona():
    try:
        with open(PERSONA, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def load_memory():
    try:
        with open(MEMORY, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


def stackchan_mode():
    return os.path.exists(MCP_JSON)


def build_prompt(path, people, resumed, asks=None):
    prompt = PROMPT.format(path=path)
    if stackchan_mode():
        prompt += ('\n一言が決まったら mcp__stackchan__say でその一言を喋る（text にそのまま渡す。'
                   '気分に合う絵文字を1つ文頭に入れると表情も変わる: 😊 🤔 😲 😢 😳）。'
                   '喋ったあと、返答の本文にはその一言だけを書く。')
    if people:
        prompt = f'この写真に映っているのは: {", ".join(people)}（家のカメラで照合済み）\n{prompt}'
    if asks:
        tags = ' '.join(f'#{a}' for a in asks)
        prompt += f'\n（知らない人が何度も映っている。文の最後に、こっそり「（この人だれ？覚えてもいい？ {tags}）」と付けて）'
    if resumed:
        rep = unseen_replies()
        if rep:
            prompt = 'ゆうころ: ' + '\nゆうころ: '.join(rep) + '\n\n' + prompt
    else:
        ctx = recent_dialogue(CONTEXT_TURNS)
        if ctx:
            prompt = f'新しい散歩が始まった。前回までの会話の終わり:\n{ctx}\n\n{prompt}'
    return prompt


def system_prompt():
    """人格＋長期記憶。会話の中ではなく毎回「性格」として渡す（会話が太らない）。"""
    parts = [load_persona()]
    mem = load_memory()
    if mem:
        parts.append('あなたが覚えていること:\n' + mem)
    return '\n\n'.join(p for p in parts if p)


SYSPROMPT_FILE = os.path.join(HERE, '.system_prompt.txt')


def _run_claude(prompt, session_id):
    base = claude_command()
    if not base:
        raise FileNotFoundError('claude')
    with open(SYSPROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(system_prompt())
    tools = ['Read'] + (STACKCHAN_TOOLS if stackchan_mode() else [])
    cmd = base + ['-p', prompt, '--allowedTools', *tools, '--output-format', 'json',
                  '--append-system-prompt-file', SYSPROMPT_FILE]
    if session_id:
        cmd += ['--resume', session_id]
    if stackchan_mode():
        cmd += ['--mcp-config', MCP_JSON, '--strict-mcp-config']
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=180)
    if not r.stdout.strip():
        raise RuntimeError((r.stderr or 'claude が何も返さない').strip()[:300])
    j = json.loads(r.stdout)
    if j.get('is_error'):
        raise RuntimeError(j.get('result') or 'claude error')
    denied = j.get('permission_denials') or []
    if denied:
        print(f'claude が使えなかった道具: {[d.get("tool_name") for d in denied]}', flush=True)
    print(f'claude: {j.get("num_turns")} turns', flush=True)
    return (j.get('result') or '(無言)').strip().replace('\n', ' '), j.get('session_id')


def ask_claude(path, people=None, asks=None):
    """散歩1回＝1つの会話。続きなら --resume、途切れていれば新しく始める。"""
    sid = current_walk_session()
    try:
        try:
            text, new_sid = _run_claude(build_prompt(path, people, resumed=bool(sid), asks=asks), sid)
        except (RuntimeError, ValueError):
            if not sid:
                raise
            print('会話の再開に失敗。新しい散歩として始める', flush=True)
            text, new_sid = _run_claude(build_prompt(path, people, resumed=False, asks=asks), None)
        if new_sid:
            save_walk(new_sid)
        return text
    except FileNotFoundError:
        return '(claude コマンドが見つからない)'
    except subprocess.TimeoutExpired:
        return '(claude タイムアウト)'
    except Exception as e:  # noqa: BLE001
        return f'(claude 失敗: {e})'


def ask_openai(path, people=None):
    """OpenAI Chat Completions に画像を base64 で渡して一言もらう。依存パッケージなし。"""
    if not OPENAI_KEY:
        return '(OPENAI_API_KEY が未設定)'
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    prompt = build_prompt('この画像', people, resumed=False)
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


def ask_brain(path, people=None, asks=None):
    if NO_CLAUDE:
        return f'(頭脳省略: OSANPO_NO_CLAUDE=1 / persona={PERSONA_NAME})'
    return ask_openai(path, people) if BRAIN == 'openai' else ask_claude(path, people, asks)


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
            threading.Thread(target=run_reflect, daemon=True).start()
            self.send_response(202)
            self.end_headers()
            return self.wfile.write(b'reflecting\n')
        if route == '/newwalk':
            end_walk()
            self.send_response(200)
            self.end_headers()
            print(f'[{now()}] 散歩を締めた（次の写真から新しい散歩）', flush=True)
            return self.wfile.write(b'new walk\n')
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
        people, unknown, asks = who_is_there(shot)
        if people or unknown:
            print(f'[{ts}] 映っている人: {people or "-"} / 知らない顔: {unknown}' + (f' / 聞く: {asks}' if asks else ''), flush=True)
        if current_walk_session() is None and load_walk().get('session_id'):
            end_walk()  # 間が空いた → 前の散歩を締めて内省
        text = ask_brain(shot, people, asks)
        for a in asks:  # 子が付け忘れても、必ず括弧書きで聞く
            if f'#{a}' not in text:
                text += f'（この人だれ？覚えてもいい？ #{a}）'
                break
        with lock:
            with open(LATEST_TXT, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            diary_append(PERSONA_NAME, text, os.path.relpath(shot, HERE), people)
        print(f'[{ts}] {DISPLAY.get(PERSONA_NAME, PERSONA_NAME)}: {text}', flush=True)

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
        print(f'[{now()}] ゆうころ: {text}', flush=True)
        note = handle_face_answer(text)
        if note:
            with lock:
                diary_append('system', note)
            print(f'[{now()}] {note}', flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok\n')

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
        if route == '/asks.json':
            data = json.dumps(faces.pending() if faces else []).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        m = re.match(r'^/candidates/(\d+)\.jpg$', route)
        if m and faces:
            return self.send_file(os.path.join(faces.CAND_DIR, m.group(1) + '.jpg'), 'image/jpeg')
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


class _Tee:
    """画面とログファイルの両方に書く（Windowsで外部のパイプを挟むと日本語が化けるため、自前で）。"""

    def __init__(self, path):
        self.console = sys.stdout
        self.f = open(path, 'a', encoding='utf-8')

    def write(self, data):
        self.console.write(data)
        self.f.write(data)

    def flush(self):
        self.console.flush()
        self.f.flush()


if __name__ == '__main__':
    if os.environ.get('OSANPO_LOG'):
        sys.stdout = sys.stderr = _Tee(os.environ['OSANPO_LOG'])
    face_state = 'ON' if (faces and faces.available() and os.path.exists(faces.DB)) else 'OFF'
    brain = 'OFF' if NO_CLAUDE else f'{BRAIN}' + (f':{OPENAI_MODEL}' if BRAIN == 'openai' else '')
    print(f'osanpo server on http://0.0.0.0:{PORT}  (persona: {DISPLAY.get(PERSONA_NAME, PERSONA_NAME)}, brain: {brain}, token: {"SET" if TOKEN else "NONE - 家の中限定"}, faces: {face_state}, stackchan: {"ON (say で喋る)" if stackchan_mode() else "OFF"})', flush=True)
    if not os.path.exists(PERSONA):
        print(f'注意: 人格ファイルがない {PERSONA}', flush=True)
    print(f'ブラウザで http://localhost:{PORT}/?token=合言葉 を開くと閲覧ページ。Ctrl+C で停止', flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
