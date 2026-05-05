"""
X (Twitter) 投稿スクリプト

OAuth 1.0a User Context (Consumer Key/Secret + Access Token/Secret) を使用。
v2 エンドポイント (POST /2/tweets) で投稿する。

使い方:
    python sns/post_x.py --post-id 2026-05-15-0-x   # キューから指定IDを投稿
    python sns/post_x.py --test "テスト投稿"          # 任意テキストでテスト投稿
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import tweepy
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")


def get_client() -> tweepy.Client:
    api_key = os.environ["X_API_KEY"]
    api_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_secret = os.environ["X_ACCESS_TOKEN_SECRET"]
    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )


def post_tweet(text: str) -> dict[str, Any]:
    client = get_client()
    resp = client.create_tweet(text=text)
    return {"id": str(resp.data["id"]), "text": resp.data["text"]}


def find_queue_path(post_id: str) -> Path:
    year_month = "-".join(post_id.split("-")[:2])
    path = SCRIPT_DIR / "queue" / f"posts_{year_month}.json"
    if not path.exists():
        raise FileNotFoundError(f"queue file not found: {path}")
    return path


def load_queue(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_queue(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mark_posted(queue_path: Path, post_id: str, tweet_id: str) -> None:
    data = load_queue(queue_path)
    for p in data["posts"]:
        if p["id"] == post_id:
            p["posted"] = True
            p["posted_at"] = datetime.now().isoformat(timespec="seconds")
            p["post_id"] = tweet_id
            break
    save_queue(queue_path, data)


def post_from_queue(post_id: str) -> dict[str, Any]:
    queue_path = find_queue_path(post_id)
    data = load_queue(queue_path)
    target = next((p for p in data["posts"] if p["id"] == post_id), None)
    if not target:
        raise ValueError(f"post not found in queue: {post_id}")
    if target["posted"]:
        print(f"[skip] already posted: {post_id}")
        return {"skipped": True}
    if target["platform"] != "x":
        raise ValueError(f"post {post_id} is not for X (platform={target['platform']})")

    result = post_tweet(target["text"])
    mark_posted(queue_path, post_id, result["id"])
    print(f"[posted] {post_id} -> https://x.com/i/web/status/{result['id']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--post-id", help="キュー内のID")
    group.add_argument("--test", help="任意テキストでテスト投稿")
    args = parser.parse_args()

    try:
        if args.test:
            result = post_tweet(args.test)
            print(f"[test posted] https://x.com/i/web/status/{result['id']}")
        else:
            post_from_queue(args.post_id)
    except tweepy.TooManyRequests as e:
        print(f"[rate-limited] {e}", file=sys.stderr)
        sys.exit(2)  # exit code 2 = retry next slot
    except tweepy.TweepyException as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
