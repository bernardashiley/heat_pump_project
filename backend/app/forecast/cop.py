import numpy as np


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
    raise NotImplementedError(f"cop.carnot_cop — see MODEL.md §5.1")


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
    raise NotImplementedError(f"cop.calculate_cop_curve — see MODEL.md §5.1")


def fit_eta_from_scop(
    scop: float,
    daily_space_heating_kwh: np.ndarray,
    t_out_c: np.ndarray,
    t_flow_sh_c: float,
) -> float:
    """Fit second-law efficiency so the demand-weighted COP curve reproduces SCOP.

    Implements MODEL.md §5.2 — Fitting η from SCOP.

    Inputs:
    - scop: stated seasonal coefficient of performance, dimensionless.
    - daily_space_heating_kwh: daily delivered space-heating demand in kWh/day.
    - t_out_c: daily mean outdoor temperatures in °C.
    - t_flow_sh_c: space-heating flow temperature in °C.

    Outputs:
    - fitted second-law efficiency eta, dimensionless fraction.
    """
    raise NotImplementedError(f"cop.fit_eta_from_scop — see MODEL.md §5.2")
