# Calibration Methodology — Heat Pump Running-Cost Forecaster

**Version:** v2 (pre-evaluation)
**Status:** Pre-registered. Frozen before any evaluation metrics computed.
**Author:** Odwira & Whitehall
**Date:** 9 June 2026
**Document commit hash:** <to be recorded at commit time>
**Model code commit hash at evaluation time:** <to be recorded at evaluation time>

This document specifies the methodology for evaluating the v1 forecasting
model against UK heat pump monitoring data from HeatpumpMonitor.org. It is
written and committed before evaluation metrics are computed, so that
thresholds, runs, and decision rules cannot be tuned to favour the model.

Numbers and decision criteria stated below are commitments. If results fall
outside the committed thresholds, the consequence stated here applies,
regardless of how close to the threshold the result is. Any deviation from
this document during evaluation is recorded as a documented departure from
pre-registration.

---

## 1. Research questions

The evaluation answers four distinct questions:

**Q1: Is the demand-side model correct, conditional on accurate inputs?**
Given measured heat loss coefficient, measured indoor temperature, and the
realised seasonal performance factor as SCOP, does the model predict total
annual electricity consumption within acceptable tolerance?

**Q2: How much error does MCS heat-loss data contribute?**
Given measured indoor temperature and realised SPF, but substituting the
MCS-declared heat loss for the measured value, how much does prediction
accuracy degrade?

**Q3: How much error does the indoor-temperature assumption contribute?**
Given measured heat loss and realised SPF, but substituting the
user-declared or default 21 °C indoor temperature for the measured value,
how much does accuracy degrade?

**Q4: What is end-to-end accuracy in the realistic pre-purchase user
scenario?**
Using only inputs a real pre-purchase user has — MCS-declared heat loss,
user-declared or default indoor temperature, and a generic SCOP proxy —
how well does the model predict realised annual electricity?

---

## 2. Evaluation design — seven-run ablation

Each evaluation case is run multiple times with different input combinations
to isolate one error source at a time. Case sets are stated explicitly to
enable paired comparisons.

| Run | HLC source | Indoor temp source | SCOP source | Case set | Question answered |
|-----|------------|--------------------|-------------|----------|---------|
| A-full | MCS-declared | User-declared or 21 °C default | Realised SPF | all eligible | Realistic-demand inputs with oracle SPF, full sample |
| A-subset | MCS-declared | User-declared or 21 °C default | Realised SPF | measured-input subset | Paired baseline for B/C/D/E |
| B | Measured | Measured | Realised SPF | measured-input subset | Q1 — demand-side upper bound |
| C | Measured | Measured | Fixed 3.5 proxy | measured-input subset | Fixed-SCOP proxy error |
| D | MCS-declared | Measured | Realised SPF | measured-input subset | Q2 — MCS HLC substitution effect |
| E | Measured | User-declared or 21 °C default | Realised SPF | measured-input subset | Q3 — indoor temp substitution effect |
| F | MCS-declared | User-declared or 21 °C default | Fixed 3.5 proxy | all eligible | Q4 — true realistic-user end-to-end forecast |

Permitted comparisons are stated as deltas:

- **B − A-subset:** total accuracy improvement from having full monitoring data, on the same cases.
- **B − D:** conditional effect of substituting MCS heat loss while other inputs are held fixed.
- **B − E:** conditional effect of substituting indoor temperature while other inputs are held fixed.
- **B − C:** conditional effect of substituting a fixed generic SCOP proxy while other inputs are held fixed.
- **F vs A-full:** end-to-end vs oracle-SPF baseline; both runs use the full sample.

The word "solely" is not used; nonlinear interactions between input errors are possible and the deltas above are conditional effects holding other inputs fixed.

---

## 3. Dataset

### 3.1 Source

HeatpumpMonitor.org public dataset, accessed via the `/system/list/public.json` and `/system/stats/all` endpoints. The dataset is maintained by the OpenEnergyMonitor community.

A snapshot is committed to `data/heatpumpmonitor/` with the fetch date in the filename. All published evaluations use the same snapshot. The snapshot date is recorded in every output file.

### 3.2 Inclusion criteria

A system is included if all of the following hold:

