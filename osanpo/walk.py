#!/usr/bin/env python3
"""散歩ループ: stackchan-mcp の常駐ゲートウェイに take_photo を頼み、写真を server.py に渡す。

  python3 osanpo/walk.py            # 5分ごとに繰り返す
  python3 osanpo/walk.py --once     # 1回だけ（配線テスト）

必要なもの:
  - stackchan-mcp が常駐していること: stackchan-mcp serve --transport streamable-http
  - server.py が動いていること
  - 環境変数: OSANPO_TOKEN（server.py の合言葉）, STACKCHAN_TOKEN（ゲートウェイの合言葉、任意）
    OSANPO_MCP_URL（既定 http://127.0.0.1:8767/mcp）, OSANPO_SERVER（既定 http://127.0.0.1:5072）,
    OSANPO_INTERVAL_MIN（既定 5）
写真そのものは ~/.stackchan/captures/ にも残る（ゲートウェイの仕様）。
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_URL = os.environ.get('OSANPO_MCP_URL', 'http://127.0.0.1:8767/mcp')
MCP_TOKEN = os.environ.get('STACKCHAN_TOKEN', '')
SERVER = os.environ.get('OSANPO_SERVER', 'http://127.0.0.1:5072').rstrip('/')
TOKEN = os.environ.get('OSANPO_TOKEN', '')
INTERVAL = float(os.environ.get('OSANPO_INTERVAL_MIN', '5'))
QUESTION = os.environ.get('OSANPO_QUESTION', 'いま何が見える？')


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


class Mcp:
    """Streamable HTTP の MCP クライアント（依存パッケージなし、最小限）。"""

    def __init__(self):
        self.sid = None

    def _post(self, body):
        h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if MCP_TOKEN:
            h['Authorization'] = f'Bearer {MCP_TOKEN}'
        if self.sid:
            h['mcp-session-id'] = self.sid
        req = urllib.request.Request(MCP_URL, data=json.dumps(body).encode('utf-8'), headers=h)
        with urllib.request.urlopen(req, timeout=60) as r:
            sid = r.headers.get('mcp-session-id')
            if sid:
                self.sid = sid
            text = r.read().decode('utf-8')
        if not text.strip():
            return None
        if text.lstrip().startswith('{'):
            return json.loads(text)
        for line in text.splitlines():  # SSE
            if line.startswith('data:'):
                return json.loads(line[5:])
        return None

    def connect(self):
        self.sid = None
        self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'osanpo-walk', 'version': '0.1'}}})
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def call(self, name, args):
        j = self._post({'jsonrpc': '2.0', 'id': int(time.time() * 1000) % 1000000,
                        'method': 'tools/call', 'params': {'name': name, 'arguments': args}})
        return (j or {}).get('result') or {}


def take_photo(mcp):
    """JPEGのバイト列を返す。撮れなければ None（理由をログに出す）。"""
    res = mcp.call('take_photo', {'question': QUESTION})
    jpeg, note = None, ''
    for c in res.get('content', []):
        if c.get('type') == 'image' and c.get('data'):
            jpeg = base64.b64decode(c['data'])
        elif c.get('type') == 'text':
            note = c.get('text', '')
    if jpeg:
        return jpeg
    if not jpeg and note:
        # ゲートウェイは大きい写真だと画像ブロックを省き、パスだけ文字で返すことがある
        try:
            info = json.loads(note)
            if info.get('error'):
                log(f'撮れない: {info["error"]}')
                return None
            path = info.get('path') or info.get('file')
            if path and os.path.exists(os.path.expanduser(path)):
                with open(os.path.expanduser(path), 'rb') as f:
                    return f.read()
        except ValueError:
            pass
        log(f'take_photo の返事が想定外: {note[:200]}')
    return None


def upload(jpeg):
    req = urllib.request.Request(f'{SERVER}/upload', data=jpeg,
                                 headers={'Content-Type': 'image/jpeg', 'X-Osanpo-Token': TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def step(mcp):
    try:
        jpeg = take_photo(mcp)
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
        log(f'ゲートウェイに届かない: {e}。つなぎ直す')
        try:
            mcp.connect()
        except Exception as e2:  # noqa: BLE001
            log(f'つなぎ直しも失敗: {e2}')
        return
    if not jpeg:
        return
    try:
        upload(jpeg)
        log(f'写真 {len(jpeg)} bytes → server.py')
    except Exception as e:  # noqa: BLE001
        log(f'server.py に届かない: {e}')


def main():
    once = '--once' in sys.argv
    mcp = Mcp()
    try:
        mcp.connect()
        log(f'ゲートウェイに接続 {MCP_URL}')
    except Exception as e:  # noqa: BLE001
        log(f'ゲートウェイに接続できない: {e}')
        if once:
            return 1
    while True:
        step(mcp)
        if once:
            return 0
        time.sleep(INTERVAL * 60)


if __name__ == '__main__':
    sys.exit(main())
