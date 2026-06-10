# Heat Pump Running-Cost Forecaster

A probabilistic forecasting model for UK domestic heat pump annual running costs, with a pre-registered calibration evaluation against the HeatpumpMonitor.org open dataset.

This repository contains the model code, the pre-registered calibration methodology, the dataset snapshot, the climate cache, the evaluation scripts, and the v1 calibration report.

## Status

The v1 model failed its pre-registered validation. The calibration evaluation identified a structural defect in the demand-period definition: the v1 model simulates October-March only and reports the result as annual electricity. The defect is documented in detail in the v1 calibration report. A v1.1 ablation evaluation with the demand-period fix and two other planned improvements is in progress.

Read first:

- **[docs/CALIBRATION_REPORT_V1.md](docs/CALIBRATION_REPORT_V1.md)** - the v1 calibration report.
- **[docs/CALIBRATION_METHODOLOGY.md](docs/CALIBRATION_METHODOLOGY.md)** - the pre-registered methodology.
- **[docs/V1_DIAGNOSTIC_FINDINGS.md](docs/V1_DIAGNOSTIC_FINDINGS.md)** - the diagnostic memo supporting the v1 report's sections 7 and 8.

## Repository structure

```text
.
├── backend/
│   ├── app/forecast/         # Model code: climate, demand, cop, monte_carlo, cost
│   ├── scripts/              # Data fetch, build, prefetch, evaluation
│   ├── tests/                # 91 unit tests covering forecast components
│   └── pyproject.toml        # Pinned dependencies
├── data/heatpumpmonitor/     # Frozen dataset snapshot and climate cache
├── docs/
│   ├── CALIBRATION_REPORT_V1.md
│   ├── CALIBRATION_METHODOLOGY.md
│   └── V1_DIAGNOSTIC_FINDINGS.md
└── README.md
```

## Reproducing the v1 calibration evaluation

The v1 evaluation runs from the frozen dataset snapshot dated 2026-06-09. The model code commit hash at evaluation time is recorded in the v1 calibration report.

Set up Python dependencies (Python 3.12+ assumed; the project's lock file uses a virtual environment at `backend/.venv/`):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Run the evaluation from the frozen snapshot:

```powershell
.venv\Scripts\python.exe scripts\build_eval_dataset.py --use-frozen-snapshot --snapshot-date 20260609
.venv\Scripts\python.exe scripts\prefetch_climate_cache.py
.venv\Scripts\python.exe scripts\run_calibration_eval.py
```

Wall-clock time is approximately 4-5 minutes from a populated cache. Outputs are written to `data/heatpumpmonitor/`.

## Authorship and citation

This work is authored by Bernard Ashiley and published under Odwira & Whitehall.

Correspondence: bernardashiley@gmail.com

The v1 calibration report may be cited as:

> Ashiley, B. (2026). *Calibration of a Probabilistic UK Heat Pump Running-Cost Forecaster v1: A Pre-Registered Evaluation Against HeatpumpMonitor.org.* Odwira & Whitehall technical report. SSRN: [identifier pending].

## Licence

The report prose under `docs/` is published under Creative Commons Attribution 4.0 International (CC BY 4.0). The code (in `backend/`) is published under the MIT Licence. See `LICENSE` for the code licence and `LICENSE-DOCS` for the prose licence.
