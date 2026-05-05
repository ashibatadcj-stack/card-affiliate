"""
Threads 投稿スクリプト

Meta Graph API (graph.threads.net) を使う2段階投稿:
  1. POST /{user-id}/threads      → media container 作成
  2. POST /{user-id}/threads_publish → 公開

使い方:
    python sns/post_threads.py --post-id 2026-05-15-0-threads
    python sns/post_threads.py --test "テスト投稿"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

GRAPH_BASE = "https://graph.threads.net/v1.0"


def get_credentials() -> tuple[str, str]:
    user_id = os.environ["THREADS_USER_ID"]
    token = os.environ["THREADS_ACCESS_TOKEN"]
    return user_id, token


def create_container(user_id: str, token: str, text: str) -> str:
    url = f"{GRAPH_BASE}/{user_id}/threads"
    resp = requests.post(
        url,
        data={"media_type": "TEXT", "text": text, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_container(user_id: str, token: str, container_id: str) -> str:
    # 公開前に短い待機（Meta推奨: container 作成直後はまだ準備中の場合がある）
    time.sleep(2)
    url = f"{GRAPH_BASE}/{user_id}/threads_publish"
    resp = requests.post(
        url,
        data={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_thread(text: str) -> dict[str, Any]:
    user_id, token = get_credentials()
    container_id = create_container(user_id, token, text)
    media_id = publish_container(user_id, token, container_id)
    return {"id": media_id, "container_id": container_id}


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


def mark_posted(queue_path: Path, post_id: str, media_id: str) -> None:
    data = load_queue(queue_path)
    for p in data["posts"]:
        if p["id"] == post_id:
            p["posted"] = True
            p["posted_at"] = datetime.now().isoformat(timespec="seconds")
            p["post_id"] = media_id
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
    if target["platform"] != "threads":
        raise ValueError(f"post {post_id} is not for Threads (platform={target['platform']})")

    result = post_thread(target["text"])
    mark_posted(queue_path, post_id, result["id"])
    print(f"[posted] {post_id} -> threads media id: {result['id']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--post-id", help="キュー内のID")
    group.add_argument("--test", help="任意テキストでテスト投稿")
    args = parser.parse_args()

    try:
        if args.test:
            result = post_thread(args.test)
            print(f"[test posted] media id: {result['id']}")
        else:
            post_from_queue(args.post_id)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text if e.response is not None else ""
        print(f"[error {status}] {body}", file=sys.stderr)
        # 429 (rate limit) は次回リトライ
        sys.exit(2 if status == 429 else 1)
    except requests.RequestException as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
