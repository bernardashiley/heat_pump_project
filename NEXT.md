Next: implement forecast\_from\_request in monte\_carlo.py.



This is the orchestrator that wires:

&#x20; climate.load\_or\_fetch\_climate → demand.calculate\_daily\_space\_heating\_demand

&#x20; → demand.calculate\_annual\_dhw\_demand → demand.distribute\_daily\_dhw\_demand

&#x20; → cop.fit\_eta\_from\_scop → cop.calculate\_cop\_curve

&#x20; → monte\_carlo.calculate\_daily\_electricity → calculate\_annual\_electricity\_by\_winter

&#x20; → generate\_electricity\_draws → cost.calculate\_cost\_by\_scenario

&#x20; → returns ForecastResponse.



After that: implement run\_walk\_forward\_backtest in calibrate.py (now possible

since forecast\_from\_request will exist).



After that: BUILD.md reference cases — Trip2nd fixture and Twentyman benchmark.



After that: frontend.

