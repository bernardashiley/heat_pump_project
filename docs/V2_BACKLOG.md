# V2 Backlog

This document records candidate v2 work identified during the v1 calibration and diagnostic process. It is not a pre-registered methodology and does not define validation thresholds. Any model change made in response to these notes should be evaluated under a separate pre-registered v2 or v1.1 evaluation before product claims are updated.

## V2 candidate model improvements

- Extend the climate and demand simulation from October-March winter windows to full-year daily weather realisations. The v1 evaluation identified the winter-only demand period as a structural defect: shoulder-season space heating and roughly half of annual DHW were omitted while the result was reported as annual electricity.

- Revisit the balance-point temperature (`t_base_c`). Diagnostics showed that raising `t_base_c` materially increases predicted electricity, but the current evidence is confounded by the missing shoulder-season days. Reassess only after the full-year demand-period fix.

- Make DHW occupancy a required or explicitly uncertain input. The v1 calibration sensitivity found that varying occupants from 1 to 5 moved Run B MAPE by more than 10 percentage points, so fixed 3-person DHW is not acceptable as a silent assumption.

- Investigate monitoring-boundary and auxiliary electricity effects. Some HeatpumpMonitor systems may include circulation pumps, controls, backup heaters, or other boundary loads not represented by the v1 model. Slice errors by available metering-boundary metadata before adding any allowance.

- Humidity-conditional defrost penalty per Zhu et al. 2015 frosting map. This requires Open-Meteo humidity fields in the climate cache, a frosting-zone severity model, and enough reference cases across UK humidity bands to constrain parameters. Do not add this until there are at least 10 suitable reference cases or an equivalent empirical calibration set.

- Flow-temperature and defrost coupling. Higher flow temperature may increase frosting/defrost losses. The current model mostly absorbs this into fitted eta. A v2 model could split this effect for better monthly or temperature-bin breakdowns.

- SCOP-constraint interaction. The defrost penalty currently redistributes electricity across temperature bins but does not change the annual total when SCOP is fixed. Future empirical cases should test whether stated SCOP values systematically overstate or understate observed seasonal electricity.

- Eta-boundary warning UX. The defrost penalty has its largest practical effect when fitted eta clamps at `ETA_MAX`. User-facing copy should explain when the eta-boundary warning means the forecast is materially constrained by inconsistent SCOP, flow-temperature, or defrost assumptions.

- Hierarchical per-case estimation of model input priors. Rather than fixed defaults for base temperature, heating slope, indoor temperature, and DHW occupancy, fit a hierarchical Bayesian model that estimates these parameters per case from observed daily electricity-vs-outdoor-temperature data. The base temperature in particular is well-defined as the kink point in a change-point regression of daily electricity on heating-degree-days (cf. PRISM and variable-base-temperature degree-day methods in the building energy literature). The hierarchical structure provides shrinkage toward population means for cases with limited data. This is a substantial methodological step beyond v1.1's fixed-input model and is likely a thesis-scale piece of work in its own right. Prerequisites: access to daily-resolution electricity and temperature data per case (HeatpumpMonitor.org aggregate stats are insufficient); a pre-registered v2 methodology document; Stan or PyMC fitting infrastructure (the author's thesis stack carries over).

## Known environment issues

- Python's local SSL trust store on this Windows machine rejects `postcodes.io` and Open-Meteo certificates in some sessions. Diagnostic workaround used during development: `httpx.Client(verify=False)`. Do not bake this into production code. Fix the local trust store instead with `pip install --upgrade certifi` and verify Python uses it with:

```powershell
python -c "import certifi; print(certifi.where())"
```
