"""
Claude API を使った対応方針プランナー

入力:  日次レポート(Markdown) + 履歴差分(deltas) + サイト構造情報
出力:  優先度付き対応方針 (Markdown)

毎日、レポートを Claude に渡して「今日やるべき具体的アクション TOP3〜5」を返してもらう。
"""
from __future__ import annotations
import os
from pathlib import Path

import anthropic


SITE_CONTEXT = """
【サイト概要】
- ドメイン: cardshindan.com
- 内容: クレジットカード比較・カード詳細解説アフィリエイトサイト
- 公開ページ: 35記事（記事9 + カード詳細26）
- 収益化: A8.net アフィリエイト
- カテゴリ:
  - guide:       初心者ガイド (1)
  - compare:     比較・ランキング (3)
  - attribute:   属性別 (2: 学生/主婦)
  - purpose:     目的別 (3: 2枚持ち/海外旅行/審査通りやすい)
  - card-detail: カード詳細 (26)
- 共通テンプレート: docs/articles/*.html, common.css 2カラム + TOC + サイドバー
- データ管理: articles_data.py（35件メタデータ）→ generate_articles.py で生成
"""


PROMPT_TEMPLATE = """\
あなたはSEO・コンテンツマーケティングに精通した分析担当者です。
以下のサイトのアクセス解析レポートを読み、**今日〜今週中に取り組むべき具体的アクション** を提案してください。

{site_context}

【直近の指標推移（前回比・前週比）】
{deltas}

【最新レポート（直近{period_days}日）】
{report}

---

【出力フォーマット（厳守）】

## 🎯 今日のアクション TOP3

各アクションは以下の構造で書く:

### 1. [アクション名]（優先度: 🔴/🟡/🟢）
- **対象**: 具体的なページ名やID（例: articles/rakuten.html）
- **理由**: データが示している問題や機会（数字で根拠を示す）
- **やること**: 30分〜2時間でできる具体的な作業3〜5ステップ
- **期待効果**: 「CTR x% 改善」「順位 N位上昇」など定量目標

## 📈 中期施策（今週〜2週間）

3〜5件、短く列挙。

## 🔍 注視すべきトレンド

数値の異常変動・好兆候を1〜3点。

---

【制約】
- 提案は具体的に。「コンテンツを改善」「SEOを最適化」のような抽象的な表現は禁止
- 必ずデータの数値を根拠として引用すること
- 当サイトのページ構成（articles/{{id}}.html）を踏まえて、どのページのどこを編集すべきか明示
- A8アフィリエイト収益最大化の視点も入れる
- 約1500〜2500字
"""


def generate_action_plan(report_md: str, deltas_md: str, period_days: int) -> str:
    """Claude を呼び出して対応方針 Markdown を返す"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # fallback: ルートの .env を override=True で読込
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env", override=True)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が未設定です")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(
        site_context=SITE_CONTEXT,
        deltas=deltas_md,
        report=report_md,
        period_days=period_days,
    )

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
