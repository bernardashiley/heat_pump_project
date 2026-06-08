from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.forecast import DhwInput, HeatPumpInput, PropertyInput, TariffScenarioInput


class PastMonthlyKwh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1900)
    month: int = Field(ge=1, le=12)
    kwh: float = Field(ge=0)


class CalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property: PropertyInput
    heat_pump: HeatPumpInput
    dhw: DhwInput
    tariff_scenarios: list[TariffScenarioInput] = Field(min_length=1)
    past_monthly_kwh: list[PastMonthlyKwh] = Field(min_length=1)


class CalibrationYearResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1900)
    realised_kwh: float = Field(ge=0)
    p10_kwh: float = Field(ge=0)
    p50_kwh: float = Field(ge=0)
    p90_kwh: float = Field(ge=0)
    in_band: bool

    @model_validator(mode="after")
    def require_ordered_percentiles(self) -> "CalibrationYearResult":
        if not self.p10_kwh <= self.p50_kwh <= self.p90_kwh:
            raise ValueError("kWh percentiles must satisfy p10_kwh <= p50_kwh <= p90_kwh.")
        return self


class CalibrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mae_kwh: float = Field(ge=0)
    mae_gbp: float = Field(ge=0)
    coverage_80_pct: float = Field(ge=0, le=1)
    pit_bins: list[float] = Field(min_length=10, max_length=10)
    per_year_results: list[CalibrationYearResult]
