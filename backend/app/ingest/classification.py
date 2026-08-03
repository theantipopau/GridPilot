"""Non-teaching period classification, per meanings confirmed with the
school on 2026-08-03 (see docs/data-formats.md #5):
  BREAK-*  -> break time
  ASM-*    -> assembly
  GP-*     -> "general purpose" (Year 11/12 early-leave / study block)
This mapping lives in one place so a new non-teaching subject code found
in a future export only needs to be added here, not hunted down across
the ingestion/analysis code."""

SUBJECT_CODE_ENTRY_TYPE = {
    "BREAK": "BREAK",
    "ASM": "ASSEMBLY",
    "GP": "GENERAL_PURPOSE",
}

PERIOD_KIND_ENTRY_TYPE = {
    "REGISTRATION": "REGISTRATION",
    "BREAK": "BREAK",
}

TEACHER_STAFF_CATEGORY = {
    "T": "TEACHER",
    "GC": "GUIDANCE_COUNSELLOR",
    "SO": "SUPPORT_OFFICER",
    "CLT": "COLLEGE_LEADERSHIP",
}


def classify_entry_type(period_entry_kind: str, subject_code: str | None) -> str:
    if period_entry_kind in PERIOD_KIND_ENTRY_TYPE:
        return PERIOD_KIND_ENTRY_TYPE[period_entry_kind]
    if subject_code and subject_code in SUBJECT_CODE_ENTRY_TYPE:
        return SUBJECT_CODE_ENTRY_TYPE[subject_code]
    return "LESSON"


def classify_period_kind(code: str) -> str:
    if code == "FR":
        return "REGISTRATION"
    if code in ("FB", "SB"):
        return "BREAK"
    return "LESSON_SLOT"
