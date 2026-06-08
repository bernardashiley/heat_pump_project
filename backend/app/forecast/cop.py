import numpy as np

KELVIN_OFFSET_C = 273.15
ETA_MIN = 0.30
ETA_MAX = 0.65


def carnot_cop(
    t_out_c: np.ndarray,
    t_flow_c: float,
) -> np.ndarray:
    """Calculate the reversed-Carnot maximum COP for heating.

    Implements MODEL.md §5.1 — Carnot-fraction form.

    Inputs:
    - t_out_c: outdoor temperatures in °C.
    - t_flow_c: heat-pump flow temperature in °C.

    Outputs:
    - theoretical maximum COP, dimensionless.
    """
    t_out_c = np.asarray(t_out_c, dtype=float)
    if np.any(t_flow_c <= t_out_c):
        offending_values = t_out_c[t_flow_c <= t_out_c]
        raise ValueError(
            "t_flow_c must be greater than every t_out_c value; "
            f"t_flow_c={t_flow_c}, offending t_out_c={offending_values.tolist()}"
        )

    t_out_k = t_out_c + KELVIN_OFFSET_C
    t_flow_k = t_flow_c + KELVIN_OFFSET_C
    return t_flow_k / (t_flow_k - t_out_k)


def calculate_cop_curve(
    t_out_c: np.ndarray,
    t_flow_c: float,
    eta: float,
) -> np.ndarray:
    """Calculate real heat-pump COP from second-law efficiency and Carnot COP.

    Implements MODEL.md §5.1 — Carnot-fraction form.

    Inputs:
    - t_out_c: outdoor temperatures in °C.
    - t_flow_c: heat-pump flow temperature in °C.
    - eta: second-law efficiency, dimensionless fraction.

    Outputs:
    - real heat-pump COP values, dimensionless.
    """
    if eta <= 0 or eta > 1:
        raise ValueError(f"eta must be > 0 and <= 1; eta={eta}")
    return eta * carnot_cop(t_out_c, t_flow_c)


def fit_eta_from_scop(
    scop: float,
    daily_space_heating_kwh: np.ndarray,
    t_out_c: np.ndarray,
    t_flow_sh_c: float,
) -> tuple[float, bool]:
    """Fit second-law efficiency so the demand-weighted COP curve reproduces SCOP.

    Implements MODEL.md §5.2 — Fitting η from SCOP.

    Inputs:
    - scop: stated seasonal coefficient of performance, dimensionless.
    - daily_space_heating_kwh: daily delivered space-heating demand in kWh/day.
    - t_out_c: daily mean outdoor temperatures in °C.
    - t_flow_sh_c: space-heating flow temperature in °C.

    Outputs:
    - fitted second-law efficiency eta, dimensionless fraction, and boundary flag.
    """
    daily_space_heating_kwh = np.asarray(daily_space_heating_kwh, dtype=float)
    t_out_c = np.asarray(t_out_c, dtype=float)

    non_zero_demand = daily_space_heating_kwh != 0
    demand_kwh = daily_space_heating_kwh[non_zero_demand]
    t_out_with_demand_c = t_out_c[non_zero_demand]
    if demand_kwh.size == 0:
        raise ValueError("daily_space_heating_kwh must contain at least one non-zero day")

    carnot = carnot_cop(t_out_with_demand_c, t_flow_sh_c)
    eta_unclamped = scop * np.sum(demand_kwh / carnot) / np.sum(demand_kwh)
    at_boundary = eta_unclamped < ETA_MIN or eta_unclamped > ETA_MAX
    eta = np.clip(eta_unclamped, ETA_MIN, ETA_MAX)
    return float(eta), bool(at_boundary)
