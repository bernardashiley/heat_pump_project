import numpy as np

from app.models import DhwInput, PropertyInput

LITRES_PER_PERSON_PER_DAY = 50
WATER_SPECIFIC_HEAT_KJ_PER_KG_K = 4.186
KJ_PER_KWH = 3600


def _cold_inlet_c(day_of_year: int) -> float:
    """Return seasonal cold-water inlet temperature for a non-leap-year day.

    Implements MODEL.md §4 — Domestic hot-water demand.

    Inputs:
    - day_of_year: one-indexed day of year, count from 1 to 365.

    Outputs:
    - cold-water inlet temperature in °C.
    """
    if 152 <= day_of_year <= 243:
        return 10.0
    if day_of_year >= 335 or day_of_year <= 59:
        return 6.0
    if 60 <= day_of_year <= 151:
        return 6.0 + ((day_of_year - 60) / (151 - 60)) * 4.0
    if 244 <= day_of_year <= 334:
        return 10.0 - ((day_of_year - 244) / (334 - 244)) * 4.0
    raise ValueError("day_of_year must be in the range 1..365")


def derive_hlc_w_per_k(property_input: PropertyInput) -> float:
    """Return the property heat loss coefficient from direct input or design heat loss.

    Implements MODEL.md §3 — Space-heating demand.

    Inputs:
    - property_input: property schema with hlc_w_per_k in W/K or heat_loss_design_w in W,
      t_internal_c in °C, and t_design_outdoor_c in °C.

    Outputs:
    - heat loss coefficient in W/K.
    """
    if property_input.hlc_w_per_k is not None:
        return property_input.hlc_w_per_k
    return property_input.heat_loss_design_w / (
        property_input.t_internal_c - property_input.t_design_outdoor_c
    )


def calculate_daily_space_heating_demand(
    t_out_c: np.ndarray,
    hlc_w_per_k: float,
    t_base_c: float,
) -> np.ndarray:
    """Calculate delivered daily space-heating demand from HLC and outdoor temperature.

    Implements MODEL.md §3 — Space-heating demand.

    Inputs:
    - t_out_c: daily mean outdoor temperatures in °C.
    - hlc_w_per_k: heat loss coefficient in W/K.
    - t_base_c: balance-point temperature in °C.

    Outputs:
    - daily delivered space-heating demand in kWh/day.
    """
    return np.maximum(0, hlc_w_per_k * (t_base_c - t_out_c) * 24) / 1000


def calculate_annual_dhw_demand(dhw: DhwInput) -> float:
    """Calculate annual domestic hot-water heat delivered to water.

    Implements MODEL.md §4 — Domestic hot-water demand.

    Inputs:
    - dhw: DHW schema with occupants count, cylinder_l in litres, and t_setpoint_c in °C.

    Outputs:
    - annual delivered DHW demand in kWh/year.
    """
    cold_inlet_c = np.array([_cold_inlet_c(day) for day in range(1, 366)])
    daily_kwh_per_person = (
        LITRES_PER_PERSON_PER_DAY
        * WATER_SPECIFIC_HEAT_KJ_PER_KG_K
        * (dhw.t_setpoint_c - cold_inlet_c)
        / KJ_PER_KWH
    )
    return float(dhw.occupants * np.sum(daily_kwh_per_person))


def distribute_daily_dhw_demand(
    annual_dhw_kwh: float,
    days: int = 365,
) -> np.ndarray:
    """Distribute annual domestic hot-water demand evenly across days.

    Implements MODEL.md §4 — Domestic hot-water demand.

    Inputs:
    - annual_dhw_kwh: annual delivered DHW demand in kWh/year.
    - days: number of days over which to distribute demand, count.

    Outputs:
    - daily delivered DHW demand in kWh/day.
    """
    return np.full(days, annual_dhw_kwh / days)
