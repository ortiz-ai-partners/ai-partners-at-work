# ortiz-ai.partners をお散歩Claudeに使う（サイト・メールと共存させる）

前提: ドメインはお名前.com、サイトとメールはXserverで稼働中。**事業のサイトとメールを止めないこと**が最優先。

## 結論

- 短期は **選択肢B（Xserverを預かり所にする）**。DNSに触らないのでサイト・メールへの影響がほぼゼロ
- 長期は **選択肢A（Cloudflare Tunnel）**。3Dオフィスを外から見るなど、用途が広がったら移る
- AへB移行後もBは残せる（バックアップ経路）

## 選択肢B: Xserverを写真の預かり所にする

```
StackChan ──POST──▶ osanpo.ortiz-ai.partners（Xserver上のPHP）
                          ▲ 家のミニPCが1分ごとに新着を取りに行く（外向き通信のみ）
                          ▼ 一言(latest.txt)を書き戻す → StackChanが読みに来る
```

手順:
1. Xserverサーバーパネルでサブドメイン `osanpo` を作る（SSLも有効化）
2. そのディレクトリに受け取り用PHPと、書き戻し用PHPを置く（合言葉トークン必須）
3. ミニPCに「1分ごとに新着JPEGを取ってきて `claude -p` に見せ、結果を書き戻す」スクリプトを置く
4. StackChanの `SERVER` を `https://osanpo.ortiz-ai.partners` にする

注意: Xserverの管理画面の文言・PHP設置の細部は実際に開いてから確認する（未確認）。

## 選択肢A: Cloudflare Tunnel

手順:
1. Cloudflare無料アカウントで `ortiz-ai.partners` を追加（移管ではない。所有はお名前.comのまま）
2. **切り替え前に** Xserverの「DNSレコード設定」を全部控える
   - A（`@`, `www`）: サイトのIP
   - MX: メールサーバー
   - TXT: SPF / DKIM / DMARC（落とすと送信メールが迷惑メール扱いになる）
   - その他CNAMEなど
3. Cloudflareに同じレコードを入れ、Xserver側の一覧と目視で突き合わせる
4. 各レコードのプロキシ（橙の雲）は **全部オフ（灰色、DNS only）**。サイトの前にCloudflareを立たせない
5. お名前.comでネームサーバーをCloudflare指定のものに変更（反映は数分〜数時間）
6. サイト表示とメール送受信を確認
7. ミニPCに `cloudflared` を入れ、トンネル作成。`osanpo.ortiz-ai.partners` → `localhost:5072`
8. 将来: `office.ortiz-ai.partners` → `localhost:3939` を同じトンネルに足すと3Dオフィスを外から見られる（鍵をかけること）

## どちらでも共通

- 外に出す窓口には合言葉（トークン）を必ず付ける
- ESP32からのHTTPSは、実験中は証明書検証なし → 動いたら正しい証明書を入れる
