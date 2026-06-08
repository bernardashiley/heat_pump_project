\# BUILD.md — Heat Pump Running-Cost Forecaster (Pre-Purchase MVP)



You are building a web application that takes a UK heat pump installation

quote plus a property's characteristics, and returns a probabilistic forecast

of annual running cost — a range with calibrated uncertainty, not a single

number. The user is a homeowner deciding whether to accept a heat pump quote.



The mathematical model is fully specified in `MODEL.md` in this repo. That

document is the source of truth for the maths. If anything in this prompt

appears to contradict `MODEL.md`, follow `MODEL.md` and flag the contradiction.

Read `MODEL.md` in full before writing any code.



\---



\## What this product is NOT



\- Not a real-time monitoring app.

\- Not a control system. Do not interact with the heat pump.

\- Not a switching/affiliate site.

\- Not a chatbot. Not an LLM wrapper. The forecast is deterministic,

&#x20; reproducible, and explainable from first principles.

\- Not a price-cap forecaster. Tariffs are user inputs.

\- Not a marketing site. No testimonials, badges, gamification, no streaks.



The audience is sceptical engineers and anxious homeowners. Both reward

plainness and traceability and punish flourish.



\---



\## Tech stack (non-negotiable)



\- \*\*Backend:\*\* Python 3.11+, FastAPI. Statistical code in numpy/scipy/pandas.

&#x20; No ML frameworks — this is physics + Monte Carlo, not deep learning.

\- \*\*Frontend:\*\* Next.js 14 (App Router), TypeScript, Tailwind. Server

&#x20; components where possible. Recharts for charts.

\- \*\*Storage:\*\* SQLite via SQLAlchemy. No user accounts in v1. Sessions

&#x20; identified by a UUID cookie. Data auto-deleted after 30 days by a

&#x20; scheduled job.

\- \*\*Deployment:\*\* runs locally first via `docker compose up`. Dockerise

&#x20; both services. Do not pick a cloud-specific managed service.

\- \*\*No telemetry, no third-party analytics, no Google Fonts, no CDN

&#x20; trackers.\*\* Privacy is a feature.



\---



\## Repository layout



```

heat\_pump\_project/

├── backend/

│   ├── app/

│   │   ├── \_\_init\_\_.py

│   │   ├── main.py              # FastAPI app

│   │   ├── models/              # Pydantic request/response models

│   │   ├── forecast/            # The model — implements MODEL.md

│   │   │   ├── climate.py       # Open-Meteo + postcodes.io

│   │   │   ├── demand.py        # Space heating + DHW demand

│   │   │   ├── cop.py           # Carnot-fraction COP, η fitting

│   │   │   ├── monte\_carlo.py   # Weather + residual MC

│   │   │   ├── cost.py          # Tariff application

│   │   │   └── calibrate.py     # Walk-forward, MAE, coverage, PIT

│   │   ├── db.py                # SQLAlchemy + 30-day cleanup

│   │   └── settings.py

│   ├── tests/                   # pytest — see "Tests that must pass"

│   ├── pyproject.toml

│   └── Dockerfile

├── frontend/

│   ├── app/                     # Next.js App Router pages

│   │   ├── page.tsx             # Single-page input form

│   │   ├── result/page.tsx      # Headline + fan chart + breakdown

│   │   └── calibrate/page.tsx   # Backtest your own data

│   ├── components/

│   ├── lib/api.ts               # Typed API client

│   ├── package.json

│   └── Dockerfile

├── docs/

│   ├── MODEL.md                 # Source of truth for the maths

│   └── BUILD.md                 # This file

├── data/cache/                  # Climate cache, gitignored

├── docker-compose.yml

├── .gitignore

└── README.md

```



\---



\## API contract



All numeric fields \*\*must\*\* carry unit suffixes (`\_kwh`, `\_gbp`, `\_pct`,

`\_c`, `\_k`). No naked numbers. This is invariant 6 of `MODEL.md` §9.



\### `POST /api/forecast`



Request:

