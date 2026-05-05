"""
SNS投稿キュー生成スクリプト

cards_data.py のカード情報 × テンプレート × ランダム要素 から
1ヶ月分の投稿文を生成し、queue/posts_YYYY-MM.json に書き出す。

使い方:
    python sns/generate_posts.py            # 当月分を生成（既存があれば skip）
    python sns/generate_posts.py --dry-run  # 標準出力に表示するだけ
    python sns/generate_posts.py --month 2026-06 --force  # 指定月を強制再生成
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Windows コンソールの cp932 で絵文字を出力するため UTF-8 に切り替え
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# card-affiliate/ をパスに追加（cards_data.py を import するため）
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from cards_data import CARDS  # noqa: E402

# サイトURL（環境変数で上書き可）
SITE_URL = os.environ.get("SITE_URL", "https://cardshindan.com")

# 1日の投稿スロット (JST)
DAILY_SLOTS = ["08:00", "12:00", "20:00"]

# プラットフォーム
PLATFORMS = ["x", "threads"]


def load_templates(platform: str) -> dict[str, Any]:
    path = SCRIPT_DIR / "templates" / f"{platform}_templates.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def card_url(card: dict[str, Any], platform: str, year_month: str) -> str:
    """カード詳細ページの内部URLを UTM 付きで返す。"""
    slug = card["id"]
    campaign = year_month.replace("-", "")
    return f"{SITE_URL}/articles/{slug}.html?utm_source={platform}&utm_medium=sns&utm_campaign={campaign}"


def render_post(template: str, card: dict[str, Any], hashtags: list[str], url: str) -> str:
    return template.format(
        name=card["name"],
        annual_fee=card["annual_fee"],
        points=card["points"],
        feature=random.choice(card["features"]),
        target=random.choice(card["target"]),
        url=url,
        hashtags=" ".join(hashtags),
    )


def pick_hashtags(pool: list[str], n: int = 3) -> list[str]:
    return random.sample(pool, k=min(n, len(pool)))


def text_hash(text: str) -> str:
    """重複検出用のハッシュ（最初の80文字を正規化）。"""
    norm = "".join(text.split())[:80]
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def truncate_for_x(text: str, max_len: int = 280, url_len: int = 23) -> str:
    """X用に文字数を保証。t.co短縮(URL=23文字換算)を考慮した実効長で判定する。"""
    # https://… を23文字としてカウント
    import re

    url_re = re.compile(r"https?://\S+")
    placeholder = "x" * url_len
    measured = url_re.sub(placeholder, text)
    if len(measured) <= max_len:
        return text
    # 末尾を削って収める（URL/ハッシュタグは末尾なので、本文側を削る）
    over = len(measured) - max_len
    cut = len(text) - over - 1
    return text[:cut].rstrip() + "…"


def generate_for_month(year: int, month: int, force: bool = False) -> dict[str, Any]:
    year_month = f"{year:04d}-{month:02d}"
    queue_path = SCRIPT_DIR / "queue" / f"posts_{year_month}.json"
    if queue_path.exists() and not force:
        print(f"[skip] {queue_path.name} already exists. Use --force to regenerate.")
        with queue_path.open(encoding="utf-8") as f:
            return json.load(f)

    templates_x = load_templates("x")
    templates_threads = load_templates("threads")

    posts: list[dict[str, Any]] = []
    days_in_month = calendar.monthrange(year, month)[1]

    # シードを月固定にして再現性を担保
    random.seed(int(f"{year}{month:02d}"))

    seen_hashes: set[str] = set()

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        # 各日: 3スロット × 2プラットフォーム = 6投稿
        for slot_idx, slot_time in enumerate(DAILY_SLOTS):
            for platform in PLATFORMS:
                # カードはローテーション（曜日 + スロット + plat で分散）
                card_idx = (day + slot_idx + (0 if platform == "x" else 2)) % len(CARDS)
                card = CARDS[card_idx]

                templates_data = templates_x if platform == "x" else templates_threads
                template = random.choice(templates_data["templates"])
                hashtags = pick_hashtags(templates_data["hashtag_pool"], n=3)
                url = card_url(card, platform, year_month)

                # 重複が出たら別テンプレで再試行（最大5回）
                text = ""
                for _ in range(5):
                    text = render_post(template, card, hashtags, url)
                    if platform == "x":
                        text = truncate_for_x(text, templates_data["_meta"]["max_length"], templates_data["_meta"]["url_length"])
                    h = text_hash(text)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        break
                    template = random.choice(templates_data["templates"])
                    hashtags = pick_hashtags(templates_data["hashtag_pool"], n=3)

                scheduled_for = f"{d.isoformat()} {slot_time}"
                posts.append({
                    "id": f"{year_month}-{day:02d}-{slot_idx}-{platform}",
                    "platform": platform,
                    "scheduled_for": scheduled_for,
                    "card_id": card["id"],
                    "text": text,
                    "posted": False,
                    "posted_at": None,
                    "post_id": None,
                })

    queue = {
        "year_month": year_month,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "site_url": SITE_URL,
        "total": len(posts),
        "posts": posts,
    }

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"[generated] {queue_path.name}: {len(posts)} posts")
    return queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", help="YYYY-MM (default: current month)")
    parser.add_argument("--dry-run", action="store_true", help="生成内容を標準出力に表示するだけ")
    parser.add_argument("--force", action="store_true", help="既存キューを上書き")
    parser.add_argument("--sample", type=int, default=6, help="--dry-run 時に表示するサンプル数")
    args = parser.parse_args()

    if args.month:
        year, month = map(int, args.month.split("-"))
    else:
        today = date.today()
        year, month = today.year, today.month

    if args.dry_run:
        # 一時的にメモリ上で生成
        random.seed(int(f"{year}{month:02d}"))
        templates_x = load_templates("x")
        templates_threads = load_templates("threads")
        print(f"=== Dry-run: {year}-{month:02d} のサンプル投稿 ===\n")
        for i in range(args.sample):
            platform = "x" if i % 2 == 0 else "threads"
            card = CARDS[i % len(CARDS)]
            t_data = templates_x if platform == "x" else templates_threads
            template = random.choice(t_data["templates"])
            hashtags = pick_hashtags(t_data["hashtag_pool"])
            url = card_url(card, platform, f"{year:04d}-{month:02d}")
            text = render_post(template, card, hashtags, url)
            if platform == "x":
                text = truncate_for_x(text)
            print(f"--- [{platform}] {card['name']} ---")
            print(text)
            print(f"(length: {len(text)})")
            print()
        return

    generate_for_month(year, month, force=args.force)


if __name__ == "__main__":
    main()
