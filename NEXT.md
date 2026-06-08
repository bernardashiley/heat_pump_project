Backend complete. 15 commits, 79 tests, both /api/forecast and

/api/calibrate serve real responses end-to-end.



Reference cases (BUILD.md §3-4) are partially specified — BUILD.md

gives targets (Trip2nd £600-1200/yr, Twentyman 13.01 kWh/day ±15%)

but does NOT specify the input configurations. Two pieces of

out-of-band research are needed before these tests can be written:



&#x20; 1. Trip2nd: find the original Reddit thread, extract the actual

&#x20;    heat loss figure from the quote, the actual postcode (or

&#x20;    county at least), and occupants/DHW info if discussed.



&#x20; 2. Twentyman: Robert Twentyman published his 5-year measurement

&#x20;    analysis somewhere (blog, Energy Stats UK, OpenEnergyMonitor

&#x20;    forum). Find that source and pull the actual property spec:

&#x20;    floor area, HLC or design heat loss, SCOP, flow temp, occupants.



Once those two specs exist, the test code is a half-hour task:

load the fixture JSON, call forecast\_from\_request, assert against

the expected band.



After that: frontend (Next.js form, fan chart, calibration page),

then Docker compose, then ICO registration, then deploy.