1. The system has a stats record.
2. `combined_data_length` ≥ 365 × 86400 seconds (at least one year of data).
3. `data_flag` is unset or zero.
4. All essential MCS fields are present and non-null: `floor_area`, `heat_loss`, `design_temp`, `flow_temp`, `hp_output`, `latitude`, `longitude`.
5. `quality_elec` ≥ 90% and `quality_heat` ≥ 90%.
6. `combined_cop` is not null and > 1.5.
7. `combined_elec_kwh`, `combined_heat_kwh`, `combined_outsideT_mean` are all present.
8. `(cooling_elec_kwh + immersion_kwh) / combined_elec_kwh ≤ 0.05`, treating missing fields as zero. Cases above this threshold are excluded from headline metrics. A strict-zero sensitivity analysis (Section 6.6) re-runs the headline metrics requiring both to be absent or zero.

Counts surviving each filter step are recorded in `eval_filter_report.txt` and committed to the repository.

### 3.3 Subsets for ablation runs

- **Eligible set:** all cases passing Section 3.2. Used in A-full and F.
- **Measured-input subset:** the subset of eligible cases with both `measured_heat_loss` present and `quality_roomT ≥ 70%`. Used in A-subset, B, C, D, E.

Subset size and the demographic distribution of the subset against the eligible set are reported. If the subset is materially different from the eligible set on age, insulation, or property type distributions, all claims from Runs B–E are restricted to the subset's characteristics in the report.

### 3.4 Snapshot governance

The dataset snapshot used for the published evaluation is frozen. Any re-fetch is a separate evaluation, separately reported.

---

## 4. Per-system input handling

### 4.1 Climate

**Headline (product-mode):** each system's latitude and longitude are used with the same 20-winter reference window (October 2006 – March 2026) that the v1 product uses for forecasts. This matches what a user receives from the product. Realised annual electricity is averaged over the system's monitoring window; this introduces a known noise floor from inter-annual demand variation, bounded at approximately ±5%.

**Secondary diagnostic (matched-window):** where each system's stats record allows reconstruction of its actual monitoring window, a parallel evaluation pulls climate data from Open-Meteo for that exact window. This diagnostic estimates the contribution of climate-window mismatch to error. It does not replace the headline product-mode metrics.

If matched-window cannot be reconstructed for some systems, the diagnostic runs on the subset where it can, and the subset size is reported.

### 4.2 SCOP

The model accepts a stated SCOP and fits a second-law efficiency η that reproduces it under the climate and demand profile. Choice of SCOP input defines the evaluation:

- **Runs A-full, A-subset, B, D, E:** feed realised SPF as SCOP. This makes the COP side of the model match reality by construction, isolating the demand side of the model from COP estimation error.
- **Runs C and F:** feed a fixed 3.5 SCOP. This is a transparent generic proxy, not nameplate SCOP. It tests the additional error introduced when the SCOP input is generic rather than realised.

The dataset does not contain manufacturer nameplate SCOP for individual systems. A future evaluation may replace the 3.5 proxy with per-model nameplate lookups; this is out of scope.

The dataset median realised SPF is not used as a proxy because that would leak outcome information from the evaluation population into the realistic run.

### 4.3 Indoor temperature

Three possible sources, in priority order:

1. **Measured** (`stats.combined_roomT_mean` when `quality_roomT ≥ 70%`). Used in Runs B, C, D.
2. **User-declared** (`systems.indoor_temperature` if it parses as a float in [15, 25]). Used in Runs A-full, A-subset, E, F when measured is unavailable.
3. **Default 21 °C.** Used when neither measured nor user-declared is available.

The fallback path used is tagged per case for slicing.

### 4.4 Heat loss coefficient

- **MCS-declared:** `systems.heat_loss × 1000` (the field is in kW). Used in Runs A-full, A-subset, D, F.
- **Measured:** `systems.measured_heat_loss × 1000`. Used in Runs B, C, E.

### 4.5 Domestic hot water

DHW inputs are held constant across all runs:

- Occupants: 3 (fixed assumption; see Section 6.2)
- Cylinder: `systems.cylinder_volume` if available, else 200 L
- Setpoint: 48 °C
- Flow: 52 °C

A DHW occupancy sensitivity analysis (Section 5.4) re-runs Run B with occupants ∈ {1, 2, 3, 4, 5}. If MAPE moves by less than 5 percentage points across that range, the fixed-occupancy assumption is not the dominant error source. If it moves by more than 10 percentage points, occupancy is critical and the v1 frontend must require it as input.

### 4.6 Other fixed inputs

