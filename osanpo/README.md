# お散歩Claude 🚶

StackChan（M5Stack公式キット、中身はCoreS3相当）を連れて散歩し、見た景色をClaude Codeに一言で言わせる実験。
このディレクトリは「サーバ側」と「StackChan側」の両方を置く場所。

## 構成（2026-09-16 改訂: stackchan-mcp 採用）

```
StackChan（stackchan-mcp ファーム）⇄ ws 8765 / http 8766 ⇄ stackchan-mcp 常駐ゲートウェイ（ミニPC）
                                                                    ⇅ http://127.0.0.1:8767/mcp
   walk.py: 5分ごとに take_photo ──▶ server.py /upload ──▶ 顔照合 → 人格＋記憶 → claude -p（散歩1回=1会話）
                                                                                  └ mcp__stackchan__say で喋る・表情
```

- 写真・声・顔・日記・記憶はミニPCの中。外に出るのは「写真とその子の言葉」を Claude に見せる分だけ
- 出荷時アプリ（小智）は使わない。理由と手順は `firmware/README.md`
- Claude Codeのhookではなく、受信サーバが直接 `claude -p` を呼ぶ。部品が一つ少ない

## 日記（双方の会話が残る）

写真を見て喋るのは `OSANPO_PERSONA` で選んだ人格（`personas/`）。ゆうころは閲覧ページの入力欄か `POST /reply` で返事ができ、
次の写真を見るとき直近の会話（既定8発言）を踏まえて続ける。

## 記憶（育つ仕組み）

```
diary.jsonl（生ログ、全部）──内省(reflect.py)──▶ memory.md（覚えたこと）──毎回prompt──▶ その子
```

- **散歩の中**: 散歩1回＝1つのClaude会話。写真ごとに `--resume` で同じ会話を続けるので、その散歩で見た**写真と会話の全部**を持ったまま歩く。90分（`OSANPO_WALK_GAP_MIN`）空くか「散歩おわり」ボタン（`POST /newwalk`）で散歩が終わり、自動で内省が走る
- **散歩をまたぐ**: 新しい散歩の最初に、前回までの直近8発言（`OSANPO_CONTEXT_TURNS`）を渡す
- **長期**: `memory.md`。見出しは「自分について / よく見るもの・場所 / ゆうころ・はるくんについて / 覚えたこと / 気になっていること」
- **内省**: 散歩が終わると自動。手動なら `python3 osanpo/reflect.py` か `POST /reflect`。上限 `OSANPO_MEMORY_MAX`（既定3000文字）
- memory.md は手で直してよい。「これは違うよ」と書き換えるのも育て方のひとつ
- 思考ジャンプ: 人格文で「いま見たものから覚えていることへ飛んでよい（そういえば〜）」と許可している。毎回飛ぶわけではない

## 人格と頭脳の切り替え

| 変数 | 値 | 意味 |
|---|---|---|
| `OSANPO_PERSONA` | `osanpo`（既定） / `vert` / `ortiz` | `personas/<値>.md` を人格として使う。日記の `role` にもこの値が入る |
| `OSANPO_BRAIN` | `claude`（既定） / `openai` | 写真を見る頭脳。`claude` はClaude Code経由で従量課金なし。`openai` は `OPENAI_API_KEY` が必要で写真1枚ごとに課金 |
| `OSANPO_OPENAI_MODEL` | `gpt-4o-mini` | `openai` のとき使うモデル。手元で最新の画像対応モデル名に変える |

既定のまま起動すれば「おさんぽの子」がClaudeで喋る。

- `diary.jsonl`: 機械用。1行1発言 `{"ts","role":"vert"|"ortiz"|"yukoro","text","photo","people"}`。**将来ご自宅LLMを育てる教材。消さない**
- `diary.log`: 人間用。`時刻 <TAB> 名前 <TAB> 発言`
- `GET /diary.txt` で閲覧ページに直近12行を表示

## ファイル

| ファイル | 役割 | 状態 |
|---|---|---|
| `server.py` | 受信サーバ。Python標準ライブラリのみ。`mcp.json` があれば `say` で喋る | 動作確認済み（curl / 常駐ゲートウェイ相手に） |
| `walk.py` | 散歩ループ。常駐ゲートウェイに `take_photo` を頼み server.py へ渡す | 本体未接続の経路まで確認済み |
| `mcp.json.example` | Claude Code に常駐ゲートウェイを教える設定。`mcp.json` にコピーして合言葉を入れる | |
| `index.html` | ブラウザで最新の写真とコメントを見るページ（`http://PC:5072/`） | 動作確認済み |
| `look.sh` | 手動で1枚 `claude -p` に見せるテスト用 | 動作確認済み |
| `reflect.py` | 内省。日記を読み返して `memory.md`（長期記憶）を書き直す。`POST /reflect` でも起動 | 動作確認済み |
| `personas/osanpo.md` | 写真を見て喋る人格: **おさんぽの子**（既定。名前は本人が後で決める） | 動作確認済み |
| `personas/vert.md` | 同: ヴェルティ（参謀。散歩には出ない） | 動作確認済み |
| `personas/ortiz.md` | 同: オルティス。**中身はゆうころが書く**（雛形のみ） | 未記入 |
| `firmware/README.md` | stackchan-mcp への書き換え手順、出荷時アプリの吸い出し・書き戻し | |
| `firmware/legacy-own-sketch/` | 自作スケッチ。**不採用**（参考のみ） | |
| `faces/` | 家族の顔照合（ミニPC内で完結、OpenCV）。名前だけをClaudeに渡す | 顔なし画像で0件まで確認。登録後の精度は実機で |
| `windows/` | ミニPC（Windows 11）で自動起動させる手順とスクリプト | 実機未検証 |
| `docs/decisions.md` | **決めたこと一覧。忘れたらまずここ** | |
| `docs/domain-and-relay.md` | ドメイン共存・Cloudflare Tunnelの手順 | |

