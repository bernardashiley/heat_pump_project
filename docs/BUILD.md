# BUILD.md — Heat Pump Running-Cost Forecaster (Pre-Purchase MVP)

You are building a web application that takes a UK heat pump installation
quote plus a property's characteristics, and returns a probabilistic forecast
of annual running cost — a range with calibrated uncertainty, not a single
number. The user is a homeowner deciding whether to accept a heat pump quote.

The mathematical model is fully specified in `MODEL.md` in this repo. That
document is the source of truth for the maths. If anything in this prompt
appears to contradict `MODEL.md`, follow `MODEL.md` and flag the contradiction.
Read `MODEL.md` in full before writing any code.

---

## What this product is NOT

- Not a real-time monitoring app.
- Not a control system. Do not interact with the heat pump.
- Not a switching/affiliate site.
- Not a chatbot. Not an LLM wrapper. The forecast is deterministic,
  reproducible, and explainable from first principles.
- Not a price-cap forecaster. Tariffs are user inputs.
- Not a marketing site. No testimonials, badges, gamification, no streaks.

The audience is sceptical engineers and anxious homeowners. Both reward
plainness and traceability and punish flourish.

---

## Tech stack (non-negotiable)

- **Backend:** Python 3.11+, FastAPI. Statistical code in numpy/scipy/pandas.
  No ML frameworks — this is physics + Monte Carlo, not deep learning.
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind. Server
  components where possible. Recharts for charts.
- **Storage:** SQLite via SQLAlchemy. No user accounts in v1. Sessions
  identified by a UUID cookie. Data auto-deleted after 30 days by a
  scheduled job.
- **Deployment:** runs locally first via `docker compose up`. Dockerise
  both services. Do not pick a cloud-specific managed service.
- **No telemetry, no third-party analytics, no Google Fonts, no CDN
  trackers.** Privacy is a feature.

---

## Repository layout