- `t_base_c` = 15.5 °C (heating-degree-day balance temperature)
- `t_design_outdoor_c` = `systems.design_temp` per case
- `t_flow_sh_c` = `systems.flow_temp` per case
- `defrost_penalty_peak_pct` = 0.0 (realised SPF already includes real defrost behaviour in Runs A/B/D/E; for Runs C and F the choice is documented but the same default applies)
- Tariff: fixed BUILD central tariff (27 p/kWh, 53 p/day). Headline accuracy claims are in kWh, not GBP.

### 4.7 Random seed and draw count

The Monte Carlo draw count is fixed at 1000 per case per run. The random seed is fixed at the evaluation script level and reported in the output. The same seed sequence is used across runs A through F on each case, so that paired comparisons are not contaminated by sampling noise. PIT values inherit this seeding.

---

## 5. Metrics

### 5.1 Per-case metrics

For each case in each run:

- `predicted_p10_kwh`, `predicted_p50_kwh`, `predicted_p90_kwh`
- `interval_width_kwh` = `p90 − p10`
- `realised_annual_elec_kwh` = `combined_elec_kwh × 365 × 86400 / combined_data_length`
- `error_kwh` = `predicted_p50_kwh − realised_annual_elec_kwh`
- `error_pct` = 100 × `error_kwh / realised_annual_elec_kwh`
- `in_p10_p90_band` = `p10 ≤ realised ≤ p90`
- `pit` = empirical CDF rank of realised within the 1000-draw distribution, strict less-than convention

### 5.2 Aggregate metrics

For each run, across all cases in the run:

**Location metrics:**
- MAE in kWh
- MAPE
- MdAPE (median absolute percentage error)
- 1%-trimmed MAPE
- Median signed error %
- 10th and 90th percentile signed error %

**Coverage metrics:**
- Coverage of 80% interval (% of cases with `in_p10_p90_band`)
- Wilson 95% confidence interval on coverage
- PIT histogram (10 bins, normalised)
- Kolmogorov–Smirnov test against uniform PIT, p-value

**Sharpness metrics:**
- Median `interval_width_kwh`
- Median `interval_width_kwh` as % of median realised electricity
- Mean interval score for 80% interval (Gneiting & Raftery 2007)

**Probabilistic skill:**
- Mean CRPS computed from the 1000 predictive draws per case, if draws are retained at evaluation time.

### 5.3 Slice analyses

Run A-full is sliced and reported by:

- Property age bands as recorded in `systems.age`
- Insulation tier as recorded in `systems.insulation`
- Realised SPF band: <2.5, 2.5-3.5, 3.5-4.5, >4.5
- Property type: detached, semi-detached, terraced, flat

For each slice: coverage, Wilson CI, MAPE, median signed error, median interval width, case count. Slices with fewer than 10 cases are reported but flagged as insufficient sample size.

### 5.4 DHW occupancy sensitivity

Run B is repeated with occupants ∈ {1, 2, 3, 4, 5}. Coverage and MAPE are reported for each. Interpretation thresholds are in Section 7.

### 5.5 Strict-zero cooling/immersion sensitivity

Headline metrics are recomputed on the subset of cases where `cooling_elec_kwh` and `immersion_kwh` are both absent or zero. The number of cases retained and the metric shift are reported.

---

## 6. Known limitations

### 6.1 Selection bias in HeatpumpMonitor population

The dataset is self-selected. Submitters skew toward technically engaged owners of well-installed systems with above-average monitoring infrastructure. The realised SPF distribution may therefore be higher than the UK fleet average. The exact dataset mean is computed from the frozen snapshot and reported in the published evaluation alongside an external reference if a cited source is available. UK fleet average estimates from external sources are quoted only where citations can be provided.

Headline findings are framed as "*among well-monitored UK heat pump installations submitted to a community open-data platform,* the model's performance is..." — not as a claim about all UK heat pumps.

### 6.2 DHW occupancy

The 3-occupant assumption introduces a noise floor on per-case prediction accuracy. Section 5.4 reports the sensitivity. The dataset's notes field occasionally contains occupant information; this is not parsed in v1.

### 6.3 Subset representativeness for Runs B–E

Cases with measured heat loss and measured indoor temperature may differ systematically from those without. The demographic breakdown of the measured-input subset against the eligible set is reported. If materially different, all claims from Runs B–E are restricted to the subset's characteristics in the report wording.

### 6.4 Measurement uncertainty in realised values

