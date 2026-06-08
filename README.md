\# Heat Pump Running-Cost Forecaster



An independent, probabilistic forecasting tool for UK heat pump running

costs. Takes a quote and a property's characteristics, returns a calibrated

range — not a single number.



The differentiator is honesty. Every existing tool returns one confident

figure; this one returns a distribution and shows its working.



\## Status



Pre-MVP. Specification stage.



\## Documents



\- `docs/MODEL.md` — the mathematical model. Source of truth for the maths.

\- `docs/BUILD.md` — the build specification. Source of truth for everything

&#x20; else (stack, API, tests, what to build and what not to build).



Read both before contributing code.



\## Stack



\- Backend: Python 3.11+, FastAPI, numpy/scipy/pandas

\- Frontend: Next.js 14, TypeScript, Tailwind, Recharts

\- Storage: SQLite (sessions only, 30-day auto-delete)

\- Deployment: Docker Compose



\## Running locally



Once the code exists:



```

docker compose up

```



Backend on `:8000`, frontend on `:3000`.



\## Tests



```

cd backend

pytest

```



The test suite enforces the invariants in `MODEL.md §9` and the

reference cases (Trip2nd quote, Twentyman benchmark) before v1 is

considered done.



\## Licence



TBD.

