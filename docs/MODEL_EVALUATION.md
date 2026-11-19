# Model evaluation summary

All figures are read from `models/metrics.json` (`evaluation_v2` and the original blocks). Alert level 0.34 for recall/precision/F1.

## Pooled grouped cross-validation (697 events, 33 employees, 10 repeats)
Every employee is held out once per repeat. 95% intervals come from resampling whole employees.

| Model | PR-AUC | 95% interval | ROC-AUC | Brier | Recall | Precision | F1 |
|---|---|---|---|---|---|---|---|
| Prevalence baseline (no skill) | 0.389 | 0.30–0.51 | 0.500 | 0.238 | 1.00 | 0.39 | 0.56 |
| Reason-only logistic regression | 0.727 | 0.63–0.81 | 0.855 | 0.133 | 0.90 | 0.73 | 0.81 |
| Smoothed reason-rate lookup | 0.732 | 0.63–0.82 | 0.857 | 0.137 | 0.89 | 0.73 | 0.80 |
| Logistic regression (3 inputs) | 0.729 | 0.63–0.82 | 0.853 | 0.137 | 0.90 | 0.73 | 0.80 |
| **Random Forest (deployed)** | 0.744 | 0.64–0.83 | 0.858 | 0.137 | 0.90 | 0.72 | 0.80 |
| SVM (RBF) | 0.753 | 0.67–0.85 | 0.857 | 0.134 | 0.87 | 0.73 | 0.79 |

## Is the deployed model better than the baselines?
| Paired PR-AUC difference | Median | 95% interval |
|---|---|---|
| Random Forest − reason-only | +0.022 | −0.006 to +0.050 |
| Random Forest − reason lookup | +0.019 | −0.012 to +0.047 |
| SVM − reason-only | +0.040 | −0.002 to +0.088 |
| Logistic regression − reason-only | +0.006 | −0.023 to +0.032 |

Every interval includes zero. **The data cannot show the Random Forest is better than a model that only knows the reason code.** The result clearly beats the no-skill baseline (PR-AUC 0.744 vs 0.389).

## Original single hold-out (6 employees, 122 events), kept as a sanity check
Random Forest at 0.34: recall 0.851 (95% 0.70–0.95), precision 0.714 (0.50–0.91), F1 0.777, PR-AUC 0.716 (0.52–0.87); confusion matrix TN 59, FP 16, FN 7, TP 40.
Reason-only at the same threshold: recall 0.851, precision 0.727, PR-AUC 0.703. The intervals are wide; two of the six employees supply most rows.

## Time-ordered check (first 25 months → last 12; months are inferred)
Train 448 events (long share 0.42), test 249 events (long share 0.33); 22 of the 26 test-period employees also appear in training.
| Model | PR-AUC | ROC-AUC | Recall | Precision |
|---|---|---|---|---|
| Reason-only | 0.670 | 0.823 | 0.88 | 0.63 |
| Random Forest | 0.687 | 0.839 | 0.89 | 0.58 |
| SVM | 0.669 | 0.840 | 0.88 | 0.59 |
Ranking quality holds up, but precision falls because long absences became rarer. This does not show performance for new employees or workplaces.

## Calibration
Out-of-fold calibration of the Random Forest is imperfect: estimates around 11–21% correspond to observed rates of 4–6%, and estimates around 65% to an observed 80%.
Expected calibration error on the original test set is 0.092. Hence the app rounds probabilities to 5% steps in text and shows the historical rate next to them.

## Permutation importance (drop in PR-AUC)
Reason 0.314, day of week 0.013, month 0.010.

## Conclusions
1. The reason code explains nearly all usable signal; month and weekday add little.
2. The model is useful as a transparent, calibrated-enough triage aid, not as evidence of complex hidden patterns.
3. Claims are limited to this company's data; nothing here supports generalisation to other workplaces or future periods.
