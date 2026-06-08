import numpy as np

from app.models import DhwInput, PropertyInput


def derive_hlc_w_per_k(property_input: PropertyInput) -> float:
    """Return the property heat loss coefficient from direct input or design heat loss.

    Implements MODEL.md §3 — Space-heating demand.

    Inputs:
    - property_input: property schema with hlc_w_per_k in W/K or heat_loss_design_w in W,
      t_internal_c in °C, and t_design_outdoor_c in °C.

    Outputs:
    - heat loss coefficient in W/K.
    """
    raise NotImplementedError(f"demand.derive_hlc_w_per_k — see MODEL.md §3")


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
    raise NotImplementedError(
        f"demand.calculate_daily_space_heating_demand — see MODEL.md §3"
    )


def calculate_annual_dhw_demand(dhw: DhwInput) -> float:
    """Calculate annual domestic hot-water heat delivered to water.

    Implements MODEL.md §4 — Domestic hot-water demand.

    Inputs:
    - dhw: DHW schema with occupants count, cylinder_l in litres, and t_setpoint_c in °C.

    Outputs:
    - annual delivered DHW demand in kWh/year.
    """
    raise NotImplementedError(f"demand.calculate_annual_dhw_demand — see MODEL.md §4")


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
    raise NotImplementedError(f"demand.distribute_daily_dhw_demand — see MODEL.md §4")
