\# MODEL.md — Heat Pump Running-Cost Forecaster



This document specifies the mathematical model behind the forecast. It is the

source of truth. Code must implement this; if code and this document disagree,

the code is wrong.



The forecaster takes a property, a heat pump, hot-water demand, and a tariff,

and returns a probabilistic forecast of annual electricity consumption and

running cost. The forecast is expressed as a distribution, not a single number.

Uncertainty comes from (a) weather variability across plausible winters and

(b) residual model error.



All temperatures are in degrees Celsius unless explicitly stated as Kelvin

(suffix `\_K`). All energy is in kWh. All power is in W or kW (suffixed).

All money is in GBP. Convert at function boundaries; never mix.



\---



\## 1. Inputs



\### 1.1 Property

\- `floor\_area\_m2` — floor area, m².

\- Either `HLC\_W\_per\_K` (heat loss coefficient) \*\*or\*\* `heat\_loss\_design\_W`

&#x20; with `T\_design\_outdoor\_C` and `T\_internal\_C` (default 21 °C). If the second

&#x20; form is given, compute:



&#x20;     HLC\_W\_per\_K = heat\_loss\_design\_W / (T\_internal\_C − T\_design\_outdoor\_C)



\- `postcode` — used only to look up latitude/longitude via postcodes.io,

&#x20; then discarded. Never persisted with user data.

\- `T\_base\_C` — balance-point temperature for heat demand, default 15.5 °C.



\### 1.2 Heat pump

\- `SCOP` — seasonal coefficient of performance from MCS/manufacturer.

\- `T\_flow\_SH\_C` — design flow temperature for space heating (typically 35–55 °C).

\- `T\_design\_outdoor\_C` — outdoor temperature at which the system is sized.



\### 1.3 Hot water

\- `occupants` — integer.

\- `cylinder\_L` — litres (informational; not used in baseline demand calc).

\- `T\_setpoint\_C` — DHW setpoint, default 48 °C.

\- `T\_flow\_DHW\_C` — flow temperature delivering DHW, default 52 °C

&#x20; (slightly above setpoint to allow heat-exchanger ΔT).



\### 1.4 Tariff (per scenario)

\- `standing\_charge\_p\_per\_day`

\- `unit\_rate\_p\_per\_kWh`



The model accepts a list of tariff scenarios; output is computed for each.



\---



\## 2. Climate input



For the property's lat/long, fetch daily mean air temperature from

Open-Meteo's historical archive for the most recent \*\*20 winters\*\*

(October–March inclusive). Each winter is treated as one realisation

of "next winter."



Let:

\- `W = { w\_1, w\_2, …, w\_20 }` — set of historical winters.

\- Each `w\_i` is a vector of daily mean temperatures `T\_out,d` for that winter.



These are not averaged. They are kept as separate realisations and propagated

through Monte Carlo (Section 6).



\---



\## 3. Space-heating demand



For each day `d` with mean outdoor temperature `T\_out,d`:



&#x20;   Q\_SH,d\_kWh = max(0, HLC\_W\_per\_K × (T\_base\_C − T\_out,d) × 24) / 1000



This is heat \*delivered to the building\*, not electricity consumed.



Annual space-heating demand for winter `w\_i`:



&#x20;   Q\_SH,i\_kWh = Σ\_d  Q\_SH,d\_kWh



Days outside the heating season (T\_out,d ≥ T\_base\_C) contribute zero,

which the `max(0, …)` enforces.



\---



\## 4. Domestic hot-water demand



Annual DHW energy delivered to water (kWh/year):



&#x20;   Q\_DHW\_annual\_kWh =

&#x20;       occupants × 50 × 365 × 4.186 × (T\_setpoint\_C − T\_cold\_inlet\_C) / 3600



where `T\_cold\_inlet\_C` varies seasonally (linear interpolation):

\- June–August: 10 °C

\- December–February: 6 °C

\- March–May, September–November: interpolated.



50 L/person/day is the BREDEM standard hot-water usage.

4.186 kJ/(kg·K) is the specific heat capacity of water.

Division by 3600 converts kJ → kWh.



DHW demand is distributed evenly across days for the MVP. (A future version

may add a winter-skewed profile; document it explicitly when added.)



\---



\## 5. Coefficient of Performance



