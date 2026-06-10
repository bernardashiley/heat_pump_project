# V1 Diagnostic Findings

## 1. Climate Window Finding

`backend/app/forecast/climate.py` fetches Open-Meteo data from `2006-10-01` to `2026-03-31` for a 20-winter run, then filters to months `{1, 2, 3, 10, 11, 12}`. The retained calendar window is October-March only:

- Winter 0: October-December 2006 plus January-March 2007
- Winter 1: October-December 2007 plus January-March 2008
- ...
- Winter 19: October-December 2025 plus January-March 2026

The frame therefore contains 182 days in non-leap winters and 183 days in winters with a leap-year February. Across 20 winters from 2006-07 through 2025-26, the cached frame contains 3,645 days.

`backend/app/forecast/demand.py` calculates daily space-heating demand only for the outdoor temperatures passed into it:

```python
Q_SH,d = max(0, HLC * (T_base - T_out) * 24) / 1000
```

There is no demand generated for dates outside the climate frame. Since the climate frame contains only October-March days, the model only calculates space-heating demand for October-March.

`backend/app/forecast/monte_carlo.py` then aggregates daily electricity by `winter_id` using `np.bincount`. There is no annualisation step that scales October-March electricity to a full calendar year. The output called annual electricity is therefore a winter-window total, not a full-year total.

Domestic hot water has the same window problem. The model computes an annual DHW heat demand, divides it by 365 to get a daily load, but only creates daily DHW values for `len(climate)` rows. Because `len(climate)` contains only October-March days, each winter gets roughly 182/365 of annual DHW, not the full annual DHW load.

To quantify the space-heating side, I used an HDD-style approximation with `t_base = 15.5 deg C` and representative UK monthly mean temperatures:

| Quantity | HDD |
|---|---:|
| Annual HDD | 2,145.9 |
| October-March HDD | 1,719.0 |
| October-March fraction | 80.1% |
| September-May fraction | 98.5% |

This implies that an October-March-only space-heating model misses roughly 20% of annual heating-degree demand. Most of the missing demand is in April, May, and September; June-August contributes little at `t_base = 15.5 deg C`.

Conclusion: the climate window is a strong candidate for systematic underprediction. It can plausibly explain about 20% missing space-heating electricity, plus roughly half of annual DHW electricity being omitted.

## 2. Base Temperature Finding

The base temperature is used in `calculate_daily_space_heating_demand`:

```python
np.maximum(0, hlc_w_per_k * (t_base_c - t_out_c) * 24) / 1000
```

For system 429, the relevant inputs are:

- Realised annual electricity: 9,857 kWh
- Run B p50 total prediction in the full evaluation: 3,648 kWh
- Measured design heat loss override: 7,500 W
- Measured indoor temperature: 22.9274 deg C
- Design outdoor temperature: -5 deg C
- Model-derived HLC: 268.55 W/K
- Realised SPF fed as SCOP: 3.49
- Space-heating flow temperature: 33 deg C

Important distinction: the dataset override is a measured design heat loss in W, not directly an HLC in W/K. The model converts it to HLC as:

```text
7500 W / (22.9274 - (-5)) K = 268.55 W/K
```

Using the cached climate for system 429 and the model's current COP fitting, the SH-only median winter-window electricity is:

| Base temperature | Fitted eta | SH electricity p50 | Delivered SH heat p50 |
|---:|---:|---:|---:|
| 15.5 deg C | 0.3180 | 3,006 kWh | 10,590 kWh |
| 18.0 deg C | 0.3151 | 3,843 kWh | 13,530 kWh |
| 20.0 deg C | 0.3136 | 4,514 kWh | 15,883 kWh |

Including the current model's winter-window DHW electricity for occupants=3:

| Base temperature | SH p50 | DHW p50 | Total p50, no residual noise |
|---:|---:|---:|---:|
| 15.5 deg C | 3,006 kWh | 560 kWh | 3,568 kWh |
| 18.0 deg C | 3,843 kWh | 565 kWh | 4,410 kWh |
| 20.0 deg C | 4,514 kWh | 568 kWh | 5,083 kWh |

Raising `t_base_c` materially increases predicted electricity, but it does not fully explain system 429's underprediction. Even at `t_base_c = 20.0 deg C`, the model remains far below the realised 9,857 kWh.

Conclusion: base temperature is an important sensitivity, but it is not the sole mechanism. It likely interacts with the climate-window issue: a higher base temperature makes shoulder-season days matter more, but those shoulder-season days are currently absent from the model.

## 3. DHW Magnitude Finding

`calculate_annual_dhw_demand` uses:

```text
occupants * sum_day(50 L/person/day * 4.186 kJ/kg/K * (T_setpoint - T_cold_inlet(day)) / 3600)
```

The cold-water inlet model is seasonal:

- December-February: 6 deg C
- June-August: 10 deg C
- Spring and autumn: linear interpolation between 6 deg C and 10 deg C

Cylinder volume and DHW flow temperature are present in the schema, but annual DHW heat demand currently depends on occupants, setpoint, and cold-inlet temperature only. Cylinder volume does not affect annual DHW demand in v1.

