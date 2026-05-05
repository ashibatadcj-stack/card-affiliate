@echo off
REM ==============================================================
REM  Daily Full Automation - Windows Task Scheduler entry point
REM ==============================================================
REM  Steps:
REM   1. Fetch GA4 + Search Console data (28 days)
REM   2. Generate report + update history CSV
REM   3. Generate action plan via Claude API
REM   4. Save analytics/output/daily-YYYY-MM-DD.md and latest.md
REM   5. Submit URLs to Google Indexing API
REM   6. Submit URLs to IndexNow (Bing/Yandex)
REM
REM  Log: analytics/output/cycle.log
REM ==============================================================

setlocal
set PYTHONIOENCODING=utf-8

REM Move to project root (one level above this bat file)
cd /d "%~dp0\.."

REM ---- Step 1-4: Daily analytics cycle ----
echo [%DATE% %TIME%] === Step 1-4: analytics/daily_cycle.py === >> analytics\output\cycle.log
python analytics\daily_cycle.py --days 28 --quiet
set CYCLE_EXIT=%ERRORLEVEL%
echo [%DATE% %TIME%] daily_cycle.py exit=%CYCLE_EXIT% >> analytics\output\cycle.log

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

echo [%DATE% %TIME%] === DAILY RUN COMPLETE: cycle=%CYCLE_EXIT% indexing=%IDX_EXIT% indexnow=%NOW_EXIT% === >> analytics\output\cycle.log

endlocal & exit /b %CYCLE_EXIT%
