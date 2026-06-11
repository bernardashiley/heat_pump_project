# Calibration Methodology for v1.1 Heat Pump Running-Cost Forecaster

**Author:** Bernard Ashiley
**Imprint:** Odwira & Whitehall
**Pre-registration date:** [TO BE FILLED ON COMMIT]
**Status:** Pre-registered. Committed to the project repository before any v1.1 code changes or evaluation runs.

---

## 1. Purpose

This document is the pre-registered methodology for the v1.1 calibration evaluation of the UK Heat Pump Running-Cost Forecaster. It is committed to the project repository before the v1.1 code changes are written and before any v1.1 evaluation is run. The discipline is the same as for v1: pre-commit the methodology so the result is credible whether v1.1 succeeds or fails.

The v1.1 evaluation tests whether three specific changes to the v1 model close the calibration gap documented in the v1 calibration report. Those three changes are evaluated as an ablation so that each change's individual contribution to v1.1 metrics is attributable.

The v1.1 methodology inherits the v1 methodology unchanged in its core structure: the same dataset and inclusion criteria, the same seven-run input ablation (A-full, A-subset, B, C, D, E, F), the same validation gates and decision thresholds, the same random seed and per-case seed scheme, and the same claim-mapping discipline. This document records only the amendments specific to v1.1.

The authoritative v1 methodology is at `docs/CALIBRATION_METHODOLOGY.md`, committed at hash `6b1a3ab`. The v1 calibration report is at `docs/CALIBRATION_REPORT_V1.md`. The reader is referred to those documents for the operative v1 definitions, decision rules, and findings.

---

## 2. Three model changes

v1.1 implements three changes to the v1 model. Each is motivated by a specific finding from the v1 calibration evaluation.

### 2.1 Change 1: demand period extended from October-March to full year

**Motivation.** Section 7 of the v1 calibration report identified a structural defect in the v1 model's demand-period definition: the climate fetcher returned 182 days (October-March only), the demand model computed daily demand on those days only, and the result was reported as annual electricity. The defect omitted approximately half of annual heating and domestic-hot-water load and produced the -29.1% median signed error observed in Run B.

**Operational definition.** The climate fetcher (`backend/app/forecast/climate.py`) is extended to return all 365 days of each historical year used in the Monte Carlo simulation. The demand model (`backend/app/forecast/demand.py`) computes daily heating demand on all 365 days using the existing heating-degree-day formula with base temperature 15.5 °C, which correctly returns zero on days when outdoor temperature exceeds the base temperature. The DHW model continues to apply daily DHW demand uniformly, but now across the full 365-day year, removing the implicit truncation to ~50%. The Monte Carlo orchestrator (`backend/app/forecast/monte_carlo.py`) continues to sum daily electricity across each historical year's full 365-day window and report the result as annual electricity.

No other component of the v1 model is altered by this change.

### 2.2 Change 2: DHW occupancy uncertainty propagated

**Motivation.** Section 8.2 of the v1 calibration report reported that DHW occupancy varying across {1, 2, 3, 4, 5} occupants moved Run B MAPE by 11.4 percentage points -- the methodology §7.8 decision rule threshold (>= 10 percentage points) was exceeded, triggering the consequence that occupancy is critical and must propagate as uncertainty in subsequent model iterations.

**Operational definition.** The v1 model uses a fixed 3-occupant default for DHW heat demand. v1.1 replaces this with a propagated uncertainty distribution. For each Monte Carlo draw within a case, an occupant count is sampled from the discrete uniform distribution over {1, 2, 3, 4, 5}:

$$\text{Occupants} \sim \text{DiscreteUniform}(\{1, 2, 3, 4, 5\})$$

The uniform choice is deliberate. It is the maximum-entropy discrete distribution over the {1..5} support, makes no assumption about UK household composition that the HeatpumpMonitor.org cohort might not match, and produces a clean ablation isolating "does propagating occupancy uncertainty improve calibration" from confounding with "does using a UK-realistic occupancy mix improve calibration".

The per-case seed scheme is extended to include an occupancy sub-seed: `occupancy_seed = case_seed + 7` (the +7 offset preserves separation from the existing three sub-seeds for climate, COP, and DHW arithmetic). The same occupancy draws are used across all seven input runs (A-full through F) for a given case so that paired comparisons within a configuration are not contaminated by sampling noise.

### 2.3 Change 3: indoor temperature required as user input

