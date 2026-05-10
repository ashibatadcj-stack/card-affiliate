@echo off
REM ==============================================================
REM  Daily Full Automation - Windows Task Scheduler entry point
REM ==============================================================
REM  Steps:
REM   1. Fetch GA4 + Search Console data (28 days)
REM   2. Generate report + update history CSV
REM   3. Generate action plan via Claude API
REM   4. Save analytics/output/daily-YYYY-MM-DD.md and latest.md
REM   4.5. URL Inspection (index status check)
REM   5. Submit URLs to Google Indexing API
REM   6. Submit URLs to IndexNow (Bing/Yandex)
REM   7. Slack notification
REM   8. Auto-implement actions via local Claude Code
REM   9. Effect tracker (weekly summary on Saturdays)
REM
REM  Logs:
REM   - analytics/output/task_trigger.log : bat 起動マーカー（トラブル切り分け用）
REM   - analytics/output/cycle.log         : 各ステップ実行ログ
REM ==============================================================

REM ★最優先: bat が起動したマーカーを残す（権限・PATH問題があれば即座に判明）
REM 注意: %DATE% %TIME% は日本語ロケールで "(日)" 等の括弧が含まれるため、
REM     echo の引数全体を "..." で囲んで解析エラーを防ぐ
echo "[%DATE% %TIME%] TASK_TRIGGERED dir=%~dp0" >> "%~dp0output\task_trigger.log" 2>&1

setlocal
set PYTHONIOENCODING=utf-8

REM Move to project root (one level above this bat file)
cd /d "%~dp0\.."

REM 起動環境の診断情報を1度だけログに出す（ダブルクオートで括弧問題を回避）
echo "[%DATE% %TIME%] BAT_STARTED cwd=%CD%" >> "analytics\output\task_trigger.log" 2>&1
where python >> "analytics\output\task_trigger.log" 2>&1

REM ---- Step 1-4: Daily analytics cycle ----
echo [%DATE% %TIME%] === Step 1-4: analytics/daily_cycle.py === >> analytics\output\cycle.log
python analytics\daily_cycle.py --days 28 --quiet
set CYCLE_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] daily_cycle.py exit=%CYCLE_EXIT% >> analytics\output\cycle.log

REM ---- Step 4.5: GSC URL Inspection（インデックス状況の取得・未登録URLリストアップ） ----
echo [%DATE% %TIME%] === Step 4.5: check_index_status.py === >> analytics\output\cycle.log
python analytics\check_index_status.py --quiet >> analytics\output\cycle.log 2>&1
set IDX_CHECK_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] check_index_status.py exit=%IDX_CHECK_EXIT% >> analytics\output\cycle.log

REM ---- Step 5: Google Indexing API ----
echo [%DATE% %TIME%] === Step 5: submit_google_indexing.py === >> analytics\output\cycle.log
python submit_google_indexing.py >> analytics\output\cycle.log 2>&1
set IDX_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] submit_google_indexing.py exit=%IDX_EXIT% >> analytics\output\cycle.log

REM ---- Step 6: IndexNow (Bing/Yandex/Seznam) ----
echo [%DATE% %TIME%] === Step 6: submit_indexnow.py === >> analytics\output\cycle.log
python submit_indexnow.py >> analytics\output\cycle.log 2>&1
set NOW_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] submit_indexnow.py exit=%NOW_EXIT% >> analytics\output\cycle.log

REM ---- Step 7: Slack 通知（日次レポート） ----
echo [%DATE% %TIME%] === Step 7: notify_slack.py === >> analytics\output\cycle.log
python analytics\notify_slack.py >> analytics\output\cycle.log 2>&1
set SLACK_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] notify_slack.py exit=%SLACK_EXIT% >> analytics\output\cycle.log

REM ---- Step 8: ローカル Claude Code でアクション自動実装（API課金なし） ----
echo [%DATE% %TIME%] === Step 8: auto_action_local.py === >> analytics\output\cycle.log
python analytics\auto_action_local.py >> analytics\output\cycle.log 2>&1
set AUTO_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] auto_action_local.py exit=%AUTO_EXIT% >> analytics\output\cycle.log

REM ---- Step 9: 効果測定・ブラックリスト学習・週次サマリー（土曜にSlack通知） ----
echo [%DATE% %TIME%] === Step 9: effect_tracker.py === >> analytics\output\cycle.log
python analytics\effect_tracker.py --quiet >> analytics\output\cycle.log 2>&1
set EFFECT_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] effect_tracker.py exit=%EFFECT_EXIT% >> analytics\output\cycle.log

echo [%DATE% %TIME%] === DAILY RUN COMPLETE: cycle=%CYCLE_EXIT% indexing=%IDX_EXIT% indexnow=%NOW_EXIT% slack=%SLACK_EXIT% auto=%AUTO_EXIT% === >> analytics\output\cycle.log

endlocal & exit /b %CYCLE_EXIT%
