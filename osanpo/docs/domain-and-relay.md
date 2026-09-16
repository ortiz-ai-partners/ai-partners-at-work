# ortiz-ai.partners をお散歩Claudeに使う（サイト・メールと共存させる）

前提: ドメインはお名前.com、サイトとメールはXserverで稼働中。

## 決定（2026-09-16）

**Cloudflare Tunnel で行く。** 理由: 確実で、将来の拡張（3Dオフィスの遠隔観察など）に同じ土台がそのまま使えるから。
Xserverを預かり所にする案（DNSに触らない代替案）は末尾に残すが、採用しない。

## 全体像

```
StackChan（テザリング）──HTTPS──▶ osanpo.ortiz-ai.partners（Cloudflare）
                                        │ トンネル（ミニPCが家の中から外向きに張る）
                                        ▼
                                 ミニPC localhost:5072 = osanpo/server.py（合言葉つき）
```

ルーターの設定は触らない。外に見えるのは受信窓口ひとつだけ。合言葉（`OSANPO_TOKEN`）が無い荷物は403で拒否する。

## 手順

### 1. 準備（DNSを切り替える前に。ここが一番大事）

1. Xserverサーバーパネル →「DNSレコード設定」→ `ortiz-ai.partners` の全レコードを控える（スクショ＋テキスト）
   - A（`@`, `www`, その他サブドメイン）: サイトのIP
   - MX: メールサーバー
   - TXT: SPF / DKIM / DMARC（落とすと送信メールが迷惑メール扱いになる）
   - CNAME など
2. お名前.comにログインできること、ネームサーバー変更画面が開けることを確認

### 2. Cloudflareにドメインを追加

1. Cloudflare無料アカウント作成 →「サイトを追加」→ `ortiz-ai.partners`（Freeプラン）
2. Cloudflareが既存レコードを自動読み取りするが、**1で控えた一覧と目視で突き合わせて不足を追加**
3. すべてのレコードのプロキシ（橙の雲）を **オフ（灰色・DNS only）** にする。サイトの前にCloudflareを立たせない
4. Cloudflareが指定する2つのネームサーバーを控える

### 3. ネームサーバー切り替え

1. お名前.com →「ネームサーバーの設定」→ Cloudflareの2つに変更
2. 反映まで数分〜数時間。Cloudflare側が「アクティブ」になるのを待つ
3. **確認**: サイト表示、メール送信、メール受信の3つ。全部通るまで次に進まない

### 4. ミニPCにトンネルを張る

1. Cloudflareダッシュボード → Zero Trust → Networks → Tunnels →「トンネルを作成」（名前: `osanpo-minipc` など）
2. 表示されるコマンドで `cloudflared` をミニPCにインストール＆サービス登録（起動時に自動で張る）
3. Public Hostname を追加: `osanpo.ortiz-ai.partners` → `http://localhost:5072`
4. ミニPCで `OSANPO_TOKEN=合言葉 python3 osanpo/server.py`（こちらも自動起動にする）
5. 外（スマホの4G）から `https://osanpo.ortiz-ai.partners/?token=合言葉` を開いて表示されれば完成

### 5. StackChan側

- スケッチの `SERVER` を `https://osanpo.ortiz-ai.partners`、`TOKEN` を合言葉にして書き込む
- 実験中は証明書検証なし（`setInsecure`）。動いたらCloudflareのルート証明書を `setCACert` で入れる

### 6. 将来の拡張（同じトンネルに1行足すだけ）

- `office.ortiz-ai.partners` → `http://localhost:3939` で3Dオフィスを外から見る（Cloudflare Accessで鍵をかける）

## まだ確認していないこと

- Xserverの現行管理画面での「DNSレコード設定」の場所と文言（開いて確認する）
- Xserverの無料独自SSLがネームサーバー移行後も自動更新されるか（AレコードがXserverを指したままなら通常は問題ないが、初回更新時に確認する）

## 不採用の代替案: Xserverを写真の預かり所にする

DNSに一切触らず、Xserver上のサブドメインにPHPを置いて写真を預かり、ミニPCが1分ごとに取りに行く方式。
サイトへのリスクはほぼゼロだが、3Dオフィスの遠隔観察のような双方向の用途には使えない。トンネルが何らかの理由で使えなくなった時の退路として記録だけ残す。
