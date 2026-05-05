"""
SNS投稿スケジューラ

GitHub Actions cron から1日3回（08:00 / 12:00 / 20:00 JST）起動される想定。
現在時刻から該当スロットを判定し、当該スロットの未投稿エントリを X / Threads に投稿する。

使い方:
    python sns/scheduler.py                    # 現在時刻から自動判定
    python sns/scheduler.py --slot morning     # スロット強制指定 (morning/noon/night)
    python sns/scheduler.py --date 2026-05-15  # 日付強制指定（テスト用）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent

# JST タイムゾーン
JST = timezone(timedelta(hours=9))

# slot 名 → スロットインデックス（generate_posts.py の DAILY_SLOTS と対応）
SLOT_INDEX = {
    "morning": 0,  # 08:00
    "noon": 1,     # 12:00
    "night": 2,    # 20:00
}

# 現在時刻 → slot 判定の境界（JST）
SLOT_BOUNDARIES = [
    (10, "morning"),  # 〜10:00 → morning
    (15, "noon"),     # 〜15:00 → noon
    (24, "night"),    # それ以降 → night
]


def detect_slot_now() -> str:
    now_jst = datetime.now(JST)
    hour = now_jst.hour
    for boundary, slot in SLOT_BOUNDARIES:
        if hour < boundary:
            return slot
    return "night"


def queue_path_for(target_date: date) -> Path:
    return SCRIPT_DIR / "queue" / f"posts_{target_date.year:04d}-{target_date.month:02d}.json"


def load_queue(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def collect_targets(target_date: date, slot: str) -> list[dict[str, Any]]:
    path = queue_path_for(target_date)
    if not path.exists():
        print(f"[warn] queue not found: {path.name}. Run generate_posts.py first.", file=sys.stderr)
        return []
    data = load_queue(path)
    slot_idx = SLOT_INDEX[slot]
    targets = []
    for p in data["posts"]:
        if p["posted"]:
            continue
        # ID 形式: YYYY-MM-DD-{slot_idx}-{platform}
        parts = p["id"].split("-")
        if len(parts) < 5:
            continue
        post_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
        post_slot = int(parts[3])
        if post_date == target_date.isoformat() and post_slot == slot_idx:
            targets.append(p)
    return targets


def run_post_script(post: dict[str, Any]) -> int:
    """post_x.py / post_threads.py を別プロセスで実行。"""
    script = "post_x.py" if post["platform"] == "x" else "post_threads.py"
    cmd = [sys.executable, str(SCRIPT_DIR / script), "--post-id", post["id"]]
    print(f"[run] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR.parent))
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=list(SLOT_INDEX.keys()), help="スロット強制指定")
    parser.add_argument("--date", help="YYYY-MM-DD で日付強制指定")
    args = parser.parse_args()

    slot = args.slot or detect_slot_now()
    target_date = date.fromisoformat(args.date) if args.date else datetime.now(JST).date()

    print(f"[scheduler] date={target_date.isoformat()} slot={slot}")

    targets = collect_targets(target_date, slot)
    if not targets:
        print("[scheduler] no targets to post")
        return

    print(f"[scheduler] {len(targets)} target(s) to post")
    failures = 0
    for post in targets:
        code = run_post_script(post)
        if code == 2:
            # rate-limited: 次回リトライ
            print(f"[scheduler] rate-limited, will retry next slot: {post['id']}")
        elif code != 0:
            failures += 1

    if failures:
        print(f"[scheduler] {failures} failure(s)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
