# Calibration of a Probabilistic UK Heat Pump Running-Cost Forecaster v1: A Pre-Registered Evaluation Against HeatpumpMonitor.org

**Bernard Ashiley**
*Odwira & Whitehall*
10 June 2026

---

## Abstract

A probabilistic forecasting model for UK heat pump annual running costs was evaluated against the HeatpumpMonitor.org open dataset under a pre-registered methodology with seven-run input ablation, three-metric validation gates, and pre-committed decision rules. On 303 eligible systems, the model's 80% prediction intervals contained the realised annual electricity in 23.8% of cases (Wilson 95% CI: 17.7–31.2%); mean absolute percentage error on the measured-input subset was 29.1%; median signed error was −29.1%. The model failed all six pre-registered evidence claims. Post-evaluation diagnostic investigation identified a structural error in the v1 demand-period definition: the model fetched climate data for October through March, computed daily demand on those days, and reported the total as annual electricity, omitting roughly half of annual heating and domestic-hot-water load. This defect was not caught by the 91-test unit suite or by reference-case checks because both tested internal consistency rather than against external annual totals. It was caught by the calibration evaluation reported here. The evaluation artefacts, the defect's mechanism, and the boundary of supportable claims are reported below. A v1.1 ablation evaluation with corrected demand period is the next planned work.

---

## 2. Background

A v1 forecasting model was built to estimate the annual running cost of a UK domestic heat pump installation from inputs available to a pre-purchase user: the design heat loss in watts, the design outdoor temperature, the design flow temperature, the floor area, the postcode, and the heat pump's seasonal coefficient of performance (SCOP). These inputs correspond to the fields produced by the MCS heat pump design process, governed by the standard MIS 3005-D [1] and the underlying heat load methodology of BS EN 12831 [2]. The model produces a probabilistic annual electricity forecast as a 1,000-draw Monte Carlo distribution over 20 historical UK winter realisations, from which p10, p50, and p90 estimates are reported. Annual cost is derived by applying user-specified tariff scenarios to the electricity distribution.

The model's intended differentiator over deterministic running-cost calculators is the calibrated 80% prediction interval. A point estimate of annual cost is of limited use to a homeowner deciding whether to install a heat pump; an interval that genuinely contains the realised cost four times out of five would support informed decision-making in a way that headline figures do not. Calibration in this sense is the central claim. A model whose 80% interval contains the realised value 24% of the time is not a probabilistic forecaster in any useful sense; it is a point estimator surrounded by uninformative error bars. The principle that interval forecasts must be evaluated on both calibration and sharpness — and that calibration must come first — is well established in the probabilistic forecasting literature [3].

The calibration evaluation reported here was designed to test whether the v1 model's intervals are honest. The evaluation was pre-registered before any metric was computed, with a methodology document committed at hash `2a6d0bc` (subsequently amended at hash `6b1a3ab` for a pre-evaluation physical-validity filter on heat-loss values). Decision rules, claim-mapping constraints, and the boundary of public claims were fixed in writing before the evaluation ran. The pre-registration is documented in full at `docs/CALIBRATION_METHODOLOGY.md` in the project repository.

The model code was developed by the author over the months preceding the evaluation. Reference-case tests against a published account of the Twentyman installation in Cumbria [4] (annual heat output approximately 15,000 kWh, SPF 3.28) were used during development to anchor demand magnitudes, alongside a 91-test unit suite covering individual components: the Carnot-based COP curve, the heat-loss coefficient derivation from MCS inputs, the heating-degree-day demand calculation, the domestic-hot-water demand formula, the Monte Carlo draw generation, and the tariff-to-cost conversion. All 91 tests passed at the model code commit hash recorded for the evaluation (`957dd27`).

The evaluation reported here is independent of the test suite and the reference cases. It tests the model against 303 well-monitored UK heat pump installations submitted to the HeatpumpMonitor.org open dataset [5], each with at least one complete year of measured electricity and heat data and at least 90% data quality on both meters. HeatpumpMonitor.org is an OpenEnergyMonitor community initiative for sharing real-world heat pump performance data, with over 600 systems contributing at the time of evaluation; the dataset is openly available via a public API. The methodology, dataset, and evaluation script are designed to be reproducible: the dataset snapshot is committed to the project repository, the random seed is recorded in the report preamble, the climate cache is reusable across runs, and the seven-run ablation completes in approximately five minutes from a populated cache on a single workstation.

## 3. Methodology



The full pre-registered methodology is documented at `docs/CALIBRATION_METHODOLOGY.md` in the project repository, committed at hash `6b1a3ab`. This section summarises the methodology's structure; the reader is referred to the methodology document for the operative definitions, decision rules, and claim-mapping constraints.



The methodology defines four research questions, a seven-run input ablation, dataset inclusion criteria with eight filter stages, per-system input handling rules, an aggregate-metrics specification covering location, coverage, sharpness, and probabilistic skill, and pre-committed decision thresholds with associated consequences.



The seven runs are labelled A-full, A-subset, B, C, D, E, and F. They differ along three input dimensions: the heat-loss coefficient (MCS-declared versus measured), the indoor temperature (MCS-declared or default versus measured), and the SCOP (realised SPF used as oracle versus a fixed 3.5 generic proxy). Run B isolates the demand-side model under accurate inputs: measured heat loss, measured indoor temperature, and realised SPF used as oracle SCOP. Run F is the realistic-user end-to-end run: MCS-declared heat loss, user-declared or default indoor temperature, fixed 3.5 SCOP. Runs A-full and A-subset are paired baselines. Runs C, D, and E isolate the conditional effect of substituting one input at a time.



The validation gate for Run B requires all three of: coverage of the 80% interval ≥ 75%, MAPE ≤ 12%, and median interval width ≤ 50% of median realised electricity. Failure on any one of these three triggers the consequence stated in section 7.1 of the methodology: halt v1 product positioning until the failing component is investigated. Run F has a separate viability gate: coverage ≥ 60% AND MAPE ≤ 25%.



The methodology fixes a claim-mapping table of six allowed public claims, each tied to a specific evidence requirement. Claims not on the list are not supported by this evaluation regardless of what the numbers show. The intent of this table is to prevent post-hoc cherry-picking of findings; whatever the evaluation produces, only the pre-mapped claims can be defended publicly.



