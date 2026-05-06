"""
アナリティクスレポート生成 CLI

使い方:
    python analytics/run.py                    # 直近28日でレポート生成
    python analytics/run.py --days 90          # 期間指定
    python analytics/run.py --report only      # キャッシュからレポートだけ再生成
    python analytics/run.py --json             # JSON生データだけ出力
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR.parent / ".env", override=True)  # ルート .env
load_dotenv(BASE_DIR / ".env", override=True)          # アナリティクス専用 .env

CACHE_DIR = BASE_DIR / ".cache"
OUTPUT_DIR = BASE_DIR / "output"


def _cache_path(days: int) -> Path:
    return CACHE_DIR / f"data-{date.today().isoformat()}-{days}d.json"


def fetch_fresh(days: int) -> tuple[dict, dict]:
    """両APIから新規取得"""
    from fetch_ga4 import fetch_all as fetch_ga4_all
    from fetch_search_console import fetch_all as fetch_gsc_all

    print(f"[1/2] GA4 から取得中（{days}日分）...", flush=True)
    ga4 = fetch_ga4_all(days)
    print(f"      ✓ {sum(len(v) for v in ga4.values())} 行取得")

    print(f"[2/2] Search Console から取得中（{days}日分）...", flush=True)
    gsc = fetch_gsc_all(days)
    print(f"      ✓ {sum(len(v) for v in gsc.values())} 行取得")

    return ga4, gsc


def save_cache(ga4: dict, gsc: dict, days: int) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(days)
    path.write_text(json.dumps({"ga4": ga4, "gsc": gsc, "days": days},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_cache(days: int) -> tuple[dict, dict] | None:
    path = _cache_path(days)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["ga4"], data["gsc"]


def main():
    ap = argparse.ArgumentParser(description="サイトアクセス分析レポート生成")
    ap.add_argument("--days", type=int, default=28, help="分析期間（日数、デフォルト28）")
    ap.add_argument("--report", choices=["only"], help="onlyならキャッシュからレポートだけ再生成")
    ap.add_argument("--json", action="store_true", help="JSON生データを標準出力")
    args = ap.parse_args()

    sys.path.insert(0, str(BASE_DIR))

    if args.report == "only":
        cached = load_cache(args.days)
        if not cached:
            print(f"[ERROR] キャッシュが見つかりません: {_cache_path(args.days)}")
            print("       --report only を外して新規取得してください")
            sys.exit(1)
        ga4, gsc = cached
        print(f"キャッシュから読込: {_cache_path(args.days).name}")
    else:
        try:
            ga4, gsc = fetch_fresh(args.days)
        except Exception as e:
            print(f"\n[ERROR] データ取得失敗: {e}")
            print("       analytics/setup.md を確認してください")
            sys.exit(1)
        cache_path = save_cache(ga4, gsc, args.days)
        print(f"      キャッシュ保存: {cache_path.name}")

    if args.json:
        print(json.dumps({"ga4": ga4, "gsc": gsc}, ensure_ascii=False, indent=2))
        return

    from generate_report import render, save_report
    print("\nレポート生成中...")
    md = render(ga4, gsc, args.days)
    out = save_report(md, OUTPUT_DIR)
    print(f"      ✓ 出力: {out}")
    print(f"\n--- レポート冒頭 ---\n")
    print("\n".join(md.split("\n")[:30]))
    print("\n...")
    print(f"\n完全版: {out}")


if __name__ == "__main__":
    main()
