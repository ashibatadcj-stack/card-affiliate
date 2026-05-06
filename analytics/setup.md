# アナリティクスAPI連携 セットアップガイド

GA4 と Search Console のデータをPythonから自動取得するための初期設定手順です。
**所要時間：約15〜20分**（Googleアカウントへのアクセス権限が必要）

---

## 完了後にできること

```powershell
cd C:\Users\ashib\card-affiliate
python analytics/run.py                # 直近28日のレポート生成
python analytics/run.py --days 90      # 期間指定
python analytics/run.py --report only  # キャッシュからレポートだけ再生成
```

→ `analytics/output/report-YYYY-MM-DD.md` が生成される。

---

## Step 1: Google Cloud プロジェクト作成

1. https://console.cloud.google.com/ にアクセス
2. 上部のプロジェクトドロップダウン → 「**新しいプロジェクト**」
3. プロジェクト名: `card-affiliate-analytics`（任意）→ 作成
4. 作成完了後、そのプロジェクトを選択した状態にする

## Step 2: 必要なAPIを有効化

「APIとサービス」→「ライブラリ」で以下2つを検索→有効化：

- ✅ **Google Analytics Data API**
- ✅ **Google Search Console API**

## Step 3: サービスアカウント作成

1. 「IAMと管理」→「サービスアカウント」→「サービスアカウントを作成」
2. 名前: `card-affiliate-reader`（任意）→ 作成して続行 → 完了
3. 作成された一覧から該当アカウントをクリック →「キー」タブ
4. 「鍵を追加」→「新しい鍵を作成」→ JSON 形式 → 作成
5. JSONファイルがダウンロードされる
6. ダウンロードしたファイルを以下に保存：

```
C:\Users\ashib\card-affiliate\analytics\credentials\service-account.json
```

> ⚠️ このJSONには認証情報が入っています。`.gitignore` で除外済みなので絶対にコミットしないこと。

7. サービスアカウントの **メールアドレス** をコピー（後で使用）。
   形式: `card-affiliate-reader@<project-id>.iam.gserviceaccount.com`

## Step 4: GA4 にサービスアカウントを追加

1. https://analytics.google.com/ にアクセス
2. 該当プロパティ（`G-HWEHFB30XE` のもの）を選択
3. 左下「**管理**」（歯車アイコン）
4. 「プロパティのアクセス管理」→ 右上「+」→「ユーザーを追加」
5. メールアドレス：Step 3 でコピーしたサービスアカウントのメール
6. 役割：**閲覧者** を選択 → 追加

5. **GA4 プロパティID** を控える：
   - 「管理」→ プロパティ列の「プロパティの詳細」
   - 「プロパティID」（数字のみ、例 `123456789`）
   - 後で `analytics/.env` に書き込む

## Step 5: Search Console にサービスアカウントを追加

1. https://search.google.com/search-console にアクセス
2. プロパティ `https://cardshindan.com/` を選択
3. 左メニュー「**設定**」→「ユーザーと権限」
4. 「**ユーザーを追加**」
5. メールアドレス：Step 3 でコピーしたサービスアカウントのメール
6. 権限：**制限付き** で十分（読み取りのみ）→ 追加

> Search Console プロパティが未登録の場合は、左上のドロップダウン → 「プロパティを追加」から先に登録してください。

## Step 6: 環境変数設定

`analytics/.env`（リポジトリルートの`.env`とは別ファイル）を作成：

```dotenv
# GA4
GA4_PROPERTY_ID=123456789

# Search Console（サイトURL）
GSC_SITE_URL=https://cardshindan.com/

# 認証ファイルへのパス（リポジトリルートからの相対）
GOOGLE_APPLICATION_CREDENTIALS=analytics/credentials/service-account.json
```

> サイトURLは末尾スラッシュ必須。

## Step 7: Python依存関係インストール

```powershell
cd C:\Users\ashib\card-affiliate
pip install -r analytics/requirements.txt
```

## Step 8: 動作確認

```powershell
python analytics/run.py --days 7
```

成功すれば `analytics/output/report-YYYY-MM-DD.md` が生成されます。

## Step 9: 日次サイクル自動化

ここまで成功したら、**毎日自動実行＋AI対応方針生成** までを組む：

```powershell
# 手動で1度サイクルを通す
python analytics/daily_cycle.py --days 28
```

→ `analytics/output/daily-YYYY-MM-DD.md` （対応方針＋詳細レポートの統合ファイル）と `latest.md` が生成される。

→ そのままタスクスケジューラに登録するには [`automation.md`](./automation.md) を参照。

---

## トラブルシューティング

| エラー | 原因 / 対応 |
|---|---|
| `403 PERMISSION_DENIED` | Step 4 / 5 の権限付与が未完了。GA4/Search Console にサービスアカウントを追加しているか確認 |
| `404 NOT_FOUND`（GA4）| `GA4_PROPERTY_ID` が間違っている。プロパティIDは数字のみ |
| `404`（Search Console）| `GSC_SITE_URL` が登録済みプロパティと完全一致しているか確認（`https://` / 末尾スラッシュ含む）|
| `FileNotFoundError: service-account.json` | Step 3 のJSONを所定パスに保存できているか確認 |
| データが空 | GA4は導入から24〜48時間データ未反映、Search Consoleは2〜3日のラグあり |

---

## 安全運用のポイント

- サービスアカウントJSONは絶対にコミットしない（`.gitignore` 設定済み）
- 鍵を漏らした疑いがあれば Google Cloud で即座に「キーを削除」→ 新規作成
- 役割は **閲覧者** で十分。書き込み権限は付与しない
