# SNS自動運用 セットアップ手順

このドキュメントは **ユーザー本人が手動で実施** する作業をまとめたものです。  
所要時間: 約2〜3時間（API承認の待ち時間を除く）

---

## 全体フロー

```
[1] X アカウント作成 → [2] X API キー取得 → [3] Threads アカウント作成
                                                    ↓
[6] 動作確認 ← [5] GitHub Secrets 登録 ← [4] Threads API トークン取得
```

---

## 1. X (Twitter) アカウント作成

1. <https://twitter.com/i/flow/signup> にアクセス
2. 専用のメールアドレス（推奨: `cardshindan+x@gmail.com` のような Gmail のエイリアス）と電話番号で新規登録
3. **アカウント名** : `カード比較ナビ` または `カード診断ナビ` 推奨
4. **ユーザー名** : `@cardshindan` （取得可能な近いハンドル）
5. **プロフィール文** に以下を含める：
   ```
   クレジットカード比較・診断サイト「カード比較ナビ」公式
   楽天/エポス/Amazon/三井住友プラチナ等を徹底解説 #PR
   👇 あなたに合うカードを30秒診断
   https://cardshindan.com
   ```
6. **アイコン** : サイトのファビコンと統一（後でも変更可）

⚠️ **アカウント開設直後の連投は凍結リスクが高い**。最初の2週間は手動で1日1〜2投稿、徐々に増やすこと。

---

## 2. X Developer Portal で API キー取得

### 2-1. Developer 登録

1. <https://developer.twitter.com/> にアクセス → "Sign up for Free Account"
2. 利用目的を英語200文字以上で記載（例: `Building a personal credit card comparison website. Will use API to schedule posts about credit card information for Japanese users. Posts will be informational, no spam.`）
3. **Free plan** を選択（月1,500投稿まで無料）

### 2-2. App 作成 + キー発行

1. Dashboard → "Create Project" → 名称: `cardshindan-sns`
2. Project内に App 作成 → 名称: `cardshindan-poster`
3. **Keys and tokens** タブから以下4つを取得・保存：
   - `API Key` (= Consumer Key)
   - `API Key Secret` (= Consumer Secret)
   - `Access Token`（"Generate" ボタンで発行）
   - `Access Token Secret`
4. **User authentication settings** で：
   - App permissions: **Read and write**
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI: `http://localhost:8080/callback`
   - Website URL: `https://cardshindan.com`

⚠️ Access Token を発行する **前に** App permissions を `Read and write` に変更しておくこと。あとから変えるとトークン再発行が必要。

---

## 3. Threads アカウント作成

1. Instagram アプリで通常アカウント作成（Instagramアカウントが Threads の前提）
2. Instagram から Threads アプリを起動 → 連携
3. ユーザー名: Xと同じ `@cardshindan` 推奨
4. プロフィール: Xと同様

---

## 4. Meta Developer App + Threads API トークン取得

### 4-1. Meta Developer 登録

1. <https://developers.facebook.com/> → "My Apps" → "Create App"
2. App type: **Business**
3. App name: `cardshindan-threads`

### 4-2. Threads API を追加

1. App Dashboard → "Add Product" → **Threads** を選択
2. Use Cases に "Access the Threads API" を追加
3. 必要な permissions: `threads_basic`, `threads_content_publish`

### 4-3. アクセストークン取得

1. Dashboard → "Threads API" → "API Setup with User Token"
2. Threadsアカウントでログイン → 認可
3. **Short-lived token** が発行される（1時間有効）
4. 即座に **Long-lived token** に交換（60日有効）：
   ```
   GET https://graph.threads.net/access_token
     ?grant_type=th_exchange_token
     &client_secret={app_secret}
     &access_token={short_lived_token}
   ```
   ブラウザで上記URLを叩くか curl で実行
5. Long-lived token と **Threads User ID** を保存

⚠️ Long-lived token は60日で切れる。`refresh_access_token` エンドポイントで延長できるが、その自動化は後続フェーズで対応（当面は2ヶ月に1回手動更新）。

---

## 5. GitHub Secrets に登録

1. <https://github.com/ashibatadcj-stack/card-affiliate/settings/secrets/actions> を開く
2. "New repository secret" で以下を順番に登録：

| Secret 名 | 内容 |
|-----------|------|
| `X_API_KEY` | 手順2-2の API Key |
| `X_API_SECRET` | 手順2-2の API Key Secret |
| `X_ACCESS_TOKEN` | 手順2-2の Access Token |
| `X_ACCESS_TOKEN_SECRET` | 手順2-2の Access Token Secret |
| `THREADS_USER_ID` | 手順4-3の Threads User ID |
| `THREADS_ACCESS_TOKEN` | 手順4-3の Long-lived token |

⚠️ **絶対にコードにキーを直書きしない**。`.env` も `.gitignore` 済みだが念のため確認。

---

## 6. 動作確認

### 6-1. ローカルで確認

```bash
cd C:\Users\ashib\card-affiliate
pip install -r sns/requirements.txt
cp sns/.env.example sns/.env
# sns/.env を編集してAPIキーを記入
```

### 6-2. ドライラン（投稿せず生成内容を確認）

```bash
python sns/generate_posts.py --dry-run
```

→ 標準出力に1ヶ月分のサンプル投稿文が表示される。

### 6-3. テスト投稿

```bash
# X にテスト投稿
python sns/post_x.py --test "テスト投稿 from cardshindan automation"

# Threads にテスト投稿
python sns/post_threads.py --test "テスト投稿 from cardshindan automation"
```

→ 投稿されたら **手動で削除**。

### 6-4. キュー生成

```bash
python sns/generate_posts.py
```

→ `sns/queue/posts_2026-05.json` が生成される。

### 6-5. GitHub Actions 手動実行

1. GitHub リポジトリ → Actions タブ → `SNS自動投稿` workflow を選択
2. "Run workflow" をクリック → 手動トリガー
3. ログでエラーなく完了することを確認
4. X / Threads に投稿されているか確認

### 6-6. 自動運用開始

スケジュール設定済み（cron）。翌朝08:00（JST）から自動投稿が始まります。

---

## トラブルシューティング

| 症状 | 対策 |
|------|------|
| X で 401 エラー | Access Token に Write 権限がない → 手順2-2のApp permissionsを再確認、Token再発行 |
| X で 429 エラー | レート制限。次回cronで自動リトライされるので放置 |
| Threads で 400 エラー | Long-lived token 期限切れの可能性。手順4-3で再取得 |
| 投稿が重複する | `posted_log.json` が削除されている可能性。`queue/posts_*.json` の `posted: true` も併用してチェック中 |

---

## 運用開始後のチェック項目（毎週）

- [ ] X / Threads ともに過去7日で20〜21件投稿されているか
- [ ] 投稿が画像なしテキストのみで成功しているか
- [ ] `cardshindan.com` の Google Analytics で `utm_source=x` の流入があるか
- [ ] A8.net 管理画面でクリック数が増えているか
- [ ] アカウントに警告・凍結通知が来ていないか
