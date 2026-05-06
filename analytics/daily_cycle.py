"""
日次自動サイクル（end-to-end）

1. GA4 + Search Console からデータ取得
2. レポート(Markdown)生成
3. 履歴CSVに追記、前回比・前週比を計算
4. Claude API で対応方針(Action Plan)を生成
5. 統合ファイルを analytics/output/daily-YYYY-MM-DD.md として保存
6. （オプション）latest.md を最新ファイルへのリンクとして更新

タスクスケジューラから呼ばれることを想定:
    pythonw.exe daily_cycle.py --days 28 --quiet
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env", override=True)   # ルート .env（ANTHROPIC_API_KEY 等）
load_dotenv(BASE_DIR / ".env", override=True)   # アナリティクス専用 .env（GA4_PROPERTY_ID 等）
sys.path.insert(0, str(BASE_DIR))

CACHE_DIR = BASE_DIR / ".cache"
OUTPUT_DIR = BASE_DIR / "output"
LATEST_FILE = OUTPUT_DIR / "latest.md"
DAILY_LOG = OUTPUT_DIR / "cycle.log"


def log(msg: str, quiet: bool = False):
    line = f"[{date.today().isoformat()}] {msg}"
    if not quiet:
        print(line, flush=True)
    DAILY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DAILY_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_cycle(days: int = 28, quiet: bool = False, skip_fetch: bool = False) -> Path:
    """フルサイクル実行。生成された統合ファイルのパスを返す"""
    today = date.today().isoformat()

    # ──────────────────────────────────────────
    # Step 1: データ取得
    # ──────────────────────────────────────────
    if skip_fetch:
        cache_path = CACHE_DIR / f"data-{today}-{days}d.json"
        if not cache_path.exists():
            raise FileNotFoundError(f"--skip-fetch指定だが本日のキャッシュなし: {cache_path}")
        log(f"キャッシュ利用: {cache_path.name}", quiet)
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        ga4, gsc = data["ga4"], data["gsc"]
    else:
        log(f"データ取得開始（{days}日分）", quiet)
        from fetch_ga4 import fetch_all as fetch_ga4_all
        from fetch_search_console import fetch_all as fetch_gsc_all
        ga4 = fetch_ga4_all(days)
        gsc = fetch_gsc_all(days)
        log(f"GA4: {sum(len(v) for v in ga4.values())}行 / GSC: {sum(len(v) for v in gsc.values())}行", quiet)

        # キャッシュ保存
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / f"data-{today}-{days}d.json"
        cache_path.write_text(json.dumps(
            {"ga4": ga4, "gsc": gsc, "days": days},
            ensure_ascii=False, indent=2), encoding="utf-8")

    # ──────────────────────────────────────────
    # Step 2: レポート生成
    # ──────────────────────────────────────────
    log("レポート生成", quiet)
    from generate_report import render
    report_md = render(ga4, gsc, days)

    # ──────────────────────────────────────────
    # Step 3: 履歴CSV追記＋差分計算
    # ──────────────────────────────────────────
    log("履歴CSV追記", quiet)
    from history import append, get_deltas, format_deltas_md
    summary_row = append(ga4, gsc, days)
    deltas = get_deltas(summary_row)
    deltas_md = format_deltas_md(deltas)

    # ──────────────────────────────────────────
    # Step 4: 対応方針（Claude API）
    # ──────────────────────────────────────────
    log("Claudeで対応方針を生成", quiet)
    from action_planner import generate_action_plan
    try:
        action_plan = generate_action_plan(report_md, deltas_md, days)
        action_status = "✓"
    except Exception as e:
        action_plan = f"_対応方針生成に失敗: {e}_"
        action_status = f"FAILED: {e}"
    log(f"対応方針: {action_status}", quiet)

    # ──────────────────────────────────────────
    # Step 5: 統合ファイル保存
    # ──────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"daily-{today}.md"

    parts = [
        f"# 日次サイト分析レポート — {today}",
        "",
        f"_実行: 直近{days}日 / 自動サイクル_",
        "",
        "## 📈 前回比・前週比",
        "",
        deltas_md,
        "",
        "---",
        "",
        action_plan,
        "",
        "---",
        "",
        report_md,
    ]
    out_path.write_text("\n".join(parts), encoding="utf-8")

    # latest.md は最新版へのコピー
    LATEST_FILE.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")

    log(f"完了: {out_path.name}", quiet)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="日次自動サイクル実行")
    ap.add_argument("--days", type=int, default=28, help="分析期間 (デフォルト 28日)")
    ap.add_argument("--quiet", action="store_true", help="標準出力を抑制 (タスクスケジューラ用)")
    ap.add_argument("--skip-fetch", action="store_true", help="本日のキャッシュを利用 (再生成のみ)")
    args = ap.parse_args()

    try:
        path = run_cycle(days=args.days, quiet=args.quiet, skip_fetch=args.skip_fetch)
        if not args.quiet:
            print(f"\n✓ 出力: {path}")
            print(f"  最新版: {LATEST_FILE}")
        sys.exit(0)
    except Exception as e:
        log(f"[ERROR] {e}", quiet=False)
        import traceback
        log(traceback.format_exc(), quiet=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