```json

{

&#x20; "property": {

&#x20;   "floor\_area\_m2": 95,

&#x20;   "hlc\_w\_per\_k": 180,

&#x20;   "heat\_loss\_design\_w": null,

&#x20;   "t\_design\_outdoor\_c": -2,

&#x20;   "t\_internal\_c": 21,

&#x20;   "t\_base\_c": 15.5,

&#x20;   "postcode": "OX1 2JD"

&#x20; },

&#x20; "heat\_pump": {

&#x20;   "scop": 3.9,

&#x20;   "t\_flow\_sh\_c": 45,

&#x20;   "t\_design\_outdoor\_c": -2

&#x20; },

&#x20; "dhw": {

&#x20;   "occupants": 3,

&#x20;   "cylinder\_l": 210,

&#x20;   "t\_setpoint\_c": 48,

&#x20;   "t\_flow\_dhw\_c": 52

&#x20; },

&#x20; "tariff\_scenarios": \[

&#x20;   { "name": "central", "standing\_charge\_p\_per\_day": 53, "unit\_rate\_p\_per\_kwh": 27 }

&#x20; ]

}

```



Response:

```json

{

&#x20; "fitted\_eta": 0.48,

&#x20; "space\_heating": { "p10\_kwh": 2100, "p50\_kwh": 2580, "p90\_kwh": 3120 },

&#x20; "dhw":           { "p10\_kwh":  820, "p50\_kwh":  880, "p90\_kwh":  940 },

&#x20; "total":         { "p10\_kwh": 2950, "p50\_kwh": 3460, "p90\_kwh": 4020 },

&#x20; "cost\_by\_scenario": \[

&#x20;   { "name": "central", "p10\_gbp": 990, "p50\_gbp": 1130, "p90\_gbp": 1280 }

&#x20; ],

&#x20; "monthly\_breakdown\_median\_kwh": \[/\* 12 numbers \*/],

&#x20; "draws\_kwh": \[/\* 1000 numbers, for the fan chart \*/],

&#x20; "assumptions": { /\* every input echoed back, plus fitted η \*/ },

&#x20; "warnings": \[ /\* e.g. "fitted η at boundary — check SCOP vs flow temp" \*/ ]

}

```



\### `POST /api/calibrate`



Request:

```json

{

&#x20; "property": { /\* as above \*/ },

&#x20; "heat\_pump": { /\* as above \*/ },

&#x20; "dhw": { /\* as above \*/ },

&#x20; "tariff\_scenarios": \[ /\* as above \*/ ],

&#x20; "past\_monthly\_kwh": \[

&#x20;   { "year": 2023, "month": 1, "kwh": 920 },

&#x20;   /\* ... \*/

&#x20; ]

}

```



Response:

```json

{

&#x20; "mae\_kwh": 210,

&#x20; "mae\_gbp": 58,

&#x20; "coverage\_80\_pct": 0.83,

&#x20; "pit\_bins": \[0.10, 0.11, 0.09, /\* 10 bins \*/],

&#x20; "per\_year\_results": \[

&#x20;   { "year": 2024, "realised\_kwh": 3200, "p10\_kwh": 2950, "p50\_kwh": 3460, "p90\_kwh": 4020, "in\_band": true }

&#x20; ]

}

```



\---



\## Frontend pages



\### `/` — input form

\- Four collapsible sections: Property, Heat Pump, Hot Water, Tariff.