**Motivation.** The v1 model accepts a user-declared indoor temperature with a 21 °C default fallback when not provided. v1 Run F (the realistic-user end-to-end run) uses this default for most cases. The v1 calibration report's §6 outcomes show that the indoor-temperature substitution comparison (B - E) was small (+2.6 pp) and below the methodology threshold, but this is not informative about indoor-temperature *availability* -- only about substitution effects given the structural defect. v1.1 tests whether removing the silent default and requiring explicit input changes the realistic-user run's behaviour.

**Operational definition.** In v1.1, indoor temperature is a mandatory user input. The 21 °C default fallback is removed from the code. Cases in the evaluation dataset where indoor temperature is unavailable are excluded from runs that previously relied on the default (specifically: Runs A-full and F, where indoor temperature would otherwise have been imputed). The eligible-set size for these runs may decrease as a result. The measured-input subset is unaffected since it requires measured indoor temperature by construction.

The user-interface change required to elicit indoor temperature in deployment is out of scope of this evaluation; this methodology specifies only the model-side change.

---

## 3. Ablation design

The three changes are evaluated as an ablation so that each change's individual contribution to v1.1 metrics is attributable.

### 3.1 Six model configurations

| Configuration | Change 1 (demand period) | Change 2 (DHW occupancy) | Change 3 (indoor temperature) |
|---|---|---|---|
| v1 baseline | Oct-Mar | Fixed 3 | Declared or 21 °C default |
| v1.1a | Full year | Fixed 3 | Declared or 21 °C default |
| v1.1b | Oct-Mar | Propagated | Declared or 21 °C default |
| v1.1c | Oct-Mar | Fixed 3 | Required (case excluded if unavailable) |
| v1.1ab | Full year | Propagated | Declared or 21 °C default |
| v1.1abc | Full year | Propagated | Required |

The v1 baseline configuration is included as a reproducibility check: running the v1 baseline through the v1.1 evaluation infrastructure should reproduce the v1 calibration report's headline numbers within sampling noise (the random seed and per-case seed scheme are unchanged).

### 3.2 Seven-run input ablation

The same seven-run input ablation (A-full, A-subset, B, C, D, E, F) defined in v1 methodology §2 is applied to each of the six configurations. The total evaluation comprises 6 × 7 = 42 (model, input) combinations.

### 3.3 Attribution questions

The ablation enables the following attribution questions:

- **v1.1a vs v1 baseline:** marginal contribution of the demand-period fix in isolation.
- **v1.1b vs v1 baseline:** marginal contribution of DHW occupancy propagation in isolation.
- **v1.1c vs v1 baseline:** marginal contribution of requiring indoor temperature input in isolation.
- **v1.1abc vs v1 baseline:** combined effect of all three changes.
- **v1.1abc vs single-change configurations (v1.1a, v1.1b, v1.1c):** identification of interaction effects between the three changes.

### 3.4 Computational scope

Total wall-clock time is approximately 6 × 4.5 minutes ≈ 27 minutes on a populated climate cache. The cache is reused unchanged from v1 (306 parquet files at `data/heatpumpmonitor/climate_cache/`), with the addition that the cache must now cover April-September daily mean temperatures for the same locations. The prefetch script `backend/scripts/prefetch_climate_cache.py` is extended to fetch the full year and re-populate the cache where needed.

---

## 4. Naive baseline and CRPSS reporting

Section 11.1 of the v1 calibration report documented the deferral of skill-score reporting to v1.1. This methodology specifies the baseline.

### 4.1 Naive baseline definition

