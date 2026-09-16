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

## ファイル

| ファイル | 役割 | 状態 |
|---|---|---|
| `server.py` | 受信サーバ。Python標準ライブラリのみ | 動作確認済み（curlで） |
| `index.html` | ブラウザで最新の写真とコメントを見るページ（`http://PC:3940/`） | 動作確認済み |
| `look.sh` | 手動で1枚 `claude -p` に見せるテスト用 | 動作確認済み |
| `firmware/osanpo_stackchan/` | StackChan側スケッチ | **実機未検証の草案** |

## まず動かす（部品なしでできる）

```bash
python3 osanpo/server.py
# 別ターミナルで、スマホで撮った写真を投げる
curl -X POST -H 'Content-Type: image/jpeg' --data-binary @photo.jpg http://localhost:3940/upload
cat osanpo/latest.txt
```

`claude` を呼ばず配線だけ確かめたい時は `OSANPO_NO_CLAUDE=1 python3 osanpo/server.py`。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `OSANPO_PORT` | 3940 | 受信ポート（3Dオフィスの3939の隣） |
| `OSANPO_NO_CLAUDE` | 未設定 | `1` で claude を呼ばない |
| `OSANPO_PROMPT` | 「何が見えるか一文で」 | `{path}` が画像パスに置き換わる |

## 手順（時系列）

1. **フェーズ0 サーバ側（今日、部品なし）**: 上の「まず動かす」を通す。`latest.txt` に一言が入れば合格
2. **フェーズ1 開封と初期ファーム確認**: 電源を入れて初期画面を記録。M5Burnerで戻せることを確認してから書き換えに進む
3. **フェーズ1 書き込み環境**: Arduino IDEにM5Stackボード定義とM5CoreS3ライブラリを入れる。`SSID/PASS/SERVER` を書き換えて書き込む
4. **フェーズ1 室内テスト**: 家のWi-FiでPCと同じネットワークに置き、`shots/` に写真が溜まり `latest.txt` が更新されるのを確認
5. **フェーズ1 テザリングテスト**: スマホのテザリングにPCとStackChanを両方つなぎ、同じことが起きるか確認
6. **初散歩（案A: ノートPC持ち歩き）**: 顔を外向きにして固定。5分ごとに一言出れば成功
7. **フェーズ2 3Dオフィス連携**: `latest.txt` の更新を `server.js` 側に流し、散歩中キャラの吹き出しに出す
8. **フェーズ3 口**: `latest.txt` をTTSで喋らせる。AIｽﾀｯｸﾁｬﾝ2の発話部分を流用
9. **案B 自宅PC常駐**: Tailscale等で自宅PCへ届く経路を作り、ノートPCなしで散歩できるようにする
10. **電池**: 5分間隔での実測稼働時間を測り、必要ならlight sleepを入れる

## まだわかっていないこと

- 公式StackChanの出荷時ファームウェアが何か、CoreS3と書き込み手順が完全に同じか（開封後に確認）
- 700mAhで5分間隔の実稼働時間（実測待ち）
- カメラは画面と同じ面。散歩では顔を外向きに持つ必要がある
