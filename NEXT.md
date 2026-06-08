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





v2 modelling backlog (deferred pending reference cases):



\- Humidity-conditional defrost penalty per Zhu et al. 2015 frosting

&#x20; map. Requires (a) Open-Meteo humidity field in climate.py cache,

&#x20; (b) frosting-zone severity model, (c) reference cases across UK

&#x20; humidity bands to constrain parameters. Identifiability constraint:

&#x20; do not add this until N >= 10 reference cases exist.



\- Flow-temperature/defrost coupling. Higher flow temp → more frost.

&#x20; Currently absorbed into η. v2 could split this for more accurate

&#x20; monthly breakdown at high flow temperatures.



\- SCOP-constraint interaction. The defrost penalty currently

&#x20; redistributes electricity across temperature bins but doesn't change

&#x20; the annual total (SCOP is fixed). When reference cases arrive, check

&#x20; whether measured annual totals match SCOP-constrained predictions

&#x20; or whether real SCOP figures systematically over/under-state energy.

&#x20; This would tell us whether to relax the SCOP constraint.



\- Defrost penalty's biggest practical effect is on units where η

&#x20; clamps at ETA\_MAX (very high SCOP). User-facing copy should explain

&#x20; when the eta-boundary warning means the defrost penalty is

&#x20; materially affecting the forecast.