Realised electricity is treated as ground truth. Class 1 electric meters contribute ~±1% accuracy; class 2 heat meters contribute ~±3-5%. The `boundary_metering` flags affect what is counted in each system. A perfect model cannot achieve 0% MAPE; the floor is approximately ±2% from meter accuracy alone. Below 5% MAPE, metric differences are no longer meaningfully distinguishable from measurement noise.

### 6.5 Climate window mismatch

The headline uses a 20-winter typical climate, not each system's actual monitoring window. This contributes approximately ±5% noise per case. Section 4.1's secondary diagnostic estimates this contribution explicitly.

### 6.6 Cooling and backup heater contributions

Some systems run heat pumps in cooling mode and some use immersion backup heaters. The model predicts heating-only electricity. Cases where these loads exceed 5% of total electricity are excluded from headline metrics (Section 3.2 criterion 8). Section 5.5 reports a strict-zero sensitivity analysis.

### 6.7 Noise floor heuristic

As a heuristic for interpretation, combining DHW occupancy, climate-window mismatch, and metering uncertainty gives an expected irreducible per-case error scale of approximately 10%. This is not treated as a formal variance decomposition; the components are not necessarily independent.

---

## 7. Decision criteria — pre-committed

The following thresholds are stated before any results are computed.

### 7.1 Demand-side model validation (Run B)

Validation requires all three:

| Metric | Validated | Adequate | Inadequate |
|---|---|---|---|
| Coverage of 80% interval | ≥ 75% | 60-75% | < 60% |
| MAPE | ≤ 12% | 12-20% | > 20% |
| Median interval width as % of median realised | ≤ 50% | 50-80% | > 80% |

Validation outcomes:

- **All three Validated:** demand-side model validated conditional on measured HLC, measured indoor temperature, and realised SPF. Proceed to v2 priorities.
- **At least one Adequate, none Inadequate:** documented as adequate but improvable. Ship v1 with explicit interval-width disclosure on the frontend.
- **Any one Inadequate:** halt v1 product positioning until the failing component is investigated.

**Threshold justification:** The 75% coverage threshold sits within the Wilson 95% confidence interval lower bound of a true 80% interval at expected sample sizes (n ≥ 100). The 12% MAPE threshold reflects the heuristic noise floor from DHW, climate window, and metering combined (Section 6.7) plus a small allowance for unmodelled effects. The 50% interval-width threshold is a product-usability bound, not a statistical truth — wider intervals are still statistically valid but cease to be useful for individual decisions.

### 7.2 v2 priorities (set by B − A-subset)

| Delta (B − A-subset) coverage | v2 priority |
|---|---|
| ≥ 30 percentage points | HLC calibration from past consumption is the highest-impact v2 feature |
| 15-30 percentage points | HLC calibration is one of several useful v2 features |
| < 15 percentage points | HLC error is not the dominant problem; investigate other sources |

### 7.3 Component-level decisions

- **If B − D coverage ≥ 20 pp:** MCS HLC substitution materially degrades accuracy. v2 product must require calibration data, not just recommend it.
- **If B − E coverage ≥ 15 pp:** Indoor-temperature substitution materially degrades accuracy. v1 frontend must require indoor temperature as input with a slider, not assume 21 °C.
- **If B − C coverage ≥ 20 pp:** Fixed generic SCOP proxy is inadequate. v2 should test whether per-model nameplate SCOP lookups reduce this error.

### 7.4 End-to-end product viability (Run F)

| Run F outcome | Action |
|---|---|
| Coverage ≥ 60% AND MAPE ≤ 25% | Realistic-user product is viable with documented uncertainty disclosure |
| Otherwise | Realistic-user product is not viable in its current form; require calibration data as gating input |

### 7.5 Sharpness diagnostic

Reported as a band, not a hard gate:

| Median p10–p90 width as % of realised | Interpretation |
|---|---|
| ≤ 25% | Sharp |
| 25-50% | Usable but broad |
| > 50% | Too wide for individual decisions |

### 7.6 Distributional shape

- **If any PIT bin > 0.15 or < 0.05** in Run B: predictive distribution shape is wrong, not just its location. Prioritise distributional fix in v2.
- **If KS test p-value < 0.05** against uniform PIT in Run B: same conclusion.

### 7.7 Slice findings

If any property-age or insulation slice in Run A-full has coverage < 50% with n ≥ 20, that slice is a known model weakness. The frontend must flag predictions for that slice as low-confidence.

