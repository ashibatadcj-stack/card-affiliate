"""
Claude を使った対応方針プランナー

入力:  日次レポート(Markdown) + 履歴差分(deltas) + サイト構造情報
出力:  優先度付き対応方針 (Markdown)

【2026-05-09 改訂2】
Anthropic API SDK 経由 → **claude CLI（Pro/Maxプラン）経由** に変更
- API課金なし（Pro/Maxプランの定額枠を消費）
- モデルを Haiku → **Sonnet** に格上げ（分析品質の向上）
- 自動化の安定性より分析品質を優先（CLI失敗時は明示的にエラーを出す）
- フォールバック: 環境変数 ALLOW_API_FALLBACK=1 のとき限り、API SDK にフォールバック
"""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
from pathlib import Path


SITE_CONTEXT = """
【サイト概要】
- ドメイン: cardshindan.com（新規ドメイン、2026年取得）
- 内容: クレジットカード・ファクタリング・キャッシング比較アフィリエイトサイト
- 公開ページ: 60URL（articles 57本＋ピラー3本＋index/about/privacy/search/404）
- 収益化: A8.net アフィリエイト
- カテゴリ:
  - クレジットカード系: 29記事（ピラー: pillar-credit-card.html）
  - ファクタリング系:    8記事（ピラー: pillar-factoring.html）
  - キャッシング系:      7記事（ピラー: pillar-cashing.html）
  - 決済代行・その他:   10記事
- 構造化データ: Article + Breadcrumb + Person + Organization + WebSite + FAQPage（全54記事）+ HowTo（33記事）
- インデックス状況: 2026-05初旬から検索表示が出始めた段階（GSC評価サイクル中）
- 既実装の改善: PR表記フッター集約 / rel=sponsored 全A8リンク付与 / canonical統一 /
  ピラー3本 / 内部リンク強化 / 関連記事サジェスト / 可視パンくず / dateModified同期 /
  検索ボックス構造化データ / GA4カスタムイベント計測（affiliate_click等）
"""


PROMPT_TEMPLATE = """\
あなたはSEO・コンテンツマーケティングに精通した分析担当者です。
以下のサイトのアクセス解析レポートを読み、**今日〜今週中に取り組むべきアクション** を提案してください。

ただし、本サイトは新規ドメインで Google 評価サイクル中です。**統計的に意味のないサンプルでの安易な改善提案は禁止**で、
「今は何もしない（待機）」も妥当な選択肢として正面から評価してください。

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

- **対象**: 具体的なページ名やID（例: articles/rakuten.html）または「サイト全体」
- **必要性評価**: 以下3点を明示し、いずれか1つでも満たさない場合は 🟢（待機）に格下げまたは提案除外
  1. データのサンプルサイズは判断に十分か（KW別表示回数 ≥ 30 / ページ別セッション ≥ 50 が目安）
  2. 直近1〜2週間で同じ箇所を変更していないか（評価サイクル中断リスクの確認）
  3. 既に類似の対応が完了済みでないか（重複対応の防止）
- **効果見込み**: 期待効果を定量的に提示。「CTR 0%→5%」のような数値目標を、根拠（業界平均 / 類似改善実績）と共に記載。**算出不能なら正直に「推定不可」と書く**
- **副作用リスク**: 実施した場合のマイナス影響を1〜2点（例: Google 再評価まで順位リセットの可能性 / クロールバジェット消費）
- **代替案**: 「今は何もしない（待つ）」を含む2案以上の選択肢
- **やること**: 30分〜2時間でできる具体的な作業3〜5ステップ（推奨案を採用する場合のみ記載）
- **期待効果**: 上記「効果見込み」の要約と、検証方法（何日後・どの指標で判定するか）

## 📈 中期施策（今週〜2週間）

3〜5件、短く列挙。各項目は1行で「対象 → 内容 → 期待効果」を明記。

## 🔍 注視すべきトレンド

数値の異常変動・好兆候を1〜3点。各項目について「これは統計的に意味のある変化か / ノイズか」の判定を含める。

---

【🛑 アンチパターン警告：以下に該当する施策は 🟢 待機 に格下げするか提案から除外せよ】

1. **微小サンプル**: 表示回数 < 30 のページに対するタイトル/メタ変更
2. **評価サイクル妨害**: 直近2週間以内にコンテンツ変更したページの再修正
3. **不可能な順位上昇**: 順位90位以下のページに対する内部修正で順位を上げようとする提案（被リンク不足が主因のため動かない）
4. **新URL追加**: 既存URLのインデックスが安定するまで Phase 3 的な新規記事量産は控える
5. **抽象提案**: 「コンテンツ改善」「SEOを最適化」等の具体性欠如した文言
6. **モバイル数値の過剰反応**: モバイルセッション < 20 で直帰率の改善施策を優先課題化する
7. **ボット流入の誤認**: 平均滞在 < 5秒のページを「直帰率改善対象」とする（ボット流入の可能性大）

---

【💚 待機の積極的活用】

評価結果として「今は何もしない」が最善である場合、TOP3の1〜2件を **🟢 待機（XX日後に再評価）** として書いてよい。
むしろ Phase 2/E の改善が浸透中の現フェーズでは、**安易に手を入れず Google評価サイクルを完走させる方が効果的**。
待機項目では「何を観測するか・いつ判定するか・判定基準は何か」を明記する。

---

【その他制約】
- 提案は具体的に。「コンテンツを改善」のような抽象的表現は禁止
- 必ずデータの数値を根拠として引用すること
- 当サイトのページ構成（articles/{{id}}.html / pillar-*.html）を踏まえて、どのページのどこを編集すべきか明示
- A8アフィリエイト収益最大化の視点も入れる（ただし統計的根拠が伴う場合のみ）
- 約2500〜4000字（必要十分な長さ。冗長は避け、各項目を必ず最後まで書ききる）
"""


