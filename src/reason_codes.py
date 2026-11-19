"""
reason_codes.py - human-readable labels for the coded columns.

SOURCE: the public UCI / OpenML documentation of the "Absenteeism at work" dataset
(archive.ics.uci.edu/dataset/445, openml.org/d/42887), checked on 2026-10-16.
  * Day of week: Monday (2) ... Friday (6)                     -> verified in the source text
  * Reason 1-21: ICD chapters I-XXI (verified in source: I-XI, 13 'musculoskeletal', 19 'injury...')
    The titles for chapters 12, 14-18, 20 and 21 were NOT in the text I retrieved; they are the
    standard ICD-10 chapter names. Check them against your own dataset documentation if you can.
  * Reason 22-28: patient follow-up, medical consultation, blood donation, laboratory
    examination, unjustified absence, physiotherapy, dental consultation -> verified in source
  * Reason 0 is NOT documented anywhere I found; the app never labels it.
The dataset file you supplied has no data dictionary, so these labels rest on that public source.
"""

REASON_LABELS = {
    1: "Infectious and parasitic diseases",
    2: "Neoplasms",
    3: "Diseases of the blood and immune mechanism",
    4: "Endocrine, nutritional and metabolic diseases",
    5: "Mental and behavioural disorders",
    6: "Diseases of the nervous system",
    7: "Diseases of the eye and adnexa",
    8: "Diseases of the ear and mastoid process",
    9: "Diseases of the circulatory system",
    10: "Diseases of the respiratory system",
    11: "Diseases of the digestive system",
    12: "Diseases of the skin and subcutaneous tissue",
    13: "Diseases of the musculoskeletal system and connective tissue",
    14: "Diseases of the genitourinary system",
    15: "Pregnancy, childbirth and the puerperium",
    16: "Conditions originating in the perinatal period",
    17: "Congenital malformations",
    18: "Symptoms and abnormal findings (not elsewhere classified)",
    19: "Injury, poisoning and other external-cause consequences",
    20: "External causes of morbidity and mortality",
    21: "Factors influencing health status and health-service contact",
    22: "Patient follow-up",
    23: "Medical consultation",
    24: "Blood donation",
    25: "Laboratory examination",
    26: "Unjustified absence",
    27: "Physiotherapy",
    28: "Dental consultation",
}

DAY_LABELS = {2: "Monday", 3: "Tuesday", 4: "Wednesday", 5: "Thursday", 6: "Friday"}

MONTH_LABELS = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July",
                8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}


def reason_text(code: int) -> str:
    """'23 - Medical consultation'. Falls back to the bare code if a label is unknown."""
    label = REASON_LABELS.get(int(code))
    return f"{int(code)} - {label}" if label else f"{int(code)}"
