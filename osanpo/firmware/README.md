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

### 2. 初回設定（本体側）

起動するとWi-Fi設定モードになる。スマホで本体のアクセスポイントに繋ぎ `http://192.168.4.1` → **Advanced** タブ:
- WebSocket Gateway URL: `ws://ミニPCのIP:8765/`
- Gateway Token: ミニPC側の `STACKCHAN_TOKEN` と同じ
- Fallback Gateway URL: 外出先用（後で。Cloudflare Tunnel 経由の `wss://...`）

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