# ============================================================
# 実行: claude CLI 経由（Pro/Maxプラン消費・課金なし・Sonnet）
# ============================================================

def _find_claude_cli() -> str | None:
    """OS に応じて claude CLI のパスを返す（見つからなければ None）"""
    if platform.system() == 'Windows':
        # Windows: shutil.which は通常 .cmd を見つけられる
        for name in ['claude.cmd', 'claude']:
            path = shutil.which(name)
            if path:
                return path
        # 既知のインストールパスをフォールバック
        npm_dir = Path(os.environ.get('APPDATA', '')) / 'npm'
        for fname in ('claude.cmd', 'claude'):
            cand = npm_dir / fname
            if cand.exists():
                return str(cand)
    else:
        path = shutil.which('claude')
        if path:
            return path
    return None


def _generate_via_cli(prompt: str, model: str = 'sonnet', timeout_sec: int = 600) -> str:
    """claude CLI 経由でレスポンス取得（Pro/Maxプラン消費）"""
    cli = _find_claude_cli()
    if not cli:
        raise RuntimeError(
            "claude CLI が見つかりません。`npm install -g @anthropic-ai/claude-code` で導入してください"
        )

    # ツール使用を無効化（純粋にテキスト生成のみさせる）
    cmd = [
        cli,
        '--print',                         # 非対話モードで応答を出力して終了
        '--model', model,                  # 'sonnet' or 'opus' or 'haiku'
        '--disallowedTools', 'Bash', 'Edit', 'Write', 'Read', 'Glob', 'Grep',
        '--disable-slash-commands',        # スラッシュコマンド無効
    ]

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout_sec,
    )

    if result.returncode != 0:
        # 失敗時は CLI が出した stderr を含めて投げる
        err = (result.stderr or '').strip()[:600]
        out = (result.stdout or '').strip()[:200]
        raise RuntimeError(
            f"claude CLI failed (exit {result.returncode})\n"
            f"  stderr: {err}\n"
            f"  stdout: {out}"
        )

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("claude CLI は空の応答を返しました（ログイン切れの可能性）")
    return output


def _generate_via_api(prompt: str) -> str:
    """API SDK 経由（フォールバック・課金あり）"""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env", override=True)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が未設定です（フォールバック不可）")

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def generate_action_plan(report_md: str, deltas_md: str, period_days: int) -> str:
    """対応方針 Markdown を返す"""
    prompt = PROMPT_TEMPLATE.format(
        site_context=SITE_CONTEXT,
        deltas=deltas_md,
        report=report_md,
        period_days=period_days,
    )

    # 優先: claude CLI（Pro/Maxプラン枠・課金なし・Sonnet）
    try:
        return _generate_via_cli(prompt, model='sonnet')
    except Exception as e:
        msg = f"[ERROR] claude CLI 経由の生成に失敗: {e}"
        # フォールバック許可フラグ確認
        if os.environ.get("ALLOW_API_FALLBACK", "").lower() in ('1', 'true', 'yes'):
            print(f"{msg}\n[WARN] API SDK へフォールバック（課金発生）...")
            return _generate_via_api(prompt)
        # フォールバック禁止 → エラー伝搬
        print(msg)
        raise
