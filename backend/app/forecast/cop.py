import numpy as np

KELVIN_OFFSET_C = 273.15
ETA_MIN = 0.30
ETA_MAX = 0.65
DEFROST_PENALTY_CENTRE_C = 2.0
DEFROST_PENALTY_WIDTH_C = 3.0
COP_FLOOR = 1.0


def carnot_cop(
    t_out_c: np.ndarray,
    t_flow_c: float,
) -> np.ndarray:
    """Calculate the reversed-Carnot maximum COP for heating.

    Implements MODEL.md section 5.1 - Carnot-fraction form.

    Inputs:
    - t_out_c: outdoor temperatures in degrees C.
    - t_flow_c: heat-pump flow temperature in degrees C.

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


def defrost_penalty(t_out_c: np.ndarray, peak: float) -> np.ndarray:
    """Defrost penalty as a Gaussian bump centred at 2 C with 3 C width.

    Returns a fraction in [0, peak] to be subtracted multiplicatively from
    the Carnot-derived COP. With peak=0 returns all zeros. Smooth and
    differentiable. Concentrates the loss in the 0-5 C frosting zone where
    UK heat pumps spend most of their winter hours.

    Physics: above roughly 6 C condensed moisture does not freeze; below
    roughly -10 C the air carries too little moisture for frost to form rapidly.
    The Gaussian shape decays appropriately on both sides. UK winter relative
    humidity is typically 80-95%, so this temperature-only approximation is
    defensible for v1; humidity-conditional frosting maps are deferred until
    reference case data can constrain them.
    """
    t_out_c = np.asarray(t_out_c, dtype=float)
    return peak * np.exp(
        -((t_out_c - DEFROST_PENALTY_CENTRE_C) / DEFROST_PENALTY_WIDTH_C) ** 2
    )


def calculate_cop_curve(
    t_out_c: np.ndarray,
    t_flow_c: float,
    eta: float,
    defrost_penalty_peak_pct: float = 0.0,
) -> np.ndarray:
    """Calculate real heat-pump COP from second-law efficiency and Carnot COP.

    Implements MODEL.md section 5.1 - Carnot-fraction form.

    Inputs:
    - t_out_c: outdoor temperatures in degrees C.
    - t_flow_c: heat-pump flow temperature in degrees C.
    - eta: second-law efficiency, dimensionless fraction.
    - defrost_penalty_peak_pct: peak defrost COP penalty, dimensionless fraction.

    Outputs:
    - real heat-pump COP values, dimensionless.
    """
    if eta <= 0 or eta > 1:
        raise ValueError(f"eta must be > 0 and <= 1; eta={eta}")
    if defrost_penalty_peak_pct < 0 or defrost_penalty_peak_pct > 0.30:
        raise ValueError(
            "defrost_penalty_peak_pct must be >= 0 and <= 0.30; "
            f"defrost_penalty_peak_pct={defrost_penalty_peak_pct}"
        )

    t_out_c = np.asarray(t_out_c, dtype=float)
    carnot = carnot_cop(t_out_c, t_flow_c)
    raw_cop = eta * carnot * (1 - defrost_penalty(t_out_c, defrost_penalty_peak_pct))
    return np.maximum(raw_cop, COP_FLOOR)


def fit_eta_from_scop(
    scop: float,
    daily_space_heating_kwh: np.ndarray,
    t_out_c: np.ndarray,
    t_flow_sh_c: float,
    defrost_penalty_peak_pct: float = 0.0,
) -> tuple[float, bool]:
    """Fit second-law efficiency so the demand-weighted COP curve reproduces SCOP.

    Implements MODEL.md section 5.2 - Fitting eta from SCOP.

    Inputs:
    - scop: stated seasonal coefficient of performance, dimensionless.
    - daily_space_heating_kwh: daily delivered space-heating demand in kWh/day.
    - t_out_c: daily mean outdoor temperatures in degrees C.
    - t_flow_sh_c: space-heating flow temperature in degrees C.
    - defrost_penalty_peak_pct: peak defrost COP penalty, dimensionless fraction.

    Outputs:
    - fitted second-law efficiency eta, dimensionless fraction, and boundary flag.
    """
    if defrost_penalty_peak_pct < 0 or defrost_penalty_peak_pct > 0.30:
        raise ValueError(
            "defrost_penalty_peak_pct must be >= 0 and <= 0.30; "
            f"defrost_penalty_peak_pct={defrost_penalty_peak_pct}"
        )
    daily_space_heating_kwh = np.asarray(daily_space_heating_kwh, dtype=float)
    t_out_c = np.asarray(t_out_c, dtype=float)

    non_zero_demand = daily_space_heating_kwh != 0
    demand_kwh = daily_space_heating_kwh[non_zero_demand]
    t_out_with_demand_c = t_out_c[non_zero_demand]
    if demand_kwh.size == 0:
        raise ValueError("daily_space_heating_kwh must contain at least one non-zero day")

    carnot = carnot_cop(t_out_with_demand_c, t_flow_sh_c)
    penalty_factor = 1 - defrost_penalty(
        t_out_with_demand_c,
        defrost_penalty_peak_pct,
    )
    weighted_carnot = carnot * penalty_factor
    eta_unclamped = scop * np.sum(demand_kwh / weighted_carnot) / np.sum(demand_kwh)
    at_boundary = eta_unclamped < ETA_MIN or eta_unclamped > ETA_MAX
    eta = np.clip(eta_unclamped, ETA_MIN, ETA_MAX)
    return float(eta), bool(at_boundary)
