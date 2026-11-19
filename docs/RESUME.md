# Resume and portfolio text

**Absenteeism Intelligence & Workforce Planning System** · Python, scikit-learn, FastAPI, React, TypeScript, AWS (EC2, S3, CloudFront)

*Resume bullets*
* Audited and redesigned a Streamlit absenteeism model into a full-stack system (FastAPI + React/TypeScript) with pattern discovery, explainable prediction and an assumption-driven workforce-planning simulator; 141 Python and 29 frontend tests.
* Replaced a single 6-employee test split with employee-grouped repeated cross-validation, bootstrap intervals and a time-ordered check; found that the deployed Random Forest (PR-AUC 0.744) was statistically indistinguishable from a one-feature baseline (difference +0.022, 95% CI −0.006 to +0.050) and reported it as such.
* Discovered that the dataset's row order is chronological and reconstructed a validated 37-month timeline (36/36 consecutive steps; fails on shuffled data) to enable temporal validation and drift analysis.
* Built a seeded Monte Carlo staffing simulator that separates user assumptions from measured absence durations; showed that long absences are 39% of events but 80% of lost hours.
* Designed a privacy-conscious API (aggregates only, small-cell pooling, strict Pydantic validation, one error contract) and a low-cost AWS deployment (private S3 + CloudFront, EC2 behind nginx with secret-header origin protection, systemd auto-restart).

*Two-sentence summary for interviews*
I rebuilt an absenteeism-prediction capstone into a tested React + FastAPI application and re-evaluated its model with grouped cross-validation and bootstrap intervals, which showed the model adds little beyond the recorded absence reason. I then built an honest planning simulator on top of the measured duration data and documented exactly what the data can and cannot support.
