Next: implement calibrate.py per MODEL.md §8.

\- aggregate\_monthly\_kwh: monthly CSV → annual DataFrame

\- calculate\_pit\_value: empirical CDF rank of realised in draws

\- calculate\_calibration\_metrics: MAE, 80% coverage, PIT histogram (10 bins)

\- run\_walk\_forward\_backtest: orchestrator over years



Then: implement forecast\_from\_request in monte\_carlo.py — wires climate → demand → cop → monte\_carlo → cost into a full ForecastResponse. This is the function that turns the API stub into a real working endpoint.



After that: the Trip2nd and Twentyman reference-case tests from BUILD.md.

