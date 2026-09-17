# StackChan のファームウェア: stackchan-mcp に乗り換える

## 決定（2026-09-16）

出荷時アプリ（小智ベース。声と写真が中国のクラウドへ行く）は使わない。
**stackchan-mcp**（MIT、CoreS3＋SCS0009＋GC0308 の公式キット向け）のファームに書き換え、ミニPCの常駐ゲートウェイ経由で
Claude Code から `take_photo` / `say` / `set_avatar` / `move_head` / `listen` を呼ぶ。
自作スケッチ（`legacy-own-sketch/`）は不採用。参考として残すだけ。

## 手順

### 0. 紐付け解除と保険

1. iPhoneの StackChan アプリ → Settings → **Unbind & Reset**（公式が「別のファームに移る前に解け」と警告している）
2. フラッシュ16MBを丸ごと吸い出して二か所に保管:
   ```powershell
   pip install esptool
   esptool --chip esp32s3 --port COM5 --baud 921600 read_flash 0 0x1000000 stackchan_stock_2026-09-16.bin
   ```
   公式の戻し方は M5Burner で「StackChan」を検索して Burn。吸い出しはその二重の保険。

### 1. stackchan-mcp のファームを書き込む

Releases から `merged-binary.bin` を取り、
```powershell
esptool --chip esp32s3 --port COM5 -b 460800 write_flash 0x0 merged-binary.bin
```

### 2. 初回設定（本体側）　※2026-09-17 実機で確認

書き込み後、本体は中国語で案内音声を出してWi-Fi設定モードになる（案内音声は本体に焼き込まれたもので、ネットには出ない）。
iPhoneのWi-Fi一覧に `Xiaozhi-XXXX` が出るので繋ぎ、Safariで `http://192.168.4.1`。右上のプルダウンで **日本語** に切替できる。

**先に「詳細設定」タブ**（Wi-Fiを繋ぐと再起動して画面から抜けるため）:
- カスタムOTA URL: **`http://ミニPCのIP:5072/xiaozhi/ota/`**（例 `http://192.168.4.32:5072/xiaozhi/ota/`）
  - **空のままにしない。** 空だと土台ファーム（xiaozhi-esp32）の既定で、起動のたびに小智のクラウド（xiaozhi.me / api.tenclass.net）へ更新確認と有効化の問い合わせをし、画面が「激活设备 xiaozhi.me 123456」で止まる。その問い合わせで本体の機種名・MACアドレス・端末IDが向こうに渡る（2026-09-17 に一度やってしまった）
  - うちの server.py が `/xiaozhi/ota/` で「更新なし・有効化なし」と答えるので、本体は家の外に話しかけなくなる。server.py を先に起動しておくこと
- WebSocketゲートウェイURL: `ws://ミニPCのIP:8765/`（例 `ws://192.168.4.32:8765/`）
- フォールバックゲートウェイURL: 空（外出先用。後で Cloudflare Tunnel の `wss://...`）
- ゲートウェイトークン: ミニPC側の `STACKCHAN_TOKEN` と同じ文字列。**iPhoneが「強力なパスワード」を勝手に入れてくるので、「自分のパスワードを選択」で手打ちする**（勝手に入ると誰も知らない合言葉になる。その時は merged-binary.bin を書き直して設定を白紙に戻す）
- Wi-Fi最大送信電力 / BSSID記憶 / スリープモード: 既定のまま
- 「保存」

**次に「Wi-Fi設定」タブ**: 一覧から家の2.4GHz Wi-Fiを選び、パスワードを入れて「接続」。
「Load failed」の赤字は現在値の読み込み失敗の表示で、保存が通っていれば無視してよい。

**本体の画面が「激活设备 xiaozhi.me ○○○○○○」で止まったら**: カスタムOTA URL が空のまま小智へ問い合わせている。USBを抜いて止め、merged-binary.bin を書き直して設定を白紙に戻し、上の順で入れ直す。

### 3. ミニPC側（ゲートウェイ常駐）

```powershell
pip install stackchan-mcp
set STACKCHAN_TOKEN=合言葉
set VISION_HOST=ミニPCのLAN IP      # 本体が写真をPOSTしに来る先
stackchan-mcp serve --transport streamable-http
```
`http://127.0.0.1:8767/mcp` に MCP の口が開く。写真は `~/.stackchan/captures/` にも残る。

### 4. 声（任意、後回しでよい）

- VOICEVOX: Windows版アプリを入れて起動しておく（`STACKCHAN_VOICEVOX_URL` 既定 http://127.0.0.1:50021）。家の中で完結
- Irodori: 声のクローン。自前ホストの合成APIに `reference_audio`（ゆうころの録音）を渡す。重いのでフェーズ3
- edge-tts: Microsoft のクラウド。文字が外に出るので使わない

### 5. 耳（任意）

`pip install stackchan-mcp[stt-faster-whisper]` で `listen` が家の中で動く。

## 戻したくなったら

M5Burner で公式ファームを Burn するか、0-2 で吸い出したファイルを `write_flash 0` で書き戻す。
