import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CODEBOOK_PATH = PROJECT_ROOT / "config" / "codebook.json"
GOLD_STANDARD_PATH = (PROJECT_ROOT / "data" / "gold_standard" / "gold_standard.json")

with CODEBOOK_PATH.open("r", encoding="utf-8") as f:
    codebook = json.load(f)

with GOLD_STANDARD_PATH.open("r", encoding="utf-8") as f:
    gold = json.load(f)


def to_bool(value):
    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()

    if value in ["true", "1", "1.0", "yes"]:
        return True

    if value in ["false", "0", "0.0", "no"]:
        return False

    return None


def classify_automation(row):
    detection = to_bool(row.get("automated_detection"))
    decision = row.get("automated_decision")

    if detection is None or pd.isna(decision):
        return "UNKNOWN"

    return (
        detection is True
        and str(decision).strip()
        == "AUTOMATED_DECISION_FULLY"
    )


def classify_sanctions(row):
    account = row.get("decision_account")
    provision = row.get("decision_provision")

    account = (
        str(account).strip()
        if pd.notna(account) else None
    )
    provision = (
        str(provision).strip()
        if pd.notna(provision) else None
    )

    return {
        "termination": (
            account == "DECISION_ACCOUNT_TERMINATED"
            or provision == "DECISION_PROVISION_TOTAL_TERMINATION"
        ),
        "suspension": (
            account == "DECISION_ACCOUNT_SUSPENDED"
            or (
                provision is not None
                and provision.startswith(
                    "DECISION_PROVISION_PARTIAL_"
                )
            )
        ),
        "content_removal": (
            to_bool(
                row.get("DECISION_VISIBILITY_CONTENT_REMOVED")
            ) is True
            or to_bool(
                row.get("DECISION_VISIBILITY_CONTENT_DISABLED")
            ) is True
        ),
        "visibility_restriction": any(
            to_bool(row.get(col)) is True
            for col in [
                "DECISION_VISIBILITY_CONTENT_DEMOTED",
                "DECISION_VISIBILITY_CONTENT_AGE_RESTRICTED",
                "DECISION_VISIBILITY_CONTENT_INTERACTION_RESTRICTED",
                "DECISION_VISIBILITY_CONTENT_LABELLED",
            ]
        )
    }


passed = 0
failed = 0
results = []

for case in gold["test_cases"]:
    inputs = case["inputs"]
    test_id = case["id"]
    variable = case.get("variable", "")

    if test_id.startswith("AUTO"):
        actual = classify_automation(inputs)

    else:
        sanctions = classify_sanctions(inputs)

        if variable in sanctions:
            actual = sanctions[variable]
        else:
            actual = sanctions.get(variable)

    expected = case["expected"]
    status = actual == expected

    passed += int(status)
    failed += int(not status)

    results.append({
        "test_id": test_id,
        "expected": expected,
        "actual": actual,
        "status": "PASS" if status else "FAIL"
    })

report = pd.DataFrame(results)
report.to_csv("gold_standard_report.csv", index=False)

print(report)
print("\nLiczba testów:", len(results))
print("PASS:", passed)
print("FAIL:", failed)

if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("Wykryto rozbieżności")