\- Sensible UK defaults pre-filled (T\_internal 21 °C, T\_base 15.5 °C,

&#x20; T\_setpoint 48 °C, three preset tariff scenarios).

\- Plain typography, generous whitespace. Tailwind defaults are fine —

&#x20; don't over-design.

\- On submit → call `/api/forecast` → navigate to `/result`.



\### `/result` — the headline

\- Big text: \*\*"Likely annual running cost £{p10}–£{p90} (central £{p50})"\*\*.

&#x20; Always show the range. Never show only the median.

\- Below: fan chart (Recharts) from `draws\_kwh`, monthly breakdown bar chart

&#x20; from `monthly\_breakdown\_median\_kwh`.

\- Then: a Space-Heating vs DHW breakdown table. This split is the

&#x20; modelling point the heat-pump community cares about most. Do not omit it.

\- Then: an expandable \*\*"How was this calculated?"\*\* panel that prints

&#x20; the actual formulas from `MODEL.md` with the user's numbers substituted in.

\- Then: a prominent CTA: \*\*"How do I know this range is honest? Backtest

&#x20; it against my own data →"\*\* linking to `/calibrate`.

\- If `warnings` is non-empty, display them clearly above the headline.



\### `/calibrate` — credibility

\- CSV upload (or paste) of monthly kWh for ≥ 1 year (≥ 2 for real

&#x20; walk-forward; show a banner for N=1 explaining the limitation).

\- Display \*\*MAE\*\*, \*\*coverage of 80% interval\*\*, and \*\*PIT histogram\*\* —

&#x20; these three figures are the product's marketing. Do not bury them.

\- Per-year table with realised vs predicted band, in-band flag.



\---



\## Things you will be tempted to do — don't



\- Don't add user accounts.

\- Don't add a "share your result" feature.

\- Don't fetch live tariff data. Tariffs are user inputs.

\- Don't add a chatbot.

\- Don't predict the price cap.

\- Don't gamify. No streaks, badges, emails.

\- Don't mix Celsius and Kelvin inside a single function. Convert at

&#x20; boundaries. Naming convention is your only defence: `\_c` and `\_k` suffixes.

\- Don't smooth or round intermediate values. Keep full precision until

&#x20; the final display, then round only for rendering.

\- Don't persist the postcode, address, or any free-text identifying

&#x20; input to the database. Use the postcode for the climate lookup, then

&#x20; drop it.



\---



\## Tests that must pass before v1 is "done"



Build `pytest` tests in `backend/tests/`. The following are required:



1\. \*\*Unit tests for every formula in `MODEL.md`\*\*, especially the

&#x20;  Kelvin-conversion boundary in the Carnot expression (§5.1).

2\. \*\*Invariants from `MODEL.md` §9\*\* as property tests:

&#x20;  - Carnot positivity (refuse `T\_flow ≤ T\_out`).

&#x20;  - `COP ≤ COP\_Carnot` always.

&#x20;  - Monotonicity in outdoor temperature for fixed flow temp.

&#x20;  - Cold-snap elasticity: a uniform −3 °C climate shift raises median

&#x20;    annual kWh by \*more\* than the same shift applied with COP held

&#x20;    constant. (This is the heat-pump signature.)

&#x20;  - DHW electricity > 0 in every month.

&#x20;  - All API response fields carry a unit suffix.

3\. \*\*Trip2nd reference case\*\* (data in `backend/tests/fixtures/trip2nd.json`):

&#x20;  \~64 m² 2012 new build in southern England, derived HLC from the quote,

&#x20;  SCOP 3.9, flow 50 °C at −1.9 °C design. The central forecast must land

&#x20;  within a plausible band (£600–£1200/year at central tariff). If it

&#x20;  doesn't, the model is wrong; fail loudly.

4\. \*\*Twentyman benchmark:\*\* a property configured to match Robert

&#x20;  Twentyman's published 5-year measured average of 13.01 kWh/day. The

&#x20;  central forecast must land within ±15% of that figure on an annual

&#x20;  basis. (Fixture: `backend/tests/fixtures/twentyman.json`.)

5\. \*\*GDPR test:\*\* run a full request, then query the SQLite file directly

&#x20;  and assert no row contains the submitted postcode string. Only the

&#x20;  session UUID and numeric inputs may persist.

6\. \*\*30-day cleanup:\*\* the scheduled cleanup deletes session rows older

&#x20;  than 30 days. Use a frozen-clock fixture.



Tests run on `pytest` in the backend container. CI is out of scope for

v1 — running `pytest` locally is enough.



\---



\## What "v1 done" looks like



\- `docker compose up` brings up backend (`:8000`) and frontend (`:3000`).

\- Submitting the form returns a forecast in under 3 seconds for 1000 MC draws.

\- The Trip2nd fixture produces a sane range; the Twentyman fixture passes

&#x20; the ±15% check.

\- The calibration page renders a real PIT histogram from real past data.

\- `MODEL.md` and the code agree.

\- A stats reviewer can read the `backend/app/forecast/` directory and

&#x20; verify the formulas against `MODEL.md` inside 30 minutes.



If any of the above is not true, v1 is not done. Don't ship marketing

polish on top of a broken model.

