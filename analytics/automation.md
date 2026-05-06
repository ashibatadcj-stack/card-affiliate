# 日次自動サイクル セットアップ

`daily_cycle.py` を Windows タスクスケジューラに登録し、毎日自動実行する手順です。
**前提**: `setup.md` の Step 1〜8 を完了していること。

---

## サイクル全体の流れ

```
┌─────────────────────────────────────────────────────────────┐
│  毎日 09:00 (タスクスケジューラ)                            │
│                                                             │
│   ↓ run_daily.bat                                           │
│   ↓                                                         │
│   ├─ 1. GA4 から28日分のページ・流入・デバイス等を取得      │
│   ├─ 2. Search Console から検索クエリ・順位を取得           │
│   ├─ 3. レポートMarkdown生成                                │
│   ├─ 4. history.csv に1行追記（前日比・前週比を計算）       │
│   ├─ 5. Claude API で「今日のアクション TOP3」生成          │
│   └─ 6. analytics/output/daily-YYYY-MM-DD.md として保存     │
│                                                             │
│   ログ: analytics/output/cycle.log                          │
│   最新: analytics/output/latest.md                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 手動テスト

タスク登録の前に手動で1回成功させてください：

```powershell
cd C:\Users\ashib\card-affiliate
python analytics\daily_cycle.py --days 28
```

成功すれば `analytics/output/` に：
- `daily-2026-05-05.md` ← 統合レポート（前日比＋対応方針＋詳細データ）
- `latest.md`           ← 最新版へのコピー
- `history.csv`         ← 日次サマリー（1行追加）
- `cycle.log`           ← 実行ログ

が出力されます。

---

## Windows タスクスケジューラ登録（GUI）

1. **Win+R** → `taskschd.msc` でタスクスケジューラを開く
2. 右ペイン「**タスクの作成**」（基本タスクではなく）
3. **全般** タブ
   - 名前: `card-affiliate-daily-analytics`
   - 説明: `cardshindan.com の日次アクセス分析と対応方針自動生成`
   - 「ユーザーがログオンしているかどうかにかかわらず実行する」を選択
   - 「最上位の特権で実行する」にチェック
4. **トリガー** タブ → 「新規」
   - 設定: 毎日
   - 開始: 翌日の 09:00（任意）
   - 「有効」チェック
5. **操作** タブ → 「新規」
   - 操作: プログラムの開始
   - プログラム/スクリプト: `C:\Users\ashib\card-affiliate\analytics\run_daily.bat`
   - 開始（オプション）: `C:\Users\ashib\card-affiliate`
6. **条件** タブ
   - 「コンピューターをAC電源で使用している場合のみタスクを開始する」のチェックを外す（ノートPCでも実行）
   - 「ネットワーク接続が利用可能な場合のみ開始する」にチェック
7. **設定** タブ
   - 「タスクが失敗した場合の再起動の間隔」: 30分
   - 「再起動試行の最大数」: 3回
   - 「タスクを停止するまでの時間」: 30分
8. OK → ユーザーパスワード入力で完了

---

## コマンドラインでの登録（CLI）

GUI操作が面倒な場合：

```powershell
schtasks /create ^
  /tn "card-affiliate-daily-analytics" ^
  /tr "C:\Users\ashib\card-affiliate\analytics\run_daily.bat" ^
  /sc DAILY ^
  /st 09:00 ^
  /rl HIGHEST ^
  /f
```

確認:
```powershell
schtasks /query /tn "card-affiliate-daily-analytics" /v
```

手動実行:
```powershell
schtasks /run /tn "card-affiliate-daily-analytics"
```

削除:
```powershell
schtasks /delete /tn "card-affiliate-daily-analytics" /f
```

---

## 出力ファイルの確認

タスク実行後、以下を確認：

```powershell
# 最新レポートを開く
notepad C:\Users\ashib\card-affiliate\analytics\output\latest.md

# ログを確認
type C:\Users\ashib\card-affiliate\analytics\output\cycle.log

# 履歴CSV
type C:\Users\ashib\card-affiliate\analytics\output\history.csv
```

---

## 通知連携（オプション）

レポート生成後にSlack/メール通知を追加したい場合は、`daily_cycle.py` の最後に以下のような処理を追加できます：

### Slack Webhook 例

```python
# daily_cycle.py 末尾に追記
import os, requests
webhook = os.environ.get("SLACK_WEBHOOK_URL")
if webhook:
    summary = "..."  # 対応方針の冒頭3行など
    requests.post(webhook, json={"text": f"今日の分析: {out_path.name}\n{summary}"})
```

### Windows トースト通知

```powershell
# run_daily.bat の末尾に追記
powershell -Command "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('日次分析レポート完了')"
```

---

## トラブルシューティング

| 症状 | 確認ポイント |
|---|---|
| タスクは動くがレポートが生成されない | `analytics/output/cycle.log` を確認。エラー全文が記録されている |
| `python` コマンドが認識されない | バッチに `python` のフルパス（例: `C:\Python\python.exe`）を指定 |
| Claude API エラー | ルートの `.env` に `ANTHROPIC_API_KEY` が設定されているか確認 |
| 履歴CSVが文字化け | エクセルで開く時はインポート→UTF-8で読込 |
| 過去レポートが大量に溜まる | 月次で `analytics/output/daily-YYYY-MM-*.md` を `_archive/` に移動 |

---

## 運用Tips

- **CSVをExcelで開く**: `history.csv` をピボットでグラフ化すると週次・月次推移が一目瞭然
- **対応方針の振り返り**: 週末に `daily-*.md` をまとめてClaude Chatに貼り、「先週の提案で実施できたもの／効果は？」と問う
- **ABテスト連動**: 提案された改善を実施したら `history.csv` の「メモ」列を手動で追加して施策タイミングを記録
- **重複実行防止**: `cycle.log` を見て同じ日付のエントリが2行以上あれば設定を見直す