### 7.8 DHW sensitivity

- **If Run B MAPE moves by < 5 pp across occupants ∈ {1,2,3,4,5}:** fixed 3-occupant assumption is acceptable.
- **If MAPE moves by 5-10 pp:** assumption is acceptable but DHW uncertainty should be propagated in v2.
- **If MAPE moves by > 10 pp:** occupancy is critical and v1 frontend must require it.

---

## 8. Reproducibility

### 8.1 Repository contents at evaluation time

- This methodology document, tagged with its commit hash
- The dataset snapshot files with their fetch date
- All three scripts:
  - `backend/scripts/fetch_heatpumpmonitor.py`
  - `backend/scripts/build_eval_dataset.py`
  - `backend/scripts/run_calibration_eval.py`
- The model code tagged with its commit hash at evaluation time
- Pinned dependencies in `backend/pyproject.toml`
- Output report `data/heatpumpmonitor/calibration_report.md`
- Per-case CSV `data/heatpumpmonitor/calibration_errors.csv`

### 8.2 Commit-hash freeze protocol

Before evaluation runs, this methodology document is committed and tagged. The model code is committed and tagged. Both commit hashes are recorded in the preamble of the published evaluation report. Any subsequent change to either before publishing results is documented as a deviation from pre-registration.

### 8.3 Reproduction commands

**To reproduce the published evaluation from the frozen snapshot:**
backend.venv\Scripts\python.exe backend\scripts\build_eval_dataset.py --use-frozen-snapshot
backend.venv\Scripts\python.exe backend\scripts\run_calibration_eval.py --snapshot-date <date>

**To generate a new evaluation from a fresh snapshot:**
backend.venv\Scripts\python.exe backend\scripts\fetch_heatpumpmonitor.py
backend.venv\Scripts\python.exe backend\scripts\build_eval_dataset.py
backend.venv\Scripts\python.exe backend\scripts\run_calibration_eval.py

The script interface (`--use-frozen-snapshot`, `--snapshot-date`) is committed in this methodology. The scripts must be updated to match before evaluation runs.

---

## 9. Pre-registered boundary of claims

The following claim boundaries are fixed before evaluation and must appear in any public summary of results.

1. Results apply only to well-monitored UK heat pump installations submitted to a community open-data platform. No claim is made about the UK fleet at large.
2. Runs A–E test the demand-side model under oracle realised-SPF input conditions. No claim that these runs validate the full forecasting pipeline.
3. Run F is the only run that tests realistic-user end-to-end forecasting.
4. The 3-occupant DHW assumption introduces a noise floor; per-case error below the Section 7.8 sensitivity range cannot be distinguished from occupancy error.
5. The model author developed the model with prior exposure to the Twentyman case used in test suites. The HeatpumpMonitor evaluation set was not used during model development. Confirmation bias cannot be excluded.

---

## 10. Claim mapping

Each public claim must be tied to a specific run outcome.

| Allowed claim | Evidence required |
|---|---|
| "Demand-side model is validated conditional on measured HLC, measured indoor temperature, and realised SPF" | Run B passes Section 7.1 |
| "MCS HLC substitution materially degrades accuracy in the measured-input subset" | B − D coverage ≥ 20 pp |
| "Indoor-temperature substitution materially degrades accuracy in the measured-input subset" | B − E coverage ≥ 15 pp |
| "Fixed generic SCOP proxy is inadequate" | B − C coverage ≥ 20 pp |
| "Realistic-user product is viable with documented uncertainty disclosure" | Run F passes Section 7.4 |
| "Calibration data is the highest-impact v2 feature" | B − A-subset coverage ≥ 30 pp |

Claims not in this table are not supported by this evaluation.

---

## 11. What this study is and is not

**It is:**

- A test of the model's demand-side and electricity-prediction behaviour against a real-world dataset under specified input assumptions
- A measurement of which input errors dominate prediction error
- A pre-committed decision framework for v2 priorities
- A reproducible artefact for institutional evaluation

**It is not:**

- A claim that the model is suitable for individual homeowner financial decisions without calibration
- A claim about UK heat pump fleet accuracy at large
- A replacement for direct measurement on a specific home
- A validated estimate of any specific system's running cost
- A validation of the full forecasting pipeline under realistic user inputs (only Run F approaches that, and it has stated limitations)
