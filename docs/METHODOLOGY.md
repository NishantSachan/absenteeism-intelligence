# Methodology

## 1. Question and scope
Given an absence that has **already been reported**, how likely is it to last at least one working day (8 hours or more)?
This supports triage and planning conversations. It does **not** predict whether anyone will be absent, and the dataset cannot measure an organisation's
absence rate: it contains absence events only (no attendance calendar, no headcount per month).

## 2. Data audit (all numbers computed from `data/raw/Absenteeism_at_work.csv`)
| Check | Result |
|---|---|
| Rows / columns / employees | 740 / 21 / 36 |
| Missing values | 0 |
| Exact duplicate rows | 34, kept (no date column, so identical rows can be different events) |
| Rule rows | 43 rows with reason code 0 are excluded. They include all 40 disciplinary-failure rows, and all have 0 hours (no absence recorded) |
| Modelling rows | 697 events from 33 employees; 271 long (38.9%) |
| Reason codes with data | 27 codes (20 never occurs); only 14 codes have 10 or more events |
| Repetition | the top 3 employees supply 34.7% of events (Gini 0.53) |
| Employee attributes | nearly fixed per person, but Age and some others take two values for some employees over three years |

## 3. Target
`long_absence = (Absenteeism time in hours ≥ 8)`. Kept from the original project because the data supports it: 208 events last exactly 8 hours and only 8 fall
between 5 and 7 hours, so 8 is a natural break. Every long absence is a whole number of working days.
Leakage review: disciplinary failure and reason 0 deterministically imply 0 hours and are excluded before modelling. Reason 27 (physiotherapy) has 0 long absences in 69 events, which is a strong
regularity rather than a rule, and is documented as such.

## 4. Features available at prediction time
Reason for absence, month and day of the week: all known when an absence is reported. Personal and workload columns were tested and dropped because they did not
improve employee-grouped validation (see `reports/tables/exp3_feature_set_ablation.csv`).

## 5. Validation design
Because the same employees appear many times, random row splits leak identity. All model selection used splits **grouped by employee**.
* Original design (kept): 27 training / 6 test employees; model selection and the alert level fixed on training data only.
* Added: pooled repeated grouped cross-validation over **all 33 employees** (5 folds, 10 seeds), so every employee is held out once per repeat.
* Added: employee-level bootstrap (2,000 resamples of whole employees) for confidence intervals and paired differences between models.
* Added: a time-ordered check (first 25 reconstructed months → last 12).
* Baselines: prevalence (no skill), reason-only logistic regression, smoothed reason-rate lookup.
Metrics: PR-AUC (primary, imbalanced task), ROC-AUC, Brier score, recall/precision/F1 at the fixed alert level 0.34, confusion matrix, calibration.

## 6. Model choice
The Random Forest (300 trees, `min_samples_leaf=3`, one-hot encoded categorical inputs inside a single scikit-learn `Pipeline`) was selected by a rule fixed in advance (simplest model within a small margin of the best).
It was **retrained in a scratch copy and reproduced byte-identically**, and the new evidence (section 5) shows it is statistically indistinguishable from simple baselines, so the artifact
`models/absenteeism_pipeline.joblib` was not replaced. `model_metadata.json` records its SHA-256 so any later change is detectable.
The alert level 0.34 comes from an assumed 2:1 cost of a missed long absence versus a false alarm, chosen on training-only out-of-fold predictions; it stays the same for ratios 2 and 3.

## 7. Explainability
With three categorical inputs the model is evaluated **exactly** on all 1,620 supported input combinations. The app reports permutation importance (reason 0.314, weekday 0.013, month 0.010),
the spread of the estimate when only month/weekday change (median interquartile range about 10 percentage points; the long/short call flips only for reason 25),
the historical rate per reason with 95% Wilson intervals, and a reason-only comparison. SHAP was not added: it would add a heavy dependency without new insight for three inputs.
Three statements are kept apart everywhere: **historical association** (the data), **model prediction** (what the model learned) and **causation** (never claimed).

## 8. Pattern discovery
Computed by `src/analytics.py` and served as aggregates: duration distribution, event share vs lost-hours share per reason, long-rate by month and weekday with Wilson intervals,
chi-square tests with Cramér's V (reason 0.70, month 0.20, weekday 0.14; p-values are optimistic because events from one employee are correlated), a 37-month event series,
and anonymous employee-concentration statistics. Clustering was deliberately not used: 14 usable reason categories and 33 employees would not support it, and employee clustering is individual profiling.

## 9. Timeline reconstruction
The file has no date, but rows are chronological: the monthly *Work load Average/day* figure forms 38 contiguous runs (37 months plus the 3 month-0 rows) and 36 of 36 consecutive month-to-month steps advance by exactly one month; a shuffled copy fails the same check (tested).
The start month (July 2007) comes from public dataset documentation, not from the file, and the app labels the timeline as inferred.

## 10. Workforce simulation
Assumptions (user): headcount, window in working days, shift hours, absence events per employee per month, reserve staff, required capacity %, reason mix.
Measured (data): the empirical distribution of hours per event by reason (small reasons pooled as "other").
Deterministic: expected events = rate × headcount × days/21; lost hours = events × mix-weighted mean hours (capped at scheduled hours);
gap = required hours − (scheduled − lost + reserve hours). Monte Carlo: Poisson event counts, durations resampled from the empirical distribution, fixed seed, independence assumed.
The model's predictions are **not** inputs to the simulator, and its outputs are never described as forecasts.

## 11. Reproducibility
`python -m src.train` → `python -m src.robustness` → `python -m src.make_app_assets`. Seeds are fixed; library versions are pinned (`requirements-train.txt`, `backend/requirements.txt`).
Synthetic data was not generated for training; the toy duration tables in tests are labelled as test fixtures.