Heat pump COP varies with outdoor temperature and flow temperature.



\### 5.1 Carnot-fraction form



The theoretical maximum COP (reversed Carnot) for heating is:



&#x20;   COP\_Carnot(T\_out, T\_flow) =

&#x20;       (T\_flow\_K) / (T\_flow\_K − T\_out\_K)



where `T\_K = T\_C + 273.15`.



Real heat pumps achieve a fraction of this. Define second-law efficiency `η`:



&#x20;   COP(T\_out, T\_flow) = η × COP\_Carnot(T\_out, T\_flow)



Typical η for modern air-source heat pumps falls in the range 0.40–0.55.



\### 5.2 Fitting η from SCOP



The user gives a single SCOP figure. We back out η so that the COP curve,

weighted by the climate-driven heat demand, reproduces the stated SCOP.



For space heating, the seasonal COP implied by η is:



&#x20;   SCOP\_implied(η) =

&#x20;       Σ\_d Q\_SH,d\_kWh

&#x20;     ────────────────────────────────────────────────

&#x20;       Σ\_d  Q\_SH,d\_kWh / (η × COP\_Carnot(T\_out,d, T\_flow\_SH))



Numerically solve for `η` such that `SCOP\_implied(η) = SCOP`.

Use the climatological mean across the 20 winters for this fit

(not any single year), so η is a property of the system, not the weather.



Constrain η to \[0.30, 0.65]. If the solver leaves this range, flag

the inputs as inconsistent — the SCOP is implausible for the stated

flow temperature.



\### 5.3 DHW COP



DHW runs at a higher, near-constant flow temperature year-round.

Use the same `η` fitted from space heating:



&#x20;   COP\_DHW(T\_out,d) = η × COP\_Carnot(T\_out,d, T\_flow\_DHW)



This is a known simplification — DHW η may differ slightly from SH η —

and is the largest acknowledged source of model error. The 8% residual

noise in Section 6.2 absorbs it.



\---



\## 6. From demand to electricity



\### 6.1 Daily electricity



For each day `d` in winter `w\_i`:



&#x20;   E\_SH,d\_kWh  = Q\_SH,d\_kWh  / COP(T\_out,d, T\_flow\_SH)

&#x20;   E\_DHW,d\_kWh = Q\_DHW,d\_kWh / COP\_DHW(T\_out,d)



where `Q\_DHW,d\_kWh = Q\_DHW\_annual\_kWh / 365`.



Annual electricity for winter `w\_i`:



&#x20;   E\_total,i\_kWh = Σ\_d (E\_SH,d\_kWh + E\_DHW,d\_kWh)



\### 6.2 Monte Carlo



Generate 1000 draws of annual electricity:



&#x20;   For k = 1 … 1000:

&#x20;       i  ← uniform random choice from {1, …, 20}      # weather draw

&#x20;       ε  ← Normal(0, σ²) where σ = 0.08 × E\_total,i\_kWh   # residual noise

&#x20;       E\_k\_kWh = E\_total,i\_kWh + ε



Clip `E\_k\_kWh` at zero. Store the full 1000-vector.



The 8% standard deviation captures unmodelled effects: occupancy variation,

the SH/DHW η difference, controller behaviour, defrost cycles, etc.

This figure is a deliberate, conservative placeholder for v1 and will be

refined when calibration data exists (Section 8).



\### 6.3 Cost



For each draw `k` and tariff scenario `s`:



&#x20;   Cost\_k,s\_GBP =

&#x20;       (E\_k\_kWh × unit\_rate\_p\_per\_kWh\_s / 100)

&#x20;     + (365 × standing\_charge\_p\_per\_day\_s / 100)



\---



\## 7. Outputs



For each tariff scenario, report:

\- 10th, 50th, 90th percentiles of `E\_k\_kWh` (space heating, DHW, total).

\- 10th, 50th, 90th percentiles of `Cost\_k,s\_GBP`.

\- The full 1000-vector for chart rendering.

\- A monthly breakdown derived by aggregating daily values from the median

&#x20; winter realisation.



Headline statement format:



&#x20;   "Likely annual running cost £P10–£P90 (central £P50)"



Always show the range. Never show only the median.



\---



\## 8. Calibration (`/calibrate`)



Given a user's actual monthly electricity for the last `N` years (N ≥ 1):