For system 429, with `t_setpoint_c = 48 deg C`, the model gives:

| Occupants | Annual DHW heat demand |
|---:|---:|
| 3 | 2,546 kWh/year |
| 4 | 3,394 kWh/year |
| 5 | 4,243 kWh/year |

The industry rule of thumb for a 4-person UK household is approximately 2,500-3,500 kWh/year of DHW heat. The model's 4-person value, 3,394 kWh/year, is within that rule-of-thumb range. The heat-demand magnitude is therefore reasonable.

However, the orchestrator only instantiates DHW daily load over the October-March climate rows. For system 429 at occupants=3, the model's winter-window DHW electricity p50 is about 560 kWh. A full-year equivalent under the same COP assumptions would be roughly double that. This is a missing-load issue caused by the climate frame, not by the DHW heat formula itself.

Conclusion: DHW heat demand is not obviously too low. The bigger DHW issue is that only the winter-window fraction of annual DHW is counted in the forecast.

## 4. Best Hypothesis for the 30% Underprediction

The strongest hypothesis is a combined annualisation/window problem:

1. Space heating is only calculated for October-March.
2. October-March represents approximately 80% of annual UK HDD at `t_base = 15.5 deg C`.
3. The missing April, May, and September shoulder-season heating can plausibly account for around 20% underprediction.
4. Annual DHW is calculated correctly as heat, but only about half of it is included because the daily DHW series is only created for October-March climate rows.
5. The PIT histogram for Run B is extremely upper-tail loaded: 72.8% of measured-input cases land above the model's 90th percentile. That is consistent with a systematic missing-load mechanism rather than random input noise.
6. Raising base temperature helps but does not fully close the gap on system 429. This suggests base temperature alone is not the smoking gun, but it likely amplifies the shoulder-season omission.

The evidence does not support the idea that the DHW heat formula itself is the main source of error. The 4-person DHW heat output matches the common UK rule-of-thumb range. The issue is that the annual DHW load is not fully represented in the daily simulation window.

## 5. V2 Fix Options

### Candidate A: Extend Climate Window to Full Year

Scope: medium.

Change climate fetching to retain all months, not only October-March. Each weather realisation should become a complete 365/366-day year or a heating year with explicit annual coverage. Space heating naturally falls to zero in warm months through the existing `max(0, ...)` demand formula. DHW would then be included for every day of the year.

This is the cleanest fix because it addresses both missing shoulder-season space heating and missing annual DHW.

Implementation work:

- Modify climate fetch/filter logic to keep full daily date range.
- Redefine `winter_id` or replace it with `weather_year_id`.
- Update tests that currently expect October-March-only rows.
- Re-run reference fixtures and HeatpumpMonitor evaluation under a v2 methodology.

### Candidate B: Annualise October-March Totals

Scope: small.

Apply a scaling factor from October-March HDD to annual HDD, and separately scale DHW from 182/365 to 365/365.

This is quick but less defensible. It assumes a fixed seasonal shape and hides the actual daily shoulder-season calculation. It also makes monthly breakdowns artificial.

Implementation work:

- Compute or assume an annualisation factor per location.
- Scale SH and DHW separately.
- Document the approximation and uncertainty.

### Candidate C: Make Base Temperature a Calibrated/User Input

Scope: small to medium.

Expose or infer a higher balance temperature for homes with continuous heating, high comfort setpoints, high ventilation, or underfloor/radiator control behaviours. Current `t_base_c = 15.5 deg C` is a conventional HDD base, but monitored heat pumps may consume meaningful electricity at higher outdoor temperatures.

Implementation work:

- Add frontend/API input for base temperature or heating pattern.
- Add calibration logic using past consumption if available.
- Expand uncertainty in the absence of calibration data.

This should not be done as a post-hoc constant change. It needs a v2 pre-registered evaluation because it can easily be tuned to the current dataset.

### Candidate D: Full-Year DHW Simulation

Scope: small if done alongside Candidate A; medium if done independently.

Ensure DHW daily load is represented for all 365 days even if the climate frame remains winter-only. If climate remains winter-only, DHW COP outside October-March would need an assumption or separate annual temperature profile.

Implementation work:

- Generate a 365-day DHW series per weather year.
- Use full-year outdoor temperatures for DHW COP if Candidate A is implemented.
- Otherwise use monthly/seasonal outdoor approximations for DHW COP.

### Candidate E: Revisit Monitoring Boundary and Non-Modelled Loads

Scope: medium to large.

Some HeatpumpMonitor systems may include pumps, controls, backup heat, cycling, or other boundary loads not represented by the model. These could explain part of the remaining gap, especially for cases where full-year climate and DHW still underpredict.

Implementation work:

- Inspect `boundary_metering` and notes fields.
- Slice errors by monitoring boundary metadata.
- Add auxiliary electricity allowance if supported by evidence.

### Recommended V2 Path

The first v2 model change should be Candidate A: switch the simulation from October-March winter windows to full-year daily weather realisations. That is the most direct correction to the identified structural mismatch and should also fix the DHW truncation. Base temperature calibration should be evaluated after that, not before, because the current base-temperature evidence is confounded by missing shoulder-season days.

