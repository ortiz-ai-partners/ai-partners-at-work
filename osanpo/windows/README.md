# ミニPC（Windows 11）を お散歩Claude の受信サーバにする

## 1. 入れるもの（1回だけ）

PowerShell（管理者）で:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install OpenJS.NodeJS.LTS
winget install Cloudflare.cloudflared
npm install -g @anthropic-ai/claude-code
```

その後、普通のターミナルで `claude` を一度起動してログインしておく（`claude -p` はこのログインを使う）。
動作確認:

```powershell
claude -p "1+1は？"
```

## 2. リポジトリを置く

```powershell
git clone https://github.com/ortiz-ai-partners/ai-partners-at-work.git
cd ai-partners-at-work
git checkout claude/osanpo-claude-setup-z11ruf
```

## 3. 合言葉を決めて、手動で1回動かす

```powershell
copy osanpo\windows\osanpo.env.example osanpo\windows\osanpo.env
notepad osanpo\windows\osanpo.env      # OSANPO_TOKEN を長いランダム文字列に
osanpo\windows\start-osanpo.bat
```

別のPCやスマホ（同じWi-Fi）から `http://ミニPCのIP:5072/?token=合言葉` が開けば合格。
開けない時はWindowsファイアウォールに穴を開ける（家の中でのテスト用。トンネル経由だけなら不要）:

```powershell
netsh advfirewall firewall add rule name="osanpo 5072" dir=in action=allow protocol=TCP localport=5072
```

## 4. 自動起動にする

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\osanpo\windows\install-autostart.ps1
```

ログオン時に `start-osanpo.bat` が立ち上がる。ログは `osanpo\windows\osanpo.log`。

ミニPCは画面なしで運用するので、次の2つも設定する:
- **自動ログオン**: `netplwiz` で「ユーザーがこのコンピューターを使うには…」のチェックを外す（ログオンしないとタスクが走らない）
- **スリープ禁止**: 設定 → システム → 電源 → 画面とスリープ を「なし」に。または `powercfg /change standby-timeout-ac 0`

## 5. Cloudflare Tunnel を張る

Cloudflareダッシュボード → Zero Trust → Networks → Tunnels →「トンネルを作成」→ Windows を選ぶと
`cloudflared service install <長いトークン>` というコマンドが表示される。管理者PowerShellでそれを実行すると
**Windowsサービスとして登録され、起動時に自動で張られる**。

Public Hostname:
- Subdomain `osanpo` / Domain `ortiz-ai.partners` / Service `HTTP` / URL `localhost:5072`

外（スマホの4G）から `https://osanpo.ortiz-ai.partners/?token=合言葉` が開けば完成。

## 6. 外から様子を見る・触る

- 見るだけ: 上のURLをiPhoneのブラウザで開く
- 触る: iPhoneの「Windows App」（旧Microsoft Remote Desktop）で同じWi-Fi内からリモートデスクトップ。設定 → システム → リモートデスクトップ をオン

## つまずきそうな所

- `python` が「Microsoft Storeを開く」だけで終わる → 設定 → アプリ → アプリ実行エイリアス で python の項目をオフ
- `claude -p` がタスクから動かない → タスクは「ログオンしたユーザー」で動く前提。自動ログオンを忘れていないか
- 起動直後にWi-Fiがまだ繋がっておらず失敗 → タスクは1分おきに3回まで再試行する設定にしてある