The naive baseline is a dataset-mean-predictor: every case is predicted as a single constant value equal to the mean of realised annual electricity across the v1.1 eligible set (303 cases under v1 inclusion criteria; smaller under v1.1c and v1.1abc owing to Change 3's case-exclusion rule). The baseline is a point predictor with zero uncertainty.

Formally, for case $i$ in the eligible set of size $n$:

$$\hat{y}_{\text{baseline}, i} = \frac{1}{n} \sum_{j=1}^{n} y_j$$

The baseline's CRPS for case $i$ collapses to the absolute error against the dataset mean:

$$\text{CRPS}_{\text{baseline}}(y_i) = |y_i - \hat{y}_{\text{baseline}, i}|$$

Mean CRPS of the baseline across the eligible set is the constant against which the v1.1 model configurations are compared.

### 4.2 Continuous Ranked Probability Skill Score (CRPSS)

For each (model configuration, input run) combination, CRPSS is reported as:

$$\text{CRPSS} = 1 - \frac{\overline{\text{CRPS}}_{\text{model}}}{\overline{\text{CRPS}}_{\text{baseline}}}$$

A CRPSS of 0 means the model is no better than the naive baseline. Positive CRPSS means the model is better; negative CRPSS means the model is worse than predicting the dataset mean. CRPSS is unitless and bounded above by 1 (achieved only by a perfect deterministic forecaster).

No CRPSS threshold is pre-committed as a validation gate. CRPSS is reported as methodological hygiene -- to give the absolute CRPS values in §5.1 a meaningful scale -- not as binary evidence for or against a claim.

---

## 5. Validation gates

The validation gates from v1 methodology §7.1 and §7.4 apply unchanged to the v1.1 evaluation. They are restated here for clarity.

### 5.1 Run B validation gate (v1 §7.1)

For any model configuration to pass the demand-side validation gate on Run B, all three of the following must hold:

- Coverage of the 80% prediction interval >= 75%
- MAPE <= 12%
- Median interval width <= 50% of median realised electricity

Failure on any one of these three triggers the v1 §7.1 consequence: deployment of that configuration is halted until the failing component is investigated.

### 5.2 Run F viability gate (v1 §7.4)

For any model configuration to pass the realistic-user viability gate on Run F, both of the following must hold:

- Coverage of the 80% prediction interval >= 60%
- MAPE <= 25%

Failure on either triggers the v1 §7.4 consequence: the realistic-user end-to-end model under that configuration is not viable as a deployment artefact in its current form.

---

## 6. Claim mapping

The v1 claim-mapping table of six allowed claims is inherited unchanged. Three new claims are pre-committed for v1.1, each tied to a specific evidence threshold. As with v1, claims not on this list are not supported by the v1.1 evaluation regardless of what the numbers show.

### 6.1 Inherited v1 claims (1-6)

The six claims defined in v1 methodology §10 and reported on in v1 calibration report §6 apply to the v1 baseline configuration as run through the v1.1 evaluation infrastructure. These are inherited unchanged and are not re-evaluated as part of v1.1's headline contribution -- they are reproducibility checks.

### 6.2 New v1.1 claims (7-9)

| # | Allowed claim | Evidence requirement |
|---|---|---|
| 7 | The demand-period correction (Change 1 alone) materially improves Run B coverage | v1.1a Run B coverage - v1 baseline Run B coverage >= 30 percentage points |
| 8 | The combined v1.1 configuration (v1.1abc) passes the v1 §7.1 demand-side validation gate on Run B | v1.1abc Run B coverage >= 75% AND MAPE <= 12% AND median interval width <= 50% of median realised |
| 9 | The combined v1.1 configuration (v1.1abc) passes the v1 §7.4 realistic-user viability gate on Run F | v1.1abc Run F coverage >= 60% AND MAPE <= 25% |

Claim 7 tests whether the structural-defect correction alone is sufficient to close the v1 calibration gap, isolating the contribution of the dominant diagnostic finding. Claim 8 tests whether the corrected model meets the v1 methodology's primary validation threshold under perfect-foresight inputs. Claim 9 tests whether the corrected model meets the deployment viability threshold under realistic-user inputs (MCS-declared heat loss, mandatory indoor temperature, fixed 3.5 SCOP).

Claims 7, 8, and 9 are the publishable headline claims if v1.1 succeeds. If any claim's evidence requirement is not met, that claim is unsupported, the report says so, and the underlying configuration's specific failure is documented and explained.

### 6.3 Claims explicitly not on the mapping

The following are not pre-committed claims and will not be reported as supported even if the evidence is favourable:

- Magnitude claims about individual ablation contributions beyond claim 7 (e.g., "DHW occupancy propagation alone provides >= X pp coverage improvement"). The ablation will produce these numbers; the report will state them; no thresholds are pre-committed.
- Claims about CRPSS magnitudes. Reported as methodological hygiene per §4 above.
- Generalisation claims beyond the HeatpumpMonitor.org cohort, per v1 §11.1 inheritance.
- Comparative claims against other forecasting models (heuristic, regression-based, neural), since no benchmark models are evaluated.
- Cost-forecast accuracy claims, since the methodology evaluates electricity forecasts only.

---

## 7. Reproducibility and provenance

The v1.1 evaluation inherits the v1 reproducibility infrastructure unchanged:

- **Dataset:** the same 9 June 2026 HeatpumpMonitor.org snapshot used in v1 (regenerable via `backend/scripts/fetch_heatpumpmonitor.py`; not committed owing to absence of an explicit redistribution licence; the exact snapshot is available from the author by request per v1 calibration report §12.1).
- **Random seed:** `20260609`. Per-case seed scheme `case_seed = random_seed * 1000 + system_id` is unchanged. Occupancy sub-seed `occupancy_seed = case_seed + 7` is added for Change 2.
- **Climate cache:** the same 306-location parquet cache at `data/heatpumpmonitor/climate_cache/`, extended to full-year coverage.
- **Code version:** the v1.1 evaluation runs against a model code commit hash that will be recorded in the v1.1 calibration report at evaluation time. A git tag `calibration-eval-model-code-v1-1` will be set on that commit before the evaluation runs.
- **Evaluation script:** `backend/scripts/run_calibration_eval.py` extended to support the six configurations. Output artefacts (per-case predictions, errors CSV, machine-generated report) follow the same naming conventions as v1, with `v1_1` suffix.

---

## 8. Decision rules and consequences

The pre-committed consequences of the v1.1 evaluation are as follows.

**If claim 7 is supported (v1.1a Run B coverage - v1 baseline Run B coverage >= 30 pp):** the structural-defect correction is confirmed as the dominant lever in the v1 calibration failure. The v1 calibration report's diagnostic finding (§7) is empirically validated.

**If claim 8 is supported (v1.1abc passes the §7.1 gate on Run B):** the demand-side model is validated. Deployment of v1.1abc is permitted under the methodology's primary validation discipline.

**If claim 9 is supported (v1.1abc passes the §7.4 gate on Run F):** the realistic-user end-to-end model is viable as a deployment artefact. v1.1abc may be positioned as a heat-pump running-cost forecaster for users without measured-input calibration data.

**If any of claims 7, 8, or 9 is not supported:** the v1.1 ablation identifies which of the three changes contributed and which did not. The v2 methodology is informed accordingly. v1.1 is not deployed at the level the failing gate would have authorised.

**If all three claims are supported:** the v1.1 calibration report is published as the successor artefact to the v1 report. v1.1abc becomes the deployed model. The v2 methodology focuses on subsequent improvements (humidity-conditional defrost, flow-temperature coupling, etc., per the V2_BACKLOG).

---

## 9. Limitations the v1.1 evaluation does not address

The v1.1 evaluation inherits the v1 limitations (v1 calibration report §11) unchanged. Specifically:

- The HeatpumpMonitor.org cohort's selection bias toward well-installed, technically engaged systems.
- Measurement uncertainty in realised values (~±2% MAPE floor from meter accuracy alone).
- Climate window mismatch with monitoring period (±5% per case from inter-annual variability, deferred matched-window diagnostic).
- Single-evaluation finding: one dataset, one snapshot, one random seed.
- Cooling and immersion-backup exclusions (15 cases excluded per v1 §3.2 criterion 8).

v1.1-specific limitations will be documented in the v1.1 calibration report when the evaluation completes. Anticipated topics include: bundle-of-fixes interaction effects between Changes 1, 2, and 3 (per v1 §11.2); CRPSS interpretation against a simple constant-predictor baseline rather than a more competitive baseline; and the absence of an external held-out validation set.

---

## 10. Status

At the time of this pre-registration, the v1.1 implementation is pending. The methodology amendments specified above are the operative pre-commitments. The code changes, the ablation evaluation, and the v1.1 calibration report are not yet complete.

The v1.1 calibration report will be published under Odwira & Whitehall when the evaluation is complete and linked from the v1 calibration report as a successor artefact.

---

## 11. Amendments

Any amendment to this methodology before the v1.1 evaluation runs will be committed to the project repository with a clear commit message identifying what is amended, why, and whether the amendment tightens or loosens the original criteria. Amendments after the evaluation runs are not permitted; if a flaw in the methodology is identified post-evaluation, the result stands and the flaw is documented in the v1.1 calibration report's limitations section.

---

*This document is the pre-registered methodology for the v1.1 calibration evaluation. It is committed to the project repository before any v1.1 code changes are written and before any v1.1 evaluation is run. Pre-registration is the discipline that makes the v1.1 result credible whether it succeeds or fails.*
