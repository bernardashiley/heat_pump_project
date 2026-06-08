from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.forecast.calibrate import run_walk_forward_backtest
from app.forecast.monte_carlo import forecast_from_request
from app.models import (
    CalibrationRequest,
    CalibrationResponse,
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
    return run_walk_forward_backtest(request)
