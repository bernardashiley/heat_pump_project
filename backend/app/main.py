from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    Assumptions,
    CalibrationRequest,
    CalibrationResponse,
    CalibrationYearResult,
    CostScenarioPercentiles,
    ForecastRequest,
    ForecastResponse,
    KwhPercentiles,
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
    zero_kwh_percentiles = KwhPercentiles(p10_kwh=0, p50_kwh=0, p90_kwh=0)

    return ForecastResponse(
        fitted_eta=0,
        space_heating=zero_kwh_percentiles,
        dhw=zero_kwh_percentiles,
        total=zero_kwh_percentiles,
        cost_by_scenario=[
            CostScenarioPercentiles(
                name=scenario.name,
                p10_gbp=0,
                p50_gbp=0,
                p90_gbp=0,
            )
            for scenario in request.tariff_scenarios
        ],
        monthly_breakdown_median_kwh=[0] * 12,
        draws_kwh=[0] * 1000,
        assumptions=Assumptions(
            property=request.property,
            heat_pump=request.heat_pump,
            dhw=request.dhw,
            tariff_scenarios=request.tariff_scenarios,
            fitted_eta=0,
        ),
        warnings=[],
    )


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
