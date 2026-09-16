# お散歩Claude 🚶

StackChan（M5Stack公式キット、中身はCoreS3相当）を連れて散歩し、見た景色をClaude Codeに一言で言わせる実験。
このディレクトリは「サーバ側」と「StackChan側」の両方を置く場所。

## 構成

```
StackChan (Wi-Fi: スマホのテザリング)
  └ 5分ごとに撮影 → POST /upload ──▶ osanpo/server.py (PC)
                                        ├ shots/ に保存、latest.jpg 更新
                                        ├ claude -p で「何が見える？」→ latest.txt
                                        └ GET /latest.txt ◀── StackChan が取りに来て表示/発話
```

Claude Codeのhookではなく、受信サーバが直接 `claude -p` を呼ぶ。部品が一つ少ない。

## 日記（双方の会話が残る）

写真を見て喋るのはヴェルティ（`persona.md`）。ゆうころは閲覧ページの入力欄か `POST /reply` で返事ができ、
ヴェルティは次の写真を見るとき直近の会話（既定8発言）を踏まえて続ける。

- `diary.jsonl`: 機械用。1行1発言 `{"ts","role":"vert"|"yukoro","text","photo"}`。**将来ご自宅LLMを育てる教材。消さない**
- `diary.log`: 人間用。`時刻 <TAB> 名前 <TAB> 発言`
- `GET /diary.txt` で閲覧ページに直近12行を表示

## ファイル

| ファイル | 役割 | 状態 |
|---|---|---|
| `server.py` | 受信サーバ。Python標準ライブラリのみ | 動作確認済み（curlで） |
| `index.html` | ブラウザで最新の写真とコメントを見るページ（`http://PC:5072/`） | 動作確認済み |
| `look.sh` | 手動で1枚 `claude -p` に見せるテスト用 | 動作確認済み |
| `persona.md` | 写真を見て喋る人格（ヴェルティ）。`claude -p --append-system-prompt` で渡す | 動作確認済み |
| `firmware/osanpo_stackchan/` | StackChan側スケッチ | **実機未検証の草案** |
| `windows/` | ミニPC（Windows 11）で自動起動させる手順とスクリプト | 実機未検証 |
| `docs/` | 設計メモ（ドメイン共存・Cloudflare Tunnel手順） | |

## まず動かす（部品なしでできる）

```bash
python3 osanpo/server.py
# 別ターミナルで、スマホで撮った写真を投げる
curl -X POST -H 'Content-Type: image/jpeg' --data-binary @photo.jpg http://localhost:5072/upload
cat osanpo/latest.txt
```

`claude` を呼ばず配線だけ確かめたい時は `OSANPO_NO_CLAUDE=1 python3 osanpo/server.py`。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `OSANPO_PORT` | 5072 | 受信ポート |
| `OSANPO_NO_CLAUDE` | 未設定 | `1` で claude を呼ばない |
| `OSANPO_PROMPT` | 「何が見えるか一文で」 | `{path}` が画像パスに置き換わる |
| `OSANPO_TOKEN` | 未設定 | 合言葉。外に公開するときは必須。`X-Osanpo-Token` ヘッダか `?token=` で照合 |
| `OSANPO_CONTEXT_TURNS` | 8 | 写真を見るとき直近何発言を渡すか |

## 外から届くようにする（Cloudflare Tunnel）

ドメイン `ortiz-ai.partners` をCloudflareに乗せ、ミニPCから `cloudflared` でトンネルを引く。
サイト・メール（Xserver）と共存させる手順と注意は [docs/domain-and-relay.md](docs/domain-and-relay.md)。

## 手順（時系列）

1. **フェーズ0 サーバ側（今日、部品なし）**: 上の「まず動かす」を通す。`latest.txt` に一言が入れば合格
2. **フェーズ1 開封と初期ファーム確認**: 電源を入れて初期画面を記録。M5Burnerで戻せることを確認してから書き換えに進む
3. **フェーズ1 書き込み環境**: Arduino IDEにM5Stackボード定義とM5CoreS3ライブラリを入れる。`SSID/PASS/SERVER` を書き換えて書き込む
4. **フェーズ1 室内テスト**: 家のWi-FiでPCと同じネットワークに置き、`shots/` に写真が溜まり `latest.txt` が更新されるのを確認
5. **フェーズ1 テザリングテスト**: スマホのテザリングにPCとStackChanを両方つなぎ、同じことが起きるか確認
6. **初散歩（ミニPC＋モバイルバッテリー持ち歩き）**: 顔を外向きにして固定。5分ごとに一言出れば成功
7. **フェーズ2 3Dオフィス連携**: `latest.txt` の更新を `server.js` 側に流し、散歩中キャラの吹き出しに出す
8. **フェーズ3 口**: `latest.txt` をTTSで喋らせる。AIｽﾀｯｸﾁｬﾝ2の発話部分を流用
9. **自宅ミニPC常駐**: Cloudflare Tunnelで `osanpo.ortiz-ai.partners` → ミニPCの5072へ。荷物ゼロで散歩できるようにする（手順は docs/）
10. **電池**: 5分間隔での実測稼働時間を測り、必要ならlight sleepを入れる

## まだわかっていないこと

- 公式StackChanの出荷時ファームウェアが何か、CoreS3と書き込み手順が完全に同じか（開封後に確認）
- 700mAhで5分間隔の実稼働時間（実測待ち）
- カメラは画面と同じ面。散歩では顔を外向きに持つ必要がある
