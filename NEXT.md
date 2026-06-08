Backend complete. /api/forecast serves real calibrated forecasts.

13 commits, 76 tests passing.



Remaining work, in order:



1\. Wire run\_walk\_forward\_backtest in calibrate.py to call

&#x20;  forecast\_from\_request iteratively (now possible since orchestrator exists).

&#x20;  Then wire /api/calibrate in main.py to call it.



2\. BUILD.md reference cases — Trip2nd fixture and Twentyman benchmark.

&#x20;  These run real-world data through the engine and assert sanity.

&#x20;  This is the moment the engine stops being code and starts being a tool.



3\. Frontend: Next.js form, fan chart, calibration page.



4\. Docker compose, deployment.



5\. NEXT.md retired — project moves to GitHub issues.

