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

---

## References

[1] Microgeneration Certification Scheme. *MIS 3005-D: Heat Pump Systems — Requirements for Contractors Undertaking the Design of Microgeneration Heat Pump Systems.* MCS, current issue. https://mcscertified.com/

[2] British Standards Institution. *BS EN 12831-1:2017: Energy performance of buildings — Method for calculation of the design heat load — Part 1: Space heating load.* BSI, 2017.

[3] Gneiting, T. and Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation.* Journal of the American Statistical Association, 102(477), 359–378.

[4] Twentyman, R. *Direct comparison: oil boiler vs air source heat pump, same house, 12 years of data.* Medium, 2024. https://medium.com/@robert_twentyman/direct-comparison-oil-boiler-vs-air-source-heat-pump-same-house-12-years-of-data-ff23cde27240

[5] OpenEnergyMonitor. *HeatpumpMonitor.org Introduction.* OpenEnergyMonitor documentation. https://d
