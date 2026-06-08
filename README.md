# Heat Pump Running-Cost Forecaster



An independent, probabilistic forecasting tool for UK heat pump running

costs. Takes a quote and a property's characteristics, returns a calibrated

range — not a single number.



The differentiator is honesty. Every existing tool returns one confident

figure; this one returns a distribution and shows its working.



## Status



Pre-MVP. Specification stage.



## Documents



- `docs/MODEL.md` — the mathematical model. Source of truth for the maths.

- `docs/BUILD.md` — the build specification. Source of truth for everything

  else (stack, API, tests, what to build and what not to build).



Read both before contributing code.



## Stack



- Backend: Python 3.11+, FastAPI, numpy/scipy/pandas

- Frontend: Next.js 14, TypeScript, Tailwind, Recharts

- Storage: SQLite (sessions only, 30-day auto-delete)

- Deployment: Docker Compose

## Local development

Requires Python 3.12.

Create the backend virtual environment:

```powershell
py -3.12 -m venv backend\.venv
```

Install the backend package:

```powershell
backend\.venv\Scripts\python.exe -m pip install -e backend
```

Run the backend server:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

The backend health check is available at `http://127.0.0.1:8000/healthz`.

## Running with Docker

```powershell
docker compose up
```

Backend on `:8000`, frontend on `:3000`.



## Tests



```

cd backend

pytest

```



The test suite enforces the invariants in `MODEL.md §9` and the

reference cases (Trip2nd quote, Twentyman benchmark) before v1 is

considered done.



## Licence



TBD.