## まず動かす（部品なしでできる）

```bash
python3 osanpo/server.py
# 別ターミナルで、スマホで撮った写真を投げる
curl -X POST -H 'Content-Type: image/jpeg' --data-binary @photo.jpg http://localhost:5072/upload
cat osanpo/latest.txt
```

`claude` を呼ばず配線だけ確かめたい時は `OSANPO_NO_CLAUDE=1 python3 osanpo/server.py`。

## 家族の顔を認識する（任意）

Claude 自身は顔から人物を特定しない。代わりに **ミニPCの中で** OpenCV（YuNet + SFace）で照合し、
「映っているのは: ゆうころ, はるくん」という文字だけを `claude -p` に渡す。写真・顔データは外に出ない。

```bash
pip install opencv-python-headless numpy
sh osanpo/faces/download_models.sh
# osanpo/faces/people/<名前>/ に正面写真を3〜5枚ずつ（登録する人の了解を先に）
python3 osanpo/faces/faces.py enroll
python3 osanpo/faces/faces.py who photo.jpg   # 確認
```

`db.npz` があれば server.py が自動で使う。

### 知らない顔を「聞いて覚える」（ゆうころの設計）

近くで正面で大きく映った知らない顔だけ、特徴ベクトルと小さな切り抜きを候補帳（`faces/candidates.json`, `faces/candidates/`）に一時保管して数える。

- **5回以上・2日以上**にまたがって見たら、その子が文の最後にこっそり「（この人だれ？覚えてもいい？ #3）」と聞く（1日1回まで）
- ゆうころが返事欄に `#3 はけんちゃんだよ` と書けば登録。`#3 だめ` なら消す。閲覧ページには切り抜きと「覚える／覚えない」ボタンが出る
- 30日見なければ自動で消える。候補は最大50人。遠い顔（`OSANPO_FACE_MIN_PX` 未満）は数えない
- **子どもを登録する時は、その子の親の了解を先に**（ゆうころの約束）

| 変数 | 既定 | 意味 |
|---|---|---|
| `OSANPO_FACE_ASK_AFTER` | 5 | この回数見たら聞く |
| `OSANPO_FACE_ASK_DAYS` | 2 | かつ、この日数以上にまたがって |
| `OSANPO_FACE_EXPIRE_DAYS` | 30 | 見なくなってから消えるまで |
| `OSANPO_FACE_MIN_PX` | 60 | これより小さい顔は数えない |

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `OSANPO_PORT` | 5072 | 受信ポート |
| `OSANPO_NO_CLAUDE` | 未設定 | `1` で claude を呼ばない |
| `OSANPO_PROMPT` | 「何が見えるか一文で」 | `{path}` が画像パスに置き換わる |
| `OSANPO_TOKEN` | 未設定 | 合言葉。外に公開するときは必須。`X-Osanpo-Token` ヘッダか `?token=` で照合 |
| `OSANPO_WALK_GAP_MIN` | 90 | 写真がこれ以上（分）空いたら次は新しい散歩 |
| `OSANPO_CONTEXT_TURNS` | 8 | 新しい散歩の最初に、前回までの直近何発言を渡すか |
| `OSANPO_MEMORY_MAX` | 3000 | memory.md の文字数上限 |
| `OSANPO_FACE_THRESHOLD` | 0.363 | 顔照合の一致しきい値（SFace公式のcosine値）。誤認が多ければ上げる |

## 外から届くようにする（Cloudflare Tunnel）

ドメイン `ortiz-ai.partners` をCloudflareに乗せ、ミニPCから `cloudflared` でトンネルを引く。
サイト・メール（Xserver）と共存させる手順と注意は [docs/domain-and-relay.md](docs/domain-and-relay.md)。

## 手順（時系列）

1. **サーバ側（部品なしでできる）**: 上の「まず動かす」を通す。`latest.txt` に一言が入れば合格
2. **StackChan の紐付け解除と保険**: アプリで Unbind & Reset → esptool で16MB吸い出し（`firmware/README.md`）
3. **stackchan-mcp のファーム書き込み**: `merged-binary.bin` を `write_flash 0x0`。初回起動でWi-FiとゲートウェイURLを設定
4. **ミニPCでゲートウェイ常駐**: `stackchan-mcp serve --transport streamable-http`。`mcp.json` を作る
5. **室内テスト**: `python3 osanpo/walk.py --once` で写真が届き、その子が `say` で喋れば合格。次に5分ループ
6. **口の声**: VOICEVOX（家の中）で仮の声。ゆうころの声（Irodori）はフェーズ3
7. **テザリングテスト**: iPhoneのテザリングにミニPCとStackChanを両方つなぐ
8. **初散歩（ミニPC＋モバイルバッテリー持ち歩き）**: 顔を外向きに固定。5分ごとに一言出れば成功
9. **耳**: `listen`（faster-whisper）でゆうころの声の返事を日記へ
10. **3Dオフィス連携**: 日記の更新を `server.js` に流し、散歩中キャラの吹き出しに出す
11. **自宅ミニPC常駐**: Cloudflare Tunnel で ws 8765 / http 8766 を外に出し、本体の Fallback Gateway URL に入れる。荷物ゼロ化
12. **電池**: 実測

## まだわかっていないこと

- stackchan-mcp のファームが手元の個体で一発で動くか（実機未検証）
- 700mAhで5分間隔の実稼働時間（実測待ち）
- Claude 側で写真が学習に使われるかの設定（契約と設定に従う。未確認）
- カメラは画面と同じ面。散歩では顔を外向きに持つ必要がある
