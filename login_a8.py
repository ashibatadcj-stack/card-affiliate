"""
A8.net 初回ログインスクリプト
このスクリプトをターミナルで直接実行してください：
  python login_a8.py
ブラウザが開くのでA8.netにログインしてEnterを押すとセッションが保存されます。
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / ".a8_session.json"


def main():
    print("=" * 50)
    print("A8.net ログインセッション保存ツール")
    print("=" * 50)
    print("\nブラウザが開きます。A8.netにログインしてください。")
    print("ログイン完了後、このターミナルに戻ってEnterを押してください。\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.a8.net/a8v2/login.html")

        input(">>> ログインが完了したらEnterを押してください: ")

        session_data = context.storage_state()
        SESSION_FILE.write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        browser.close()

    print(f"\nセッションを保存しました: {SESSION_FILE}")
    print("次回から auto_discover_pw.py が自動実行できます。")


if __name__ == "__main__":
    main()