```
heat_pump_project/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── models/              # Pydantic request/response models
│   │   ├── forecast/            # The model — implements MODEL.md
│   │   │   ├── climate.py       # Open-Meteo + postcodes.io
│   │   │   ├── demand.py        # Space heating + DHW demand
│   │   │   ├── cop.py           # Carnot-fraction COP, η fitting
│   │   │   ├── monte_carlo.py   # Weather + residual MC
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

---

## API contract

All numeric fields **must** carry unit suffixes (`_kwh`, `_gbp`, `_pct`,
`_c`, `_k`). No naked numbers. This is invariant 6 of `MODEL.md` §9.

### `POST /api/forecast`

Request:
```json
{
  "property": {
    "floor_area_m2": 95,
    "hlc_w_per_k": 180,
    "heat_loss_design_w": null,
    "t_design_outdoor_c": -2,
    "t_internal_c": 21,
    "t_base_c": 15.5,
    "postcode": "OX1 2JD"
  },
  "heat_pump": {
    "scop": 3.9,
    "t_flow_sh_c": 45,
    "t_design_outdoor_c": -2
  },
  "dhw": {
    "occupants": 3,
    "cylinder_l": 210,
    "t_setpoint_c": 48,
    "t_flow_dhw_c": 52
  },
  "tariff_scenarios": [
    { "name": "central", "standing_charge_p_per_day": 53, "unit_rate_p_per_kwh": 27 }
  ]
}
```

Response:
```json
{
  "fitted_eta": 0.48,
  "space_heating": { "p10_kwh": 2100, "p50_kwh": 2580, "p90_kwh": 3120 },
  "dhw":           { "p10_kwh":  820, "p50_kwh":  880, "p90_kwh":  940 },
  "total":         { "p10_kwh": 2950, "p50_kwh": 3460, "p90_kwh": 4020 },
  "cost_by_scenario": [
    { "name": "central", "p10_gbp": 990, "p50_gbp": 1130, "p90_gbp": 1280 }
  ],
  "monthly_breakdown_median_kwh": [/* 12 numbers */],
  "draws_kwh": [/* 1000 numbers, for the fan chart */],
  "assumptions": { /* every input echoed back, plus fitted η */ },
  "warnings": [ /* e.g. "fitted η at boundary — check SCOP vs flow temp" */ ]
}
```

### `POST /api/calibrate`

Request:
```json
{
  "property": { /* as above */ },
  "heat_pump": { /* as above */ },
  "dhw": { /* as above */ },
  "tariff_scenarios": [ /* as above */ ],
  "past_monthly_kwh": [
    { "year": 2023, "month": 1, "kwh": 920 },
    /* ... */
  ]
}
```

Response:
```json
{
  "mae_kwh": 210,
  "mae_gbp": 58,
  "coverage_80_pct": 0.83,
  "pit_bins": [0.10, 0.11, 0.09, /* 10 bins */],
  "per_year_results": [
    { "year": 2024, "realised_kwh": 3200, "p10_kwh": 2950, "p50_kwh": 3460, "p90_kwh": 4020, "in_band": true }
  ]
}
```

---

## Frontend pages

### `/` — input form
- Four collapsible sections: Property, Heat Pump, Hot Water, Tariff.
- Sensible UK defaults pre-filled (T_internal 21 °C, T_base 15.5 °C,
  T_setpoint 48 °C, three preset tariff scenarios).
- Plain typography, generous whitespace. Tailwind defaults are fine —
  don't over-design.
- On submit → call `/api/forecast` → navigate to `/result`.

### `/result` — the headline
- Big text: **"Likely annual running cost £{p10}–£{p90} (central £{p50})"**.
  Always show the range. Never show only the median.
- Below: fan chart (Recharts) from `draws_kwh`, monthly breakdown bar chart
  from `monthly_breakdown_median_kwh`.
- Then: a Space-Heating vs DHW breakdown table. This split is the
  modelling point the heat-pump community cares about most. Do not omit it.
- Then: an expandable **"How was this calculated?"** panel that prints
  the actual formulas from `MODEL.md` with the user's numbers substituted in.
- Then: a prominent CTA: **"How do I know this range is honest? Backtest
  it against my own data →"** linking to `/calibrate`.
- If `warnings` is non-empty, display them clearly above the headline.

### `/calibrate` — credibility
- CSV upload (or paste) of monthly kWh for ≥ 1 year (≥ 2 for real
  walk-forward; show a banner for N=1 explaining the limitation).
- Display **MAE**, **coverage of 80% interval**, and **PIT histogram** —
  these three figures are the product's marketing. Do not bury them.
- Per-year table with realised vs predicted band, in-band flag.

---

## Things you will be tempted to do — don't

- Don't add user accounts.
- Don't add a "share your result" feature.
- Don't fetch live tariff data. Tariffs are user inputs.
- Don't add a chatbot.
- Don't predict the price cap.
- Don't gamify. No streaks, badges, emails.
- Don't mix Celsius and Kelvin inside a single function. Convert at
  boundaries. Naming convention is your only defence: `_c` and `_k` suffixes.
- Don't smooth or round intermediate values. Keep full precision until
  the final display, then round only for rendering.
- Don't persist the postcode, address, or any free-text identifying
  input to the database. Use the postcode for the climate lookup, then
  drop it.

---

## Tests that must pass before v1 is "done"

Build `pytest` tests in `backend/tests/`. The following are required:

1. **Unit tests for every formula in `MODEL.md`**, especially the
   Kelvin-conversion boundary in the Carnot expression (§5.1).
2. **Invariants from `MODEL.md` §9** as property tests:
   - Carnot positivity (refuse `T_flow ≤ T_out`).
   - `COP ≤ COP_Carnot` always.
   - Monotonicity in outdoor temperature for fixed flow temp.
   - Cold-snap elasticity: a uniform −3 °C climate shift raises median
     annual kWh by *more* than the same shift applied with COP held
     constant. (This is the heat-pump signature.)
   - DHW electricity > 0 in every month.
   - All API response fields carry a unit suffix.
3. **Trip2nd reference case** (data in `backend/tests/fixtures/trip2nd.json`):
   64 m² 2012 new build in Yorkshire, 1.79 kW design heat loss from the quote,
   SCOP 3.9, flow 50 °C at −1.9 °C design. The central forecast lands in the
   range GBP 518.11-591.63/year at the central tariff (27 p/kWh, 53 p/day
   standing charge). The original BUILD.md spec guessed GBP 600-1200/year; the
   real model output is lower because the property has a very low 1.79 kW
   design heat loss for a 64 m² 2012 new build. Trip2nd has no realised running
   cost reported — only the installer's quote and property specs. The expected
   band is therefore the model's own p10-p90 predictive distribution, making
   this test a regression anchor (catches model drift) rather than an empirical
   validation. Twentyman remains the empirical anchor with real measured
   electricity.
4. **Twentyman benchmark:** a property configured to match Robert
   Twentyman's published 5-year measured average of 13.01 kWh/day. The
   central forecast must land within ±15% of that figure on an annual
   basis. (Fixture: `backend/tests/fixtures/twentyman.json`.)
5. **GDPR test:** run a full request, then query the SQLite file directly
   and assert no row contains the submitted postcode string. Only the
   session UUID and numeric inputs may persist.
6. **30-day cleanup:** the scheduled cleanup deletes session rows older
   than 30 days. Use a frozen-clock fixture.

Tests run on `pytest` in the backend container. CI is out of scope for
v1 — running `pytest` locally is enough.

---

## What "v1 done" looks like

- `docker compose up` brings up backend (`:8000`) and frontend (`:3000`).
- Submitting the form returns a forecast in under 3 seconds for 1000 MC draws.
- The Trip2nd fixture produces a sane range; the Twentyman fixture passes
  the ±15% check.
- The calibration page renders a real PIT histogram from real past data.
- `MODEL.md` and the code agree.
- A stats reviewer can read the `backend/app/forecast/` directory and
  verify the formulas against `MODEL.md` inside 30 minutes.

If any of the above is not true, v1 is not done. Don't ship marketing
polish on top of a broken model.
