"""
config.py - single source of truth for paths, column names and project decisions.

WHY THIS FILE EXISTS
Every other file (EDA notebook, training script, web app, tests) imports from here,
so a column name or threshold is defined exactly once. If the dataset changes,
you edit this file only.
"""
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (built from this file's location so they work on Windows, Linux and EC2)
# ----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "Absenteeism_at_work.csv"
MODELS_DIR = PROJECT_ROOT / "models"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"

# ----------------------------------------------------------------------------
# Reproducibility
# ----------------------------------------------------------------------------
RANDOM_STATE = 42  # fixed seed so every run gives identical splits and results

# ----------------------------------------------------------------------------
# Target definition (decision confirmed with the project owner)
# ----------------------------------------------------------------------------
RAW_TARGET_COLUMN = "Absenteeism time in hours"
TARGET_COLUMN = "long_absence"        # 1 = absence of 8+ hours, 0 = shorter
LONG_ABSENCE_THRESHOLD_HOURS = 8      # 8 hours = one full working day. The data
                                      # has a natural break here: almost nothing
                                      # between 5 and 8 hours, and 8 is the mode.

# Employee identifier. Used ONLY to keep one employee's rows on the same side of
# a split. It is never a model input (it would let the model memorise people).
GROUP_COLUMN = "ID"

# ----------------------------------------------------------------------------
# Raw column names (after stripping stray whitespace; the CSV has a trailing
# space after "Work load Average/day")
# ----------------------------------------------------------------------------
REASON = "Reason for absence"
MONTH = "Month of absence"
DAY_OF_WEEK = "Day of the week"
SEASONS = "Seasons"
TRANSPORT_EXPENSE = "Transportation expense"
DISTANCE = "Distance from Residence to Work"
SERVICE_TIME = "Service time"
AGE = "Age"
WORKLOAD = "Work load Average/day"
HIT_TARGET = "Hit target"
DISCIPLINARY_FAILURE = "Disciplinary failure"
EDUCATION = "Education"
SON = "Son"
SOCIAL_DRINKER = "Social drinker"
SOCIAL_SMOKER = "Social smoker"
PET = "Pet"
WEIGHT = "Weight"
HEIGHT = "Height"
BMI = "Body mass index"

EXPECTED_RAW_COLUMNS = [
    GROUP_COLUMN, REASON, MONTH, DAY_OF_WEEK, SEASONS, TRANSPORT_EXPENSE, DISTANCE,
    SERVICE_TIME, AGE, WORKLOAD, HIT_TARGET, DISCIPLINARY_FAILURE, EDUCATION, SON,
    SOCIAL_DRINKER, SOCIAL_SMOKER, PET, WEIGHT, HEIGHT, BMI, RAW_TARGET_COLUMN,
]

# ----------------------------------------------------------------------------
# Rows excluded from modelling (see EDA section 4 for the evidence)
#   - Reason for absence == 0   : 43 rows, ALL have 0 hours
#   - Disciplinary failure == 1 : 40 rows, ALL have 0 hours
# These are deterministic rules, not patterns a model should "learn".
# ----------------------------------------------------------------------------
RULE_REASON_CODE = 0
RULE_DISCIPLINARY_VALUE = 1

# ----------------------------------------------------------------------------
# Model input features (the contract between training and the web app)
# ----------------------------------------------------------------------------
# Categorical codes with no numeric meaning -> one-hot encoded.
CATEGORICAL_FEATURES = [REASON, MONTH, DAY_OF_WEEK]
# Already 0/1 -> passed through unchanged.
BINARY_FEATURES = [SOCIAL_DRINKER, SOCIAL_SMOKER]
# Quantities / counts / ordered levels -> standardised.
NUMERIC_FEATURES = [
    TRANSPORT_EXPENSE, DISTANCE, SERVICE_TIME, AGE, EDUCATION, SON, PET, BMI,
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + BINARY_FEATURES + NUMERIC_FEATURES

# Columns deliberately NOT used as features, with the reason (shown in the EDA).
EXCLUDED_FEATURES = {
    GROUP_COLUMN: "Employee identifier: used only for grouped splitting, never a feature.",
    RAW_TARGET_COLUMN: "Source of the target; using it would be direct leakage.",
    DISCIPLINARY_FAILURE: "Constant (always 0) once the 43 rule rows are excluded.",
    SEASONS: "Redundant with Month of absence (derivable from it except at season boundaries).",
    WEIGHT: "Highly correlated with BMI (r=0.90); BMI kept as the single summary.",
    HEIGHT: "Summarised by BMI; fewer sensitive raw attributes is also preferable.",
    WORKLOAD: "Company-level monthly figure that identifies the calendar period; "
              "not known to a user entering one absence. Tested by ablation in Phase 3.",
    HIT_TARGET: "Same as above (period identifier). Tested by ablation in Phase 3.",
}
# Kept here so the Phase 3 ablation can add them back without touching other code.
PERIOD_FEATURES = [WORKLOAD, HIT_TARGET]

# ----------------------------------------------------------------------------
# Preprocessing parameter
# ----------------------------------------------------------------------------
# Reason codes seen in fewer than this many TRAINING rows are pooled into one
# "infrequent" bucket (13 of the 27 codes in the modelling data have <10 rows).
MIN_CATEGORY_FREQUENCY = 10

# ============================================================================
# PHASE 3 DECISION: FINAL MODEL INPUTS
# ----------------------------------------------------------------------------
# The 13 features above (CATEGORICAL/BINARY/NUMERIC/FEATURE_COLUMNS) are the CANDIDATE
# set studied in Phases 2-3. They are kept unchanged so notebooks 01 and 02 stay
# reproducible. Phase 3 showed that, for NEW employees, personal attributes act as an
# employee fingerprint and lower accuracy, so the deployed model uses only these 3:
# ============================================================================
MODEL_FEATURES = [REASON, MONTH, DAY_OF_WEEK]

# Input contract for the app: the values the model accepts. The ranges are the observed
# code ranges in the data (reason 1-28, months 1-12, day codes 2-6). Reason 0 is NOT
# accepted: those records are handled by the documented rule, not by the model.
ALLOWED_VALUES = {
    REASON: list(range(1, 29)),
    MONTH: list(range(1, 13)),
    DAY_OF_WEEK: [2, 3, 4, 5, 6],
}

# ---- Saved artifacts ----
MODEL_PATH = MODELS_DIR / "absenteeism_pipeline.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

# ============================================================================
# PHASE 4: FINAL MODEL SETTINGS
# The 13-feature lists above are kept unchanged so notebooks 01 and 02 stay
# reproducible. The deployed model uses ONLY the three features below
# (decision based on Phase 3, Experiments 2, 3, 5 and 7).
# ============================================================================
FINAL_CATEGORICAL_FEATURES = [REASON, MONTH, DAY_OF_WEEK]
FINAL_FEATURE_COLUMNS = list(FINAL_CATEGORICAL_FEATURES)
FINAL_PREPROCESSOR_KWARGS = dict(categorical=FINAL_CATEGORICAL_FEATURES, binary=[], numeric=[])

# Model-selection rule, fixed BEFORE looking at the test set:
# among the shortlisted models, keep those whose cross-validated PR-AUC is within
# this tolerance of the best AND whose Brier score (probability accuracy) is within
# the Brier tolerance of the best; then choose the SIMPLEST of them.
# 0.02 PR-AUC is about the size of the fold-to-fold noise in paired comparisons
# (Phase 3, Experiment 7: std of paired differences 0.02-0.06).
SELECTION_PR_AUC_TOLERANCE = 0.02
SELECTION_BRIER_TOLERANCE = 0.01

# Decision threshold: a missed long absence (false negative) is assumed to cost this
# many times more than a false alarm (false positive). This is a stated ASSUMPTION about
# the business, not something learned from data; change it here to change the threshold.
FN_TO_FP_COST_RATIO = 2.0

# Saved artifacts
MODEL_VERSION = "1.0.0"
MODEL_PATH = MODELS_DIR / "absenteeism_pipeline.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"
METRICS_PATH = MODELS_DIR / "metrics.json"

# ============================================================================
# PHASE 5: web app assets
# Aggregate-only data for the app's EDA page (no employee-level rows, no IDs),
# generated by `python -m src.make_app_assets`.
# ============================================================================
APP_ASSETS_DIR = PROJECT_ROOT / "reports" / "app_assets"

# ============================================================================
# v2 (React + FastAPI redesign): timeline, analytics assets, simulation defaults
# ============================================================================
# The CSV has no date column, but rows are in chronological order and the monthly
# "Work load Average/day" value changes exactly once per calendar month. We therefore
# reconstruct a month index (1..37). The start month is NOT in the file: it is taken from
# the public dataset documentation (UCI #445: July 2007 - July 2010) and is an assumption.
TIMELINE_START_YEAR = 2007
TIMELINE_START_MONTH = 7
TEMPORAL_TRAIN_FRACTION = 0.70      # first 70% of months = train in the time-ordered check

ANALYTICS_PATH = APP_ASSETS_DIR / "analytics.json"
MODEL_GRID_PATH = APP_ASSETS_DIR / "model_grid.json"
EVALUATION_PATH = APP_ASSETS_DIR / "evaluation.json"
HOURS_BY_REASON_MIN_N = 5           # reasons with fewer records are pooled as "other" in public histograms
LOW_N_THRESHOLD = 10                # rates from fewer records are flagged as unreliable

# Simulation defaults/limits (the simulator is assumption-driven; see src/simulation.py)
WORKING_DAYS_PER_MONTH = 21
SIM_DEFAULT_SEED = 42
SIM_DEFAULT_N = 2000