1\. Walk-forward: for each year `y` in the user's data, fit using only years

&#x20;  `< y` and forecast year `y`.

&#x20;  - For `N = 1`, "fit" is trivial — use the model with the stated SCOP and

&#x20;    report a single point. Real walk-forward needs N ≥ 2.

2\. For each forecasted year, compute:

&#x20;  - Absolute error in kWh and GBP versus realised.

&#x20;  - Whether the realised value fell within the predicted 10th–90th band

&#x20;    (1 if yes, 0 if no).

&#x20;  - The PIT value: empirical CDF of the realised value within the 1000

&#x20;    predicted draws, i.e. `rank(realised) / 1000`.

3\. Aggregate:

&#x20;  - \*\*MAE\*\* in kWh and GBP.

&#x20;  - \*\*Coverage of 80% interval\*\* = mean of the in-band indicators. Should

&#x20;    be ≈ 0.80 if the model is calibrated.

&#x20;  - \*\*PIT histogram\*\* with 10 bins. Should be approximately uniform if

&#x20;    calibrated; a U-shape means intervals are too narrow; a hump means

&#x20;    they are too wide.



These three numbers — MAE, coverage, PIT — are the product's credibility.

They must be displayed prominently, not buried.



\---



\## 9. Invariants the code must satisfy



These are testable claims that, if violated, indicate a bug.



1\. \*\*Carnot positivity.\*\* `T\_flow\_K − T\_out\_K > 0` always. If a user enters

&#x20;  a flow temp below outdoor temp, refuse the input.

2\. \*\*COP bound.\*\* Computed COP never exceeds Carnot. If

&#x20;  `COP(T\_out, T\_flow) > COP\_Carnot(T\_out, T\_flow)`, the code has mixed

&#x20;  Kelvin and Celsius somewhere. Stop and assert.

3\. \*\*Monotonicity in outdoor temperature.\*\* For fixed `T\_flow`, daily

&#x20;  electricity is non-increasing in `T\_out` over the heating season. If a

&#x20;  colder day forecasts less electricity, units are wrong.

4\. \*\*Cold-snap elasticity.\*\* A uniform −3 °C shift to the climate raises

&#x20;  median annual electricity by \*more\* than the same shift applied with

&#x20;  COP held constant. This is the heat-pump signature; if absent, the

&#x20;  COP model is not engaged.

5\. \*\*DHW non-zero.\*\* DHW electricity > 0 even at outdoor temperatures

&#x20;  above `T\_base\_C`. (DHW runs year-round.)

6\. \*\*Unit traceability.\*\* Every numeric field in the API response is

&#x20;  suffixed `\_kWh`, `\_gbp`, `\_pct`, `\_C`, or `\_K`. Naked numbers are

&#x20;  a bug.



\---



\## 10. Acknowledged limitations (be honest about these in the UI)



\- η is fitted once and held constant across SH and DHW.

\- The 8% residual noise is a placeholder, not estimated from data.

\- DHW load is spread evenly across days.

\- No solar PV credit. No battery. No time-of-use tariffs in v1.

\- Defrost cycles, auxiliary resistive heaters, and standby losses are

&#x20; absorbed into η and the residual noise rather than modelled explicitly.

\- The model assumes the heat pump is correctly sized to the building.

&#x20; An undersized unit running on resistive backup will exceed the

&#x20; forecast and the model has no way to know.



A v2 should address the η split between SH and DHW first; it is the

largest known source of bias.



\---



\## 11. References



\- BS EN 12831:2017 — Energy performance of buildings: heating load.

\- BREDEM 2012 — Building Research Establishment Domestic Energy Model

&#x20; (hot-water demand: 50 L/person/day).

\- Staffell, I., Brett, D., Brandon, N., Hawkes, A. (2012). \*A review of

&#x20; domestic heat pumps.\* Energy \& Environmental Science, 5(11): 9291–9306.

&#x20; (Source of typical η values and Carnot-fraction approach.)

\- Open-Meteo Historical Weather API — https://open-meteo.com/en/docs/historical-weather-api

\- Gneiting, T., Raftery, A. E. (2007). \*Strictly proper scoring rules,

&#x20; prediction, and estimation.\* JASA, 102(477): 359–378. (PIT and

&#x20; coverage as calibration tests.)