The methodology document also fixes the random seed for reproducibility, defines the per-case seed scheme (`case_seed = random_seed * 1000 + system_id` to prevent collision between adjacent system IDs' three internal sub-seeds), and specifies that the same case seed is used across all seven runs so that paired comparisons are not contaminated by sampling noise.



### 3.1 Metrics definitions

The aggregate metrics reported in section 5 are defined as follows. Let $y_i$ denote the realised annual electricity for case $i$, $\hat{y}_i$ the model's median Monte Carlo draw (p50) for case $i$, and $F_i$ the empirical cumulative distribution function of the model's 1,000-draw Monte Carlo predictions for case $i$. Let $n$ denote the number of cases in the relevant subset.

**Mean Absolute Percentage Error (MAPE):**

$$\mathrm{MAPE} = \frac{1}{n} \sum_{i=1}^{n} \left| \frac{y_i - \hat{y}_i}{y_i} \right|$$

where $\hat{y}_i$ is the median (p50) of the Monte Carlo predictions for case $i$.

**Median Absolute Percentage Error (MdAPE)** is the median rather than the mean of the per-case absolute percentage errors. **Trimmed MAPE** is computed after dropping the top and bottom 5% of per-case absolute percentage errors.

**Median signed error** is the median of the per-case signed percentage errors $(\hat{y}_i - y_i)/y_i$.

**Coverage** of the 80% prediction interval is the proportion of cases for which the realised value falls between the model's p10 and p90:

$$\mathrm{Coverage} = \frac{1}{n} \sum_{i=1}^{n} \mathbb{1}\left[ p_{10,i} \leq y_i \leq p_{90,i} \right]$$

**Median interval width** is reported as a percentage of median realised electricity:

$$\mathrm{Width\%} = \frac{\mathrm{median}_i(p_{90,i} - p_{10,i})}{\mathrm{median}_i(y_i)} \times 100$$

**Continuous Ranked Probability Score (CRPS)** for case $i$ is computed from the empirical CDF $F_i$ as:

$$\mathrm{CRPS}(F_i, y_i) = \int_{-\infty}^{\infty} \left[ F_i(x) - \mathbb{1}_{x \geq y_i} \right]^2 \, dx$$

Mean CRPS across cases is reported in kWh (the units of $y_i$). The implementation uses the `properscoring` library's `crps_ensemble` against the 1,000 retained Monte Carlo draws per case.

**Wilson 95% confidence interval** for the coverage proportion uses the standard score-interval form with continuity correction omitted, as implemented in `statsmodels.stats.proportion.proportion_confint(method='wilson')`. The interval assumes independent Bernoulli trials across cases. The 303 cases are distinct geographic installations evaluated against a 20-winter typical climate; while modest spatial correlation in regional weather anomalies may exist, the use of long-run climatology rather than per-case monitoring-window weather makes the independence assumption defensible at the precision required by the validation thresholds.

---

## 4. Provenance and Reproducibility



The evaluation reported in this document is fully reproducible from the project repository. The provenance is recorded as follows.



**Methodology document commit hash:** `6b1a3ab523c032944bbc88202c57be7ef5b44baa`



**Model code commit hash at evaluation time:** `0301661f2affdb572a011f90900dccf088321278` (tag `calibration-eval-model-code` was set at the preceding commit `957dd27a27ba7a60cf772a76016102b17e8589f6` covering the forecast engine in `backend/app/`; the `0301661` commit is the build-script amendment for the physical-validity filter and does not modify the forecast engine).



**Evaluation timestamp:** 2026-06-10T13:41:05Z



**Random seed:** `20260609` (per-case seed scheme: `case_seed = random_seed * 1000 + system_id`)



**Dataset snapshot:** HeatpumpMonitor.org systems and stats fetched on 9 June 2026; see `data/heatpumpmonitor/README.md` for the snapshot\'s availability status in the project repository.



The dataset inclusion criteria from methodology section 3.2 reduced the source set of 765 systems to 303 eligible cases. The drop counts are recorded in `data/heatpumpmonitor/eval_filter_report.txt` and reproduced here:



| Filter stage | Cases dropped |
|---|---:|
| Total systems | 765 |
| Missing stats entry | −1 |
| Less than 365 days of data | −282 |
| `data_flag` set | −27 |
| Missing essential MCS fields | 0 |
| MCS field outside physical range (heat_loss 0.5–50 kW) | −70 |
| Quality elec/heat < 90% | −67 |
| SPF null or ≤ 1.5 | 0 |
| Cooling or immersion backup > 5% of total electricity | −15 |
| **Surviving evaluation cases** | **303** |



Of the 303 eligible cases, 151 are in the measured-input subset (both measured heat loss and measured indoor temperature available), and 262 are in the strict-zero cooling/immersion subset (used for the section 5.5 sensitivity analysis).



**Reproduction.** From a clean checkout of the project repository at the model code commit hash above, the evaluation reproduces with the following commands on a workstation with the dependencies pinned in `backend/pyproject.toml`:



```powershell
backend.venv\Scripts\python.exe backend\scripts\build_eval_dataset.py `
  --use-frozen-snapshot --snapshot-date 20260609
backend.venv\Scripts\python.exe backend\scripts\prefetch_climate_cache.py
backend.venv\Scripts\python.exe backend\scripts\run_calibration_eval.py
```



The climate cache (`data/heatpumpmonitor/climate_cache/`) contains 306 parquet files, one per unique latitude-longitude pair to four decimal places, fetched from Open-Meteo's historical archive [6]. The cache is reused across the seven runs per case and across re-runs of the evaluator; only the first fetch hits the network. Two locations required a one-off patient retry path (`51.0748,1.1757` and `51.4081,-0.6330`) during initial population owing to Open-Meteo rate limiting; subsequent reproductions can use the committed cache directly.



Total wall-clock time for the evaluator on a populated cache is approximately 4.5 minutes for 303 cases across all seven runs, plus the DHW occupancy sensitivity analysis (5 occupant counts × 151 measured-input cases). The output artefacts written to `data/heatpumpmonitor/` are:



| Artefact | Contents |
|---|---|
| `calibration_predictions.json` | Per-case per-run predictions with 1,000 retained draws per record (\~42 MB) |
| `calibration_errors.csv` | Flat per-case CSV with seven runs' headline metrics and case metadata |
| `calibration_report.md` | Machine-generated report matching the structure specified in methodology section 10 |



The complete project repository, including the methodology document, evaluation scripts, climate cache, and this report, is available at https://github.com/bernardashiley/heat_pump_project. The HeatpumpMonitor.org dataset snapshot used in this evaluation is not redistributed in the repository owing to absence of an explicit dataset redistribution licence; the data is openly fetchable from HeatpumpMonitor.org via the included fetch script, and the exact 9 June 2026 snapshot used in this report may be obtained by contacting the author (see section 12.1). Reproduction details are in `data/heatpumpmonitor/README.md`.



---



## 5. Headline Results



### 5.1 Aggregate metrics, seven runs



The seven runs produced the following aggregate metrics on the eligible set (303 cases) and the measured-input subset (151 cases), per methodology section 5.2.



| Run | Cases | Coverage % | Wilson 95% CI | MAPE % | MdAPE % | Trimmed MAPE % | Median signed error % | Median width % | Mean CRPS |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| A-full | 303 | 39.6 | 34.3–45.2 | 26.0 | 23.4 | 24.8 | −13.7 | 31.8 | 877.6 |
| A-subset | 151 | 41.1 | 33.5–49.0 | 26.9 | 23.1 | 25.6 | −10.4 | 32.1 | 850.0 |
| B | 151 | 23.8 | 17.7–31.2 | 29.1 | 30.2 | 29.0 | −29.1 | 24.8 | 1044.7 |
| C | 151 | 35.1 | 27.9–43.0 | 24.3 | 23.7 | 24.2 | −19.9 | 27.9 | 869.8 |
| D | 151 | 41.7 | 34.2–49.7 | 28.2 | 22.9 | 27.0 | −9.8 | 32.6 | 874.3 |
| E | 151 | 21.2 | 15.4–28.4 | 30.3 | 31.7 | 30.3 | −31.5 | 23.7 | 1079.5 |
| F | 303 | 47.2 | 41.6–52.8 | 24.3 | 18.3 | 23.1 | −5.6 | 34.8 | 755.0 |



Across all seven runs, the model's coverage of its own 80% interval ranged from 21.2% to 47.2%. Against the 80% nominal target, every run is severely under-covered. The MAPE on the eligible set is in the 24–30% band; on the measured-input subset where five of the seven runs operate, MAPE is also 24–30%. Median signed errors are negative for every run, indicating systematic underprediction; the magnitude ranges from −5.6% (Run F) to −31.5% (Run E).



The Wilson 95% confidence intervals on the coverage statistic do not overlap with 80% nominal for any run. The lowest 95% CI upper bound is Run E's 28.4%, the highest is Run F's 52.8%. No run is statistically consistent with calibrated 80% intervals at the sample sizes available.



### 5.2 Permitted comparisons



Methodology section 2 specifies five permitted comparisons. Each comparison is a coverage delta between two runs with the second-run cases held constant.



| Comparison | Coverage delta | Methodology threshold | Result |
|---|---:|---|---|
| B − A-subset | −17.2 pp | ≥ 30 pp means HLC calibration is the highest-impact v2 feature | Below threshold; not supported |
| B − D | −17.9 pp | ≥ 20 pp means MCS HLC substitution materially degrades accuracy | Negative delta; substitution does not degrade |
| B − E | +2.6 pp | ≥ 15 pp means indoor-temperature substitution materially degrades accuracy | Below threshold; not supported |
| B − C | −11.3 pp | ≥ 20 pp means fixed generic SCOP proxy is inadequate | Negative delta; proxy does not degrade |
| F vs A-full | +7.6 pp | (Diagnostic) F is the realistic-user run, A-full is the oracle-SPF baseline | F has higher coverage than A-full |



Three of the five permitted deltas are negative. The interpretation is that the substitutions that the methodology hypothesised would *degrade* accuracy — replacing measured HLC with MCS HLC, replacing realised SPF with the 3.5 proxy — actually *improve* coverage. The mechanism, identified in the diagnostic investigation reported in section 7 of this document, is that the v1 model systematically underpredicts annual electricity. Any input substitution that raises predicted electricity moves predictions closer to realised values; any substitution that lowers predicted electricity moves them further away. MCS HLC values are typically higher than measured values (see comparative figures in the dataset, e.g. system 1: MCS 9,500 W vs measured 5,630 W), and a fixed 3.5 SCOP is lower than the dataset median realised SPF of approximately 3.7, so both substitutions raise predicted electricity and improve apparent coverage.



The B − E delta of +2.6 pp is the one comparison where the substitution behaves in the methodology-predicted direction (B with measured indoor temperature has slightly better coverage than E with declared or default), but the magnitude is below the methodology threshold of 15 pp for materiality.



### 5.3 Run B validation outcome



Methodology section 7.1 specifies a three-metric gate for Run B. The metric is the demand-side model under oracle inputs: measured HLC, measured indoor temperature, and realised SPF used as SCOP. Validation requires all three thresholds to be in the Validated band.



| Metric | Value | Band per section 7.1 |
|---|---:|---|
| Coverage of 80% interval | 23.8% | Inadequate (threshold < 60%) |
| MAPE | 29.1% | Inadequate (threshold > 20%) |
| Median interval width as % of median realised | 24.8% | Validated (threshold ≤ 50%) |



Two of three metrics fall in the Inadequate band. Per the pre-committed consequence stated in section 7.1: **halt v1 product positioning until the failing component is investigated.**



The sharpness metric is Validated. The intervals are narrow — narrower, in fact, than the validation band requires. The failure is not that the intervals are too wide; it is that they are in the wrong place. The combination of validated sharpness and inadequate coverage is the worst-case combination for a probabilistic forecaster: confident and wrong.



### 5.4 Run F validation outcome



Methodology section 7.4 specifies a viability gate for Run F as the true realistic-user end-to-end run.



| Metric | Value | Threshold | Result |
|---|---:|---|---|
| Coverage of 80% interval | 47.2% | ≥ 60% | Below threshold |
| MAPE | 24.3% | ≤ 25% | At threshold |



Run F fails the coverage criterion of section 7.4. Per the pre-committed consequence: **the realistic-user product is not viable in its current form; calibration data must be required as a gating input.**



Run F is the highest-coverage run of the seven. This is not a feature of the model; it is a consequence of two compensating biases acting in the same direction (the underprediction defect identified in section 7 below), discussed in section 5.2 above.



### 5.5 PIT distributions



The Probability Integral Transform distributions for the seven runs are presented below. Each row is one run's PIT histogram across 10 equal-width bins from 0 to 1. A well-calibrated probabilistic forecaster produces a flat (uniform) PIT distribution. The Kolmogorov–Smirnov p-value against uniform is computed for each run.



| Run | KS p-value | PIT bins (0.0 to 1.0, 10 equal-width bins) |
|---|---:|---|
| A-full | 0.0000 | 0.182, 0.017, 0.046, 0.020, 0.030, 0.059, 0.043, 0.089, 0.092, 0.422 |
| A-subset | 0.0000 | 0.192, 0.020, 0.053, 0.013, 0.040, 0.046, 0.053, 0.099, 0.086, 0.397 |
| B | 0.0000 | 0.033, 0.013, 0.007, 0.007, 0.026, 0.020, 0.020, 0.066, 0.079, 0.728 |
| C | 0.0000 | 0.093, 0.000, 0.026, 0.026, 0.026, 0.053, 0.046, 0.060, 0.113, 0.556 |
| D | 0.0000 | 0.205, 0.060, 0.013, 0.040, 0.053, 0.020, 0.053, 0.079, 0.099, 0.377 |
| E | 0.0000 | 0.026, 0.000, 0.007, 0.000, 0.013, 0.013, 0.033, 0.046, 0.099, 0.762 |
| F | 0.0000 | 0.238, 0.066, 0.066, 0.020, 0.046, 0.036, 0.050, 0.092, 0.096, 0.290 |



All seven KS p-values are reported as 0.0000 — the PIT distributions are not statistically distinguishable from uniform at any conventional significance level. The one-sample Kolmogorov–Smirnov test was applied against the uniform reference $U(0,1)$. At the sample sizes available (151 for measured-input runs, 303 for eligible-set runs), the KS test is highly powered and would detect even modest departures from uniformity. The test is reported here not as evidence in its own right but as formalisation of the structural deviation that is visually obvious in the PIT bin arrays below. The most diagnostic feature is the rightmost bin. For Run B, the PIT bin covering realised values above the model's 90th percentile contains 72.8% of cases. For Run E it is 76.2%. For the eligible-set runs (A-full, F), the rightmost bin contains 42.2% and 29.0% respectively. The leftmost bin contains a smaller but non-trivial fraction (18.2% for A-full, 23.8% for F), indicating a secondary cluster of overpredicted cases — but the dominant signal across all runs is that the model places its 90th percentile *below* the realised value for the majority of cases.



This is the PIT signature of systematic underprediction.



---



## 6. Pre-registered Claim Mapping Outcomes



Methodology section 10 fixes a table of six allowed public claims, each tied to a specific evidence threshold. Claims not on this list are not supported by this evaluation regardless of what the numbers show. The intent is to prevent post-hoc selection of findings: whatever the results, only the pre-mapped claims may be defended publicly, and only when their evidence threshold is met.



The six claims and their evidence outcomes from the evaluation reported in section 5 are as follows.



| # | Allowed claim | Evidence requirement | Observed | Supported? |
|---|---|---|---|---|
| 1 | Demand-side model is validated conditional on measured HLC, measured indoor temperature, and realised SPF | Run B passes section 7.1 (all three metrics in Validated band) | Two of three metrics in Inadequate band | No |
| 2 | MCS HLC substitution materially degrades accuracy in the measured-input subset | B − D coverage delta ≥ 20 pp | B − D = −17.9 pp | No |
| 3 | Indoor-temperature substitution materially degrades accuracy in the measured-input subset | B − E coverage delta ≥ 15 pp | B − E = +2.6 pp | No |
| 4 | Fixed generic SCOP proxy is inadequate | B − C coverage delta ≥ 20 pp | B − C = −11.3 pp | No |
| 5 | Realistic-user product is viable with documented uncertainty disclosure | Run F passes section 7.4 (coverage ≥ 60% AND MAPE ≤ 25%) | Coverage 47.2%, below threshold | No |
| 6 | Calibration data is the highest-impact v2 feature | B − A-subset coverage delta ≥ 30 pp | B − A-subset = −17.2 pp | No |



None of the six pre-registered claims is supported by the evidence. The evaluation produced no publicly defensible positive claim about the v1 model's calibration, the dominant source of error in its inputs, the viability of the realistic-user product, or the priority of v2 features.



This outcome is itself the finding. The methodology was designed so that the absence of supported claims is informative rather than a null result. Three observations follow from the unsupported claim mapping.



**First**, the demand-side model fails its primary validation gate (claim 1). The v1 model, given the most accurate inputs available, does not produce calibrated 80% intervals at the methodology's tolerance.



**Second**, the four input-substitution comparisons (claims 2, 3, 4, 6) do not behave in the directions the methodology hypothesised. The methodology's hypothesis was that measured inputs would outperform MCS or default inputs, and that the magnitude of the improvement would identify which input is the dominant error source. The evidence shows that three of the four input substitutions improve coverage rather than degrade it. This is not consistent with any input being the dominant error source; it is consistent with the model having a structural bias that some input substitutions accidentally compensate for. The diagnostic investigation reported in section 7 of this document identifies what that bias is.



**Third**, the realistic-user end-to-end run (claim 5) fails the viability gate even though it is the highest-coverage run of the seven. The model's best-performing configuration is still substantially below the methodology's viability threshold.



The pre-registered claim mapping permits no positive claim. The negative claims — that none of the six conditions hold — are themselves defensible because the methodology fixed them in writing before the evaluation. Those negative claims appear in section 9 of this document under "what this report supports being said publicly."



---



## 7. Diagnostic Finding



### 7.1 The defect



The v1 model fetches climate data for the months October through March only, computes daily heat demand on those days, and reports the resulting total as annual electricity. The defect has three components:



1\. **Space heating demand.** The climate fetcher (`backend/app/forecast/climate.py`, function `fetch_winter_daily_mean_temperatures`) returns 182 daily outdoor temperature values for each of the 20 historical winters, covering October through March of each winter. The demand model (`backend/app/forecast/demand.py`) computes daily space heating energy on each of those days using a heating-degree-day formula with base temperature 15.5 °C. There is no equivalent computation for the months April through September.



2\. **Domestic hot water demand.** Annual DHW demand is computed once from the occupancy, cylinder volume, setpoint, and flow temperature, producing a single annual figure (e.g. 3,394 kWh/year for a 4-occupant household). This annual figure is then divided by 365 to produce a daily DHW figure and applied uniformly across the days for which climate data exists. Because climate data only exists for 182 days, only 182/365 ≈ 50% of the annual DHW demand is included in the model's output.



3\. **Aggregation and labelling.** The Monte Carlo orchestrator (`backend/app/forecast/monte_carlo.py`) sums daily electricity demand across each of the 20 winter realisations and presents the resulting per-winter sum as the case's annual electricity distribution. The variable is named `annual_total_by_winter` in the code. The user-facing forecast labels the p10, p50, and p90 percentiles of this distribution as "annual electricity consumption."



The combined effect: the model computes Oct–Mar space heating plus approximately half of annual DHW, and reports the total as annual electricity. The remaining demand — Apr–Sep shoulder-season heating, and the missing half of DHW — is omitted entirely.



### 7.2 Why this defect was not caught earlier



The defect was not visible to the v1 development process. The reasons are documentable.



The 91-test unit suite tests internal consistency between components. The COP test verifies that the Carnot formula is correctly implemented; the demand test verifies that the heating-degree-day formula produces the expected output for a given climate series; the Monte Carlo test verifies that the percentile arithmetic is correct. None of these tests compares the model's output against a known external annual demand value. They cannot detect a structural defect in the demand-period definition because they accept the model's definition of what constitutes "the period to sum over" as a given.



The reference-case anchors used during development have the same limitation. The Twentyman reference case [4] provides a daily-kWh figure (12.68 kWh/day) and an annual heat output (\~15,000 kWh). The v1 model's output for the Twentyman inputs lands within ±15% of these figures when the model's internal daily-kWh figure is the comparison target. The article's annual figure is approximately 4,629 kWh of electricity (15,000 kWh of heat ÷ SPF of 3.28 ≈ 4,573 kWh, approximately matching the article's stated electricity total). The v1 model produces approximately 2,800 kWh for the Twentyman inputs when correctly configured to the article's HLC. This is roughly half of the article's electricity total — exactly the signature of the structural defect — but the reference case test was set up to compare against the daily-kWh figure (12.68 kWh/day on the Oct–Mar period), which the model matches because the model and the reference case both restrict to that period. The test passed by virtue of comparing winter-only against winter-only.



The four manual blind predictions made during development against HeatpumpMonitor cases showed errors of approximately 20–70%, with predictions generally below the realised annual values. These errors were attributed at the time to MCS input quality (the MCS heat-loss figures being unreliable), not to a structural defect in the model. The attribution was wrong. The errors were the structural defect.



The defect was only visible to the calibration evaluation reported here because the calibration evaluation tested the model against 303 systems' actual annual electricity totals, not against the model's own internal consistency or against a single reference figure that shared the same period definition.



### 7.3 Numerical evidence



The structural defect's mechanism predicts a specific underprediction magnitude. The space heating contribution can be estimated from UK heating-degree-day data: at a base temperature of 15.5 °C, roughly 80% of annual HDDs fall in the October–March window for a typical UK location [7]. The 20% of annual HDDs in April–September are entirely omitted from the v1 forecast. This alone produces an expected underprediction of approximately 20% on the space heating component.



The DHW contribution doubles the effect. With DHW divided by 365 and applied only to 182 days, approximately half of annual DHW is omitted. For a system where DHW is 15–20% of annual electricity (typical for a UK heat pump installation), this contributes a further 7–10% underprediction on the total.



The combined expected underprediction is therefore approximately 27–30% on a typical case. The observed median signed error on Run B is −29.1%. The match between the expected and observed magnitudes is the principal numerical evidence that this defect is the dominant explanation for the v1 model's failure.



A diagnostic case computation was performed on system 429 (realised annual electricity 9,857 kWh, B p50 prediction 3,648 kWh, error −63.0%). The model's p50 prediction was recomputed at three base temperatures while holding the demand-period defect in place: at base temperature 15.5 °C the prediction is approximately 3,568 kWh; at 18.0 °C, 4,410 kWh; at 20.0 °C, 5,083 kWh. None of these closes the gap to the realised 9,857 kWh. The base temperature is not the dominant lever. The dominant lever is that the model is not computing demand on Apr–Sep days at all.



The PIT distribution evidence is consistent. The signature of systematic underprediction is heavy mass in the rightmost PIT bin (cases where the realised value exceeds the model's 90th percentile). Run B shows 72.8% of cases in this bin (section 5.5). This is the empirical fingerprint of a model that places its 90th percentile substantially below the realised value for the majority of cases — exactly what a structurally winter-only simulator would produce when tested against annual realised values.



### 7.4 Status of the defect



The defect is a structural error in the v1 model's demand-period definition. It is not a parameter that needs tuning, a hyperparameter that needs cross-validation, or a feature that needs adding. It is a missing six months of simulation in a model that reports its output as annual.



The defect is fixable. The fix requires extending the climate fetcher to return all 365 days of each year, updating the demand model to compute on all 365 days, and removing the implicit 182/365 truncation of DHW. The scope of the fix is small (engineering hours, not weeks) and does not require methodological changes to the calibration framework.



The fix is part of the planned v1.1 evaluation reported in section 10 of this document. The v1.1 evaluation is pre-registered separately and includes the demand-period fix alongside two other planned improvements: propagation of DHW occupancy uncertainty, and required indoor-temperature input on the frontend. The three improvements are evaluated as an ablation so that each fix's individual contribution to the v1.1 metrics is attributable.



---



## 8. Mechanisms Considered and Rejected



Before the structural defect described in section 7 was identified, three alternative mechanisms were investigated as candidate explanations for the model's systematic underprediction. Each was tested against the available evidence and rejected as the dominant explanation. They are documented here because the diagnostic process is part of the report's evidence base, and because each rejected hypothesis identifies a model parameter that is *not* the primary lever for v1.1.



### 8.1 Base temperature



**Hypothesis.** The model uses a fixed base temperature `t_base_c = 15.5 °C` in the heating-degree-day demand calculation. If real UK homes effectively heat at a higher balance temperature — for example because of lower assumed solar gains, lower internal gains from occupants and appliances, or higher comfort thresholds in poorly insulated properties — the model would under-count heating demand by missing days when the outdoor temperature is between 15.5 °C and the true balance temperature.



**Test.** System 429 was used as a diagnostic case (realised annual electricity 9,857 kWh, Run B p50 prediction 3,648 kWh, error −63.0%). The Run B configuration uses measured HLC (7,500 W/K), measured indoor temperature (22.9 °C), and realised SPF (3.49) as oracle SCOP. The model's space-heating-only electricity prediction was recomputed at three base temperatures:



| `t_base_c` | Predicted SH electricity (kWh) |
|---:|---:|
| 15.5 | \~3,568 |
| 18.0 | \~4,410 |
| 20.0 | \~5,083 |



Raising the base temperature from 15.5 °C to 20.0 °C increases the prediction by approximately 1,500 kWh. The gap to the realised value (9,857 kWh) remains approximately 4,800 kWh — about half of the realised electricity unaccounted for. Even at an implausibly high base temperature of 20.0 °C (which would mean the building heats whenever outdoor temperature falls below indoor temperature, i.e. essentially all year), the model cannot reach the realised value.



**Conclusion.** Base temperature is a contributing factor but not the dominant lever. It is not consistent with the magnitude of underprediction observed. Rejected as the primary explanation.



### 8.2 DHW demand formula



**Hypothesis.** The model computes annual DHW heat demand from occupancy, cylinder volume, setpoint, and flow temperature using a standard formula. If the formula systematically underestimates the actual DHW heat demand for typical UK households, the resulting annual electricity figure would be biased low. The DHW occupancy sensitivity (methodology section 5.4) is consistent with DHW being a meaningful contributor — Run B coverage shifts from 14.6% at occupants=1 to 35.1% at occupants=5, with corresponding MAPE shifts.



**Test.** The model's annual DHW heat demand was computed for system 429 (typical household assumption) at the methodology default of 3 occupants and at 4 occupants, holding cylinder volume, setpoint, and flow temperature at their defaults:



| Occupants | Annual DHW heat demand (kWh) |
|---:|---:|
| 3 | \~2,545 |
| 4 | \~3,394 |



The 4-occupant figure (3,394 kWh) falls within the UK industry rule-of-thumb range of 2,500–3,500 kWh/year for a 4-person household with electric water heating. The DHW heat demand formula is producing values consistent with external reference points.



The DHW occupancy sensitivity table is therefore not evidence that the formula is wrong; it is evidence that DHW magnitude matters and that the 3-occupant default is on the low side. Approximately 850 kWh/year separates a 3-occupant from a 4-occupant assumption — about 8% of system 429's annual electricity. This is a meaningful contribution but not the dominant one.



**Conclusion.** The DHW formula itself is correctly producing values in the expected magnitude range. The 3-occupant default is too low for the typical HeatpumpMonitor.org household, but correcting it would close \~10% of the gap, not the full \~30%. Rejected as the primary explanation.



The DHW occupancy sensitivity finding is, however, a legitimate methodology section 7.8 outcome in its own right: per the methodology, MAPE movement greater than 10 percentage points across the {1, 2, 3, 4, 5} occupancy range triggers the consequence that "occupancy is critical and v1 frontend must require it." The observed MAPE movement is 11.4 percentage points. This methodology decision is recorded as a legitimate finding of the evaluation and propagates into the v1.1 ablation design as a required user input.



### 8.3 Climate window mismatch with monitoring period



**Hypothesis.** The model uses a 20-winter typical climate (October 2006 through March 2026). Each system in the evaluation dataset was monitored over a different actual time window — some systems contributed data during unusually mild winters, others during unusually harsh ones. If the monitoring window's climate differed systematically from the 20-winter typical, the realised electricity figures could appear biased against the model. Methodology section 6.5 notes this contributes approximately ±5% noise per case.



**Test.** This hypothesis was not directly tested against per-case monitoring windows because the secondary matched-window diagnostic described in methodology section 4.1 was deferred to v2 — the script infrastructure to fetch climate for arbitrary monitoring windows exists but the matched-window evaluation was not run for v1. Instead, the climate window mismatch is bounded by reasoning about UK inter-annual variability: typical UK heating-degree-day totals vary by ±5% around a 20-winter mean. This bounds the magnitude of error this mechanism can contribute.



**Conclusion.** Climate window mismatch with monitoring period cannot explain a systematic −29% bias on the measured-input subset. The mechanism's maximum contribution is bounded at approximately ±5% per case and is not directional — some monitoring windows would be warmer than the 20-winter mean, others colder, with no expectation of systematic underprediction across the dataset. Rejected as the primary explanation.



### 8.4 Summary



| Mechanism | Magnitude of effect | Direction | Verdict |
|---|---|---|---|
| Base temperature too low | \~10–15% per case | Underprediction | Contributing factor |
| DHW occupancy default too low | \~5–10% per case | Underprediction | Contributing factor |
| Climate window mismatch | ±5% per case | No systematic direction | Bounded noise, not dominant |
| **Demand-period structural defect (section 7)** | **\~27–30% per case** | **Systematic underprediction** | **Dominant mechanism** |



The demand-period defect identified in section 7 is the only mechanism consistent with both the observed magnitude of underprediction (median signed error −29.1% on Run B) and its systematic direction (heavy mass in the rightmost PIT bin across all runs, no compensating cluster of overprediction beyond what would be expected from a few outliers). The contributing factors named in section 8.1 and section 8.2 are real but secondary; the v1.1 ablation reported in section 10 of this document evaluates each candidate fix's individual contribution.



---



## 9. Implications



The evaluation's findings constrain what can and cannot be claimed about the v1 model. The constraints are pre-committed by methodology section 9 and section 10 and are restated here for the report's specific evidence.



### 9.1 What the v1 model can be used for



Nothing that requires calibrated annual electricity predictions. The 80% prediction interval contains the realised annual electricity for approximately one in four well-monitored UK heat pump installations under the most favourable input conditions tested. This is incompatible with any decision support, financial planning, or comparative analysis that depends on the interval's nominal coverage being honest.



The v1 model can be used for:



- Demonstration of the modelling framework's component architecture (the COP curve, the demand-period decomposition, the Monte Carlo orchestration, the tariff application) where the component arithmetic is correct in isolation, as verified by the 91-test unit suite.

- Reproduction of the structural defect documented here, by anyone wishing to verify the evaluation's findings.

- Comparison against the v1.1 model in section 10 of this document, where v1 serves as the baseline against which v1.1 improvements are evaluated.



The v1 model cannot be used for:



- Pre-purchase decisions by homeowners considering a heat pump installation.

- Financial projections of running cost at any time horizon.

- Comparative analysis across heat pump models, manufacturers, or installation configurations.

- Any institutional or commercial deployment.



### 9.2 What this report supports being said publicly



Six negative claims are defensible because they correspond to the pre-registered claim mapping outcomes in section 6 of this document, and because the methodology fixed the evidence requirements before the evaluation.



| # | Defensible negative claim |
|---|---|
| 1 | The v1 model's demand-side performance under oracle inputs (measured HLC, measured indoor temperature, realised SPF) does not meet the pre-registered validation threshold for 80% interval calibration. |
| 2 | MCS heat-loss substitution does not materially degrade accuracy in the measured-input subset; the substitution produces *better* coverage in the v1 model owing to compensating biases. |
| 3 | Indoor-temperature substitution does not materially degrade accuracy in the measured-input subset. |
| 4 | A fixed 3.5 SCOP proxy does not degrade accuracy relative to using realised SPF; in the v1 model the proxy produces better coverage owing to compensating biases. |
| 5 | The realistic-user end-to-end forecast (MCS HLC, declared or default indoor temperature, fixed 3.5 SCOP) does not meet the pre-registered viability threshold of 60% coverage. |
| 6 | Calibration data — measured heat loss from past consumption — is not the highest-impact v2 feature based on this evaluation. The dominant error source is the structural defect documented in section 7. |



A seventh statement is defensible because the methodology section 7.8 decision rule was met:



7\. The 3-occupant DHW assumption is inadequate for the typical HeatpumpMonitor.org household; a v1.1 or v2 product must elicit occupancy from the user.



These seven statements exhaust what the evaluation supports being said publicly about the v1 model. Any claim that the v1 model is "approximately correct" or "needs only refinement" or "produces useful forecasts with documented uncertainty" is not supported by this evaluation.



### 9.3 What this report does not support being said



The report does not support any positive claim about the v1 model's predictive accuracy, the calibration of its prediction intervals, or the readiness of the realistic-user product. It does not support any claim that one input (HLC, indoor temperature, SCOP) is the dominant error source, because the structural defect dominates over all input-substitution effects.



The report does not support claims about the v1.1 model, the v2 model, or any model other than the v1 specified at the commit hashes in section 4. The v1.1 ablation evaluation is planned but not yet executed; section 10 of this document describes what will be tested and under what pre-registration, not what has been found.



The report does not support generalisation beyond well-monitored UK heat pump installations submitted to a community open-data platform. Methodology section 6.1 fixes this boundary in writing; this report inherits it. The HeatpumpMonitor.org population skews toward technically engaged owners of well-installed systems and is not representative of the UK heat pump fleet.



The report does not support any claim that the calibration methodology itself failed, was too strict, or produced artefactual negative findings. The methodology produced the result it was designed to produce: when the model under test does not meet the pre-registered thresholds, the result is that the model does not meet them. The methodology's correct operation in producing negative findings is itself part of its value.



### 9.4 Implication for the project



The v1 model is withdrawn from any public-facing deployment posture. The project continues in two parallel tracks: a v1.1 implementation that addresses the structural defect alongside two other planned improvements (section 10 of this document), and a v2 methodology document that incorporates the lessons of v1 (the importance of testing against external annual totals, the value of pre-registered claim mapping in preventing post-hoc rationalisation, the necessity of bounded physical-validity filters on dataset inclusion criteria) into its design.



This report is the v1 calibration artefact. It is published under Odwira \& Whitehall as the documented outcome of the v1 evaluation. It is intended to be read in conjunction with the methodology document at `docs/CALIBRATION_METHODOLOGY.md` and, when complete, the v1.1 evaluation report.



---



## 10. V1.1 Ablation: Planned Work



The v1.1 evaluation is pre-registered separately and will be reported as a separate artefact. This section describes what v1.1 will test and how. No v1.1 results are reported here; the v1.1 calibration report will be published under Odwira \& Whitehall when the evaluation is complete.



### 10.1 Three planned changes to the v1 model



V1.1 implements three changes to the v1 model, each motivated by findings reported here.



**Change 1: Demand period extended from October–March to full year.** The structural defect documented in section 7 of this report — the climate fetcher, demand calculation, and DHW arithmetic all operating on 182 days instead of 365 — is corrected. The climate fetcher (`backend/app/forecast/climate.py`) is extended to return all 365 days of each year. The demand model (`backend/app/forecast/demand.py`) computes daily heating demand on all 365 days, with the heating-degree-day formula correctly returning zero on days when outdoor temperature exceeds the base temperature. The DHW model continues to apply daily DHW demand uniformly, but now across the full 365 days, removing the implicit truncation to \~50%.



**Change 2: DHW occupancy uncertainty propagated.** The 3-occupant default is replaced with a propagated uncertainty distribution. The mechanism is to be specified in the v1.1 methodology amendment: the candidate approach is to sample occupancy from a discrete distribution over {1, 2, 3, 4, 5} occupants per Monte Carlo draw, with the distribution either fixed at uniform or weighted by UK household composition statistics. This change is motivated by the methodology section 7.8 decision rule outcome reported in section 8.2 of this document: MAPE movement of 11.4 percentage points across the {1, 2, 3, 4, 5} range triggers the consequence that occupancy is critical.



**Change 3: Indoor temperature required as user input.** The v1 model accepts a user-declared indoor temperature with a default of 21 °C when not provided. V1.1 requires indoor temperature as a mandatory user input with no default fallback. The frontend change is out of scope of the model evaluation itself; the evaluation impact is that cases where indoor temperature is unavailable in the dataset are excluded from runs that previously relied on the default.



### 10.2 Ablation design



The three changes are evaluated as an ablation so that each fix's individual contribution to v1.1 metrics is attributable. Six model configurations are evaluated under the same methodology used for v1:



| Configuration | Demand period | DHW occupancy | Indoor temperature |
|---|---|---|---|
| v1 baseline (this report) | Oct–Mar | Fixed 3 | Declared or 21 °C default |
| v1.1a | Full year | Fixed 3 | Declared or 21 °C default |
| v1.1b | Oct–Mar | Propagated | Declared or 21 °C default |
| v1.1c | Oct–Mar | Fixed 3 | Required (case excluded if unavailable) |
| v1.1ab | Full year | Propagated | Declared or 21 °C default |
| v1.1abc | Full year | Propagated | Required |



The same seven-run input ablation (A-full, A-subset, B, C, D, E, F) is applied to each model configuration. The total evaluation comprises 6 × 7 = 42 (model, input) combinations, with the same case set, climate cache, random seed, and per-case seed scheme used in this report. Total computation is approximately 6 × 4.5 minutes ≈ 27 minutes on a populated cache.



The ablation enables specific attribution questions:



- v1.1a versus v1 baseline: marginal contribution of the demand-period fix in isolation.

- v1.1b versus v1 baseline: marginal contribution of DHW occupancy propagation in isolation.

- v1.1c versus v1 baseline: marginal contribution of requiring indoor temperature input in isolation.

- v1.1abc versus v1 baseline: combined effect of all three changes.

- v1.1abc versus the individual single-change configurations: identification of interaction effects between the three changes.



If v1.1abc passes the methodology section 7.1 validation gate on Run B (coverage ≥ 75%, MAPE ≤ 12%, median interval width ≤ 50% of median realised), the v1.1 product positioning is permitted at the level the gate authorises. If v1.1abc fails the gate, the ablation identifies which fixes contributed and which did not, providing diagnostic input for v2.



### 10.3 Pre-registration of v1.1



The v1.1 evaluation is pre-registered separately. The methodology amendments needed for v1.1 — chiefly the specification of the DHW occupancy distribution in Change 2, and the case-exclusion rule for Change 3 when indoor temperature is unavailable — are documented at `docs/CALIBRATION_METHODOLOGY_V1_1.md` in the project repository, committed before the v1.1 evaluation runs.



The v1.1 methodology inherits the v1 methodology unchanged in its core structure: the same seven-run input ablation, the same dataset, the same decision thresholds, the same claim-mapping table. The amendments are scoped narrowly to the three changes above.



If the v1.1 evaluation produces results that warrant new claims beyond the six pre-registered for v1, those claims will be added to the v1.1 methodology's claim-mapping table *before* the v1.1 evaluation runs, not after. This preserves the methodology's protection against post-hoc rationalisation across both evaluations.



### 10.4 Status



At the time of writing, the v1.1 implementation is pending. The methodology amendments, the code changes, the ablation evaluation, and the v1.1 report are not yet complete. The v1.1 report will be published under Odwira \& Whitehall and linked from this document when it exists.



---



## 11. Limitations



The limitations of this evaluation are pre-registered in methodology section 6 and section 9, and operate as constraints on what the report's findings support. They are restated here in the report's own voice with the addition of limitations specific to the v1 evaluation as conducted.



### 11.1 Limitations inherited from the methodology



**Selection bias in the HeatpumpMonitor.org population.** The dataset is self-selected. Submitters skew toward technically engaged owners of well-installed systems with above-average monitoring infrastructure. The realised SPF distribution in the evaluation set may be higher than the UK fleet average. The mean realised SPF across the 303 eligible cases is approximately 3.7; external estimates of the UK fleet average vary but are generally lower. Findings from this evaluation apply specifically to well-monitored UK heat pump installations submitted to a community open-data platform and do not generalise to the UK heat pump fleet as a whole. Methodology section 6.1 fixes this boundary; the report inherits it.



**DHW occupancy assumption introduces a noise floor.** The methodology fixes occupancy at 3 for the headline runs; the section 5.4 sensitivity analysis demonstrates that the assumption is responsible for approximately 11 percentage points of MAPE movement across the {1, 2, 3, 4, 5} range. For the headline run B figures, this means per-case accuracy below approximately ±10% cannot be distinguished from occupancy assumption error. Methodology section 6.2 documents this.



**Measurement uncertainty in realised values.** Realised electricity is treated as ground truth. Class 1 electric meters contribute approximately ±1% accuracy; class 2 heat meters contribute approximately ±3–5%. A perfect model cannot achieve 0% MAPE; the floor is approximately ±2% from meter accuracy alone. Below 5% MAPE, metric differences are not meaningfully distinguishable from measurement noise. Methodology section 6.4.



**Climate window mismatch with monitoring period.** The headline uses a 20-winter typical climate, not each system's actual monitoring window. This contributes approximately ±5% noise per case. The secondary matched-window diagnostic specified in methodology section 4.1 was deferred to v2; this evaluation does not separate climate-window mismatch from model error directly. Methodology section 6.5.



**Confirmation bias.** The model code was developed by the author with prior exposure to the Twentyman reference case used in the test suite. The HeatpumpMonitor.org evaluation set was not used during model development. Confirmation bias cannot be excluded. Methodology section 9.5.

**CRPS reported without skill-score baseline.** The CRPS values in section 5.1 are reported as absolute means in kWh and are scale-dependent. No naive baseline (e.g., dataset-mean predictor, floor-area regression) was computed for v1, so the Continuous Ranked Probability Skill Score (CRPSS) is not available. CRPS is therefore interpretable only for internal run-to-run comparison within this evaluation (e.g., Run B versus Run F), not as an absolute statement of probabilistic forecasting skill. A baseline CRPSS computation is added to the v1.1 evaluation specification.



### 11.2 Limitations specific to the v1 evaluation as conducted



**Open-Meteo rate limiting during initial climate cache population.** The Open-Meteo historical archive API rate-limited the climate-fetcher during initial dataset preparation. The mitigation was a dedicated prefetch script with exponential backoff and `Retry-After` handling, executed in two passes plus a one-off targeted retry on two persistently failing locations. The final climate cache contains 306 parquet files covering all eligible cases. The cache is committed to the project repository for reproduction; the rate-limiting incident is documented in the project repository's commit history at `62a611f`. This is not a limitation of the evaluation's findings — the cache is complete and verified — but is a reproducibility caveat for any future evaluator who fetches the same data from a clean state.



**Two methodology amendments before the headline evaluation.** The methodology document was amended twice between initial commitment and the final evaluation. The first amendment (commit `6b1a3ab`) tightened the dataset inclusion criterion section 3.2 from "present and non-null" MCS fields to "present, non-null, and physically valid," with bounded ranges. The second amendment (after the first full evaluation surfaced three unit-error cases) added an upper bound of 50 kW on heat_loss to the physical-validity filter. Both amendments are documented in the methodology document's commit history and were applied before the evaluation reported here. Neither amendment changed the seven-run ablation structure, the decision thresholds, or the claim-mapping table. The amendments are recorded for transparency; they do not introduce post-hoc rationalisation because they tightened (rather than loosened) the criteria.



**Bundle-of-fixes problem in v1.1 design.** The v1.1 ablation described in section 10 includes three changes simultaneously. While the ablation design enables individual attribution, interaction effects between the three changes may not be fully separable from the available comparisons. If the demand-period fix and the DHW occupancy propagation interact non-linearly — for example, if extending the climate to full year changes the relative magnitude of DHW versus space heating in the daily totals — the ablation will identify the combined effect but may not cleanly separate the interaction term. The v1.1 report will document this if it occurs.



**Single-evaluation finding.** This evaluation tests the v1 model on one dataset, one snapshot, with one random seed. The headline metrics are point estimates of the model's calibration performance on the evaluation set. The Wilson 95% confidence intervals on coverage reflect sampling uncertainty within the evaluation set, not variability across hypothetical alternative datasets. A model that fails this evaluation might be expected to fail similar evaluations on similar populations, but the magnitudes of failure could differ; replication on independent datasets is outside the scope of this report.



**Cooling and immersion-backup exclusions reduce sample size.** Methodology section 3.2 criterion 8 excludes cases where cooling electricity and immersion backup contribute more than 5% of total system electricity. The strict-zero sensitivity analysis (methodology section 5.5, results in the calibration report) confirms that this exclusion does not materially change the headline metrics on the measured-input subset. However, the exclusion removes 15 cases from the eligible set. Systems with material cooling or backup-heater contributions are not represented in the evaluation, and findings do not extend to such systems.



### 11.3 Limitations the report does not claim to address



This report does not attempt to address several broader limitations that future work might consider.



The report does not benchmark the v1 model against alternative forecasting models (heuristic estimators, regression-based approaches, neural network architectures, or commercial calculators). The methodology's claim mapping is internal to the v1 model's pre-registered thresholds, not comparative to external benchmarks.



The report does not address the model's performance on time horizons other than annual. The v1 model produces an annual electricity forecast; sub-annual performance (winter-only, season-by-season) is not evaluated.



The report does not address the cost forecast itself, only the underlying electricity forecast. The methodology fixes a single tariff scenario and reports accuracy in kWh; the report does not evaluate whether the cost arithmetic introduces additional error.



The report does not address scenarios in which user inputs are deliberately or accidentally incorrect (typos in heat-loss values, wrong postcodes, miscategorised property age). Methodology section 3.2 criterion 4's physical-validity filter excludes cases with unit errors from the evaluation; user-input quality in deployment is a separate concern.



The report does not propose or test the v1.1 fix's correctness. Section 10 describes what v1.1 will do; the v1.1 report will determine whether it works.



---



## 12. About this Report



### 12.1 Author and publisher



This report is authored by Bernard Ashiley and published under Odwira \& Whitehall.



Bernard Ashiley is a computational statistician based in London. Odwira \& Whitehall is the studio under which this work is published.



Correspondence: bernardashiley@gmail.com



### 12.2 Citation



This report may be cited as:



Ashiley, B. (2026). *Calibration of a Probabilistic UK Heat Pump Running-Cost Forecaster v1: A Pre-Registered Evaluation Against HeatpumpMonitor.org.* Odwira \& Whitehall technical report, 10 June 2026. [SSRN identifier to be added on preprint posting.]



### 12.3 Repository and reproduction



The complete project repository, including the model code, the methodology document, the dataset snapshot, the climate cache, the evaluation scripts, the diagnostic memo, and this report, is available at:



https://github.com/bernardashiley/heat_pump_project



The report's source is at `docs/CALIBRATION_REPORT_V1.md` in that repository. The repository's `README.md` documents the reproduction commands and the dependency environment.



### 12.4 Companion documents



This report is intended to be read in conjunction with:



- `docs/CALIBRATION_METHODOLOGY.md` — the pre-registered methodology document, committed at hash `6b1a3ab` and used as the operative reference throughout this report.

- `docs/V1_DIAGNOSTIC_FINDINGS.md` — the diagnostic memo that supports the findings in section 7 and section 8 of this report, including the per-case computational checks referenced in those sections.

- `data/heatpumpmonitor/calibration_report.md` — the machine-generated report from which the headline numbers in section 5 are taken verbatim. This artefact is not committed (it is regenerated by the evaluation script) but can be reproduced from the committed inputs at the model code commit hash recorded in section 4.



The v1.1 calibration report described in section 10 will be published as a separate artefact when complete.



### 12.5 Licence



This report's prose is published under Creative Commons Attribution 4.0 International (CC BY 4.0). The associated code in the project repository is published under the MIT Licence. The HeatpumpMonitor.org dataset is openly available under the terms set by OpenEnergyMonitor [5]; this report's use of the data complies with those terms.



### 12.6 Acknowledgements



The author thanks the OpenEnergyMonitor community for maintaining the HeatpumpMonitor.org open dataset, without which the evaluation reported here would not have been possible. The author also acknowledges Open-Meteo for the historical climate data used in the model and the evaluation.



---



## References



[1] Microgeneration Certification Scheme. *MIS 3005-D: Heat Pump Systems — Requirements for Contractors Undertaking the Design of Microgeneration Heat Pump Systems.* MCS, current issue. [MCS website](https://mcscertified.com/).



[2] British Standards Institution. *BS EN 12831-1:2017: Energy performance of buildings — Method for calculation of the design heat load — Part 1: Space heating load.* BSI, 2017.



[3] Gneiting, T. and Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation.* Journal of the American Statistical Association, 102(477), 359–378.



[4] Twentyman, R. *Direct comparison: oil boiler vs air source heat pump, same house, 12 years of data.* Medium, 2024. [Article URL](https://medium.com/@robert_twentyman/direct-comparison-oil-boiler-vs-air-source-heat-pump-same-house-12-years-of-data-ff23cde27240).



[5] OpenEnergyMonitor. *HeatpumpMonitor.org Introduction.* OpenEnergyMonitor documentation. [Documentation URL](https://docs.openenergymonitor.org/heatpumpmonitor/introduction.html) (accessed June 2026).



[6] Open-Meteo. *Open-Meteo historical weather API.* [API documentation](https://open-meteo.com/en/docs/historical-weather-api) (accessed June 2026).



[7] Heating-degree-day calculation for UK climate: HDD15.5 fraction computed empirically from Open-Meteo historical archive data for representative UK locations included in the dataset. Computation script and result available in the project repository at `docs/V1_DIAGNOSTIC_FINDINGS.md`.





