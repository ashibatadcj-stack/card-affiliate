# cardshindan PJ — Claude Code Action 用ガイド

このファイルは GitHub Actions 経由で Claude が動くときに参照するプロジェクトコンテキストです。

## サイト概要

- **本番URL**: https://cardshindan.com/
- **ホスティング**: GitHub Pages（`docs/` ディレクトリを公開）
- **カスタムドメイン**: `cardshindan.com`（`docs/CNAME`）
- **目的**: クレジットカード比較・診断アフィリエイトサイト
- **収益**: A8.net アフィリエイト（記事内バナー＋詳細ページCTA）

## ディレクトリ構成

```
card-affiliate/
├── docs/                       ← GitHub Pages 公開ディレクトリ
│   ├── index.html              ← トップページ
│   ├── articles/*.html         ← 41記事（カード詳細20＋比較ガイド15＋活用法6）
│   ├── assets/
│   │   ├── common.css          ← 全ページ共通スタイル
│   │   └── common.js           ← 全ページ共通JS（モバイルTOC等）
│   ├── sitemap.xml
│   ├── robots.txt
│   ├── 404.html                ← 旧URL自動リダイレクト
│   └── CNAME
├── analytics/                  ← 日次自動分析
│   ├── run_daily.bat           ← タスクスケジューラから6:00実行
│   ├── daily_cycle.py          ← GA4+Search Console取得
│   ├── notify_slack.py         ← Slack通知
│   └── output/daily-*.md       ← 日次レポート出力
├── articles_data.py            ← 全41記事のメタ情報（title/description等）
├── cards_data.py               ← カードマスター
├── generate_articles.py        ← Claude API で記事HTML生成
├── a8_banner_fetcher.py        ← A8 バナー自動取得・注入
├── submit_google_indexing.py   ← Google Indexing API 一括送信
├── submit_indexnow.py          ← IndexNow（Bing/Yandex）送信
└── .env                        ← API Keys（gitignore）
```

## コーディング規約

### HTML
- 全ページ UTF-8（BOM なし）
- `<head>` に必ず `canonical` link
- `<meta name="description">` の content 内では `"` を `&quot;` でエスケープ（HTML属性早期終了防止）
- 閉じタグは必ず `</tag>`（`/tag>` のような不正形式は禁止）

### CSS
- 共通スタイルは `docs/assets/common.css` のみに記述
- index.html 固有スタイルはインライン `<style>` 内
- レスポンシブブレークポイント: 860px / 768px / 600px / 420px

### Python
- ファイル読み書きは必ず `encoding="utf-8"` 明示（Windows のデフォルト cp932 を避ける）
- **cp932 へのフォールバック処理は禁止**（過去に文字化けバグの原因になった）

### Git コミットメッセージ
- 日本語OK、Conventional Commits 風（feat/fix/refactor/docs/chore）
- 1行目はサマリ、必要なら空行+本文

## デプロイフロー

`main` ブランチへの push で自動的に GitHub Pages に反映（1〜2分）。

## 自動化されているもの

1. **毎朝6:00**: タスクスケジューラ `card-affiliate-daily-analytics`
   - GA4 + Search Console データ取得
   - Claude API で対応方針生成
   - Google Indexing API へ43URL送信
   - IndexNow（Bing/Yandex）へ送信
   - **Slack 通知（日次レポート）**
2. **`@claude` メンション付きIssue/コメント**: claude-code-action が起動 ← このファイル

## アフィリエイトリンク管理

- A8リンク済 22ページ（`articles_data.py` の `aff_url` フィールド）
- A8リンク無し19ページには `alt-cta-section` で代替記事誘導済

## 修正の優先方針

1. **HTML/CSS/JSの修正**: 該当ファイルを直接編集
2. **記事内容の変更**: `articles_data.py` を編集 → `generate_articles.py <slug>` で再生成
3. **新カード追加**: `articles_data.py` と `cards_data.py` 両方に追加
4. **大量書き換えバッチ処理**: 必ず UTF-8 エンコード明示で実装

## やらないこと

- `.env` をリポジトリに含めない（gitignore対象）
- `cp932` フォールバック処理は書かない
- `<script>` 内に `</script>` を含む文字列を直書きしない（早期終了する）
- 過去のスクリプトの `add_canonical.py` `add_alt_cta.py` のような全ページ書き換えバッチは作らない（壊滅的バグの再発リスク）
