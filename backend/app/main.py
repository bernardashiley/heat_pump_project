from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.forecast.monte_carlo import forecast_from_request
from app.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationYearResult,
    ForecastRequest,
    ForecastResponse,
)

app = FastAPI(title="Heat Pump Running-Cost Forecaster")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest) -> ForecastResponse:
    return forecast_from_request(request)


@app.post("/api/calibrate", response_model=CalibrationResponse)
def calibrate(request: CalibrationRequest) -> CalibrationResponse:
    return CalibrationResponse(
        mae_kwh=0,
        mae_gbp=0,
        coverage_80_pct=0,
        pit_bins=[0] * 10,
        per_year_results=[
            CalibrationYearResult(
                year=request.past_monthly_kwh[0].year,
                realised_kwh=0,
                p10_kwh=0,
                p50_kwh=0,
                p90_kwh=0,
                in_band=True,
            )
        ],
    )
