from pydantic import BaseModel, ConfigDict, Field, model_validator


class PropertyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor_area_m2: float = Field(gt=0)
    hlc_w_per_k: float | None = Field(default=None, gt=0)
    heat_loss_design_w: float | None = Field(default=None, gt=0)
    t_design_outdoor_c: float
    t_internal_c: float = Field(default=21)
    t_base_c: float = Field(default=15.5)
    postcode: str = Field(min_length=5, max_length=10)

    @model_validator(mode="after")
    def require_hlc_or_design_heat_loss(self) -> "PropertyInput":
        if self.hlc_w_per_k is None and self.heat_loss_design_w is None:
            raise ValueError("Either hlc_w_per_k or heat_loss_design_w is required.")
        if self.t_internal_c <= self.t_design_outdoor_c:
            raise ValueError("t_internal_c must be greater than t_design_outdoor_c.")
        return self


class HeatPumpInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scop: float = Field(gt=0)
    t_flow_sh_c: float
    t_design_outdoor_c: float

    @model_validator(mode="after")
    def require_flow_above_design_outdoor(self) -> "HeatPumpInput":
        if self.t_flow_sh_c <= self.t_design_outdoor_c:
            raise ValueError("t_flow_sh_c must be greater than t_design_outdoor_c.")
        return self


class DhwInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occupants: int = Field(ge=1)
    cylinder_l: float = Field(gt=0)
    t_setpoint_c: float = Field(default=48)
    t_flow_dhw_c: float = Field(default=52)

    @model_validator(mode="after")
    def require_flow_at_or_above_setpoint(self) -> "DhwInput":
        if self.t_flow_dhw_c < self.t_setpoint_c:
            raise ValueError("t_flow_dhw_c must be at least t_setpoint_c.")
        return self


class TariffScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    standing_charge_p_per_day: float = Field(ge=0)
    unit_rate_p_per_kwh: float = Field(ge=0)


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property: PropertyInput
    heat_pump: HeatPumpInput
    dhw: DhwInput
    tariff_scenarios: list[TariffScenarioInput] = Field(min_length=1)


class KwhPercentiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10_kwh: float = Field(ge=0)
    p50_kwh: float = Field(ge=0)
    p90_kwh: float = Field(ge=0)

    @model_validator(mode="after")
    def require_ordered_percentiles(self) -> "KwhPercentiles":
        if not self.p10_kwh <= self.p50_kwh <= self.p90_kwh:
            raise ValueError("kWh percentiles must satisfy p10_kwh <= p50_kwh <= p90_kwh.")
        return self


class CostScenarioPercentiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    p10_gbp: float = Field(ge=0)
    p50_gbp: float = Field(ge=0)
    p90_gbp: float = Field(ge=0)

    @model_validator(mode="after")
    def require_ordered_percentiles(self) -> "CostScenarioPercentiles":
        if not self.p10_gbp <= self.p50_gbp <= self.p90_gbp:
            raise ValueError("GBP percentiles must satisfy p10_gbp <= p50_gbp <= p90_gbp.")
        return self


class Assumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property: PropertyInput
    heat_pump: HeatPumpInput
    dhw: DhwInput
    tariff_scenarios: list[TariffScenarioInput] = Field(min_length=1)
    fitted_eta: float = Field(ge=0)


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fitted_eta: float = Field(ge=0)
    space_heating: KwhPercentiles
    dhw: KwhPercentiles
    total: KwhPercentiles
    cost_by_scenario: list[CostScenarioPercentiles] = Field(min_length=1)
    monthly_breakdown_median_kwh: list[float] = Field(min_length=12, max_length=12)
    draws_kwh: list[float] = Field(min_length=1000, max_length=1000)
    assumptions: Assumptions
    warnings: list[str] = Field(default_factory=list)
