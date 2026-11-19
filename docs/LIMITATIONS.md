# Limitations and responsible use

* **Small, single-source data.** 697 events, 33 employees, one company. Results may not transfer to other workplaces or future periods.
* **Event data only.** No attendance calendar and no headcount per month: absence rates cannot be measured, and the model cannot say whether an absence will happen.
* **Model ≈ baseline.** The Random Forest is not statistically distinguishable from a reason-only model (PR-AUC difference +0.022, 95% interval −0.006 to +0.050).
* **Wide intervals.** The original 6-employee test has a PR-AUC interval of 0.52–0.87; pooled intervals are about ±0.1.
* **Calibration is imperfect** (see MODEL_EVALUATION.md).
* **Inferred timeline.** Months are reconstructed from row order; the start month comes from public documentation. A date column would replace this inference.
* **Reason labels** come from public dataset documentation, not from the file.
* **Association, not cause.** Nothing in the app shows that a reason, month or weekday causes a longer absence.
* **Simulator** outputs follow from user assumptions (independence, Poisson event counts, duration distribution from one company). Upper percentiles are noisy because durations are heavy-tailed (up to 120 h).
* **Privacy.** Absence reasons can relate to health. Only aggregates are exposed, but small groups remain sensitive; do not load other organisations' data without consent.
* **Deployment.** The CloudFront-to-EC2 hop uses HTTP; use HTTPS (domain and certificate or a load balancer) for anything beyond a demo.
* **Not for** hiring, firing, discipline, ranking or evaluating individuals.
