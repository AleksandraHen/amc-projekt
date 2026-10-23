import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from feature_enginnering import evaluate


CODEBOOK_PATH = PROJECT_ROOT / "config" / "codebook.json"
GOLD_STANDARD_PATH = (
    PROJECT_ROOT / "data" / "gold_standard" / "gold_standard.json"
)
REPORT_PATH = (
    PROJECT_ROOT / "reports" / "instrument_validation"
    / "gold_standard_report.csv"
)

with CODEBOOK_PATH.open("r", encoding="utf-8") as f:
    CODEBOOK = json.load(f)

with GOLD_STANDARD_PATH.open("r", encoding="utf-8") as f:
    GOLD_STANDARD = json.load(f)


def classify_automation(row):
    definition = CODEBOOK["automation"]
    rules = [
        {
            "variable": "automated_detection",
            "equals": definition["rule"]["automated_detection"],
        },
        {
            "variable": "automated_decision",
            "equals": definition["rule"]["automated_decision"],
        },
    ]
    return evaluate(row, rules, "AND")


def classify_sanctions(row):
    return {
        name: evaluate(
            row,
            definition["rules"],
            definition.get("operator", "OR"),
        )
        for name, definition in CODEBOOK["derived_variables"].items()
    }


def classify_case(case):
    inputs = case["inputs"]
    variable = case.get("variable", CODEBOOK["automation"]["output_variable"])

    if variable == CODEBOOK["automation"]["output_variable"]:
        return classify_automation(inputs)

    return classify_sanctions(inputs).get(variable)


def main():
    results = []
    for case in GOLD_STANDARD["test_cases"]:
        actual = classify_case(case)
        expected = case["expected"]
        results.append(
            {
                "test_id": case["id"],
                "expected": expected,
                "actual": actual,
                "status": "PASS" if actual == expected else "FAIL",
            }
        )

    report = pd.DataFrame(results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_PATH, index=False, encoding="utf-8")

    passed = int((report["status"] == "PASS").sum())
    failed = len(report) - passed
    print(report)
    print("\nLiczba testów:", len(results))
    print("PASS:", passed)
    print("FAIL:", failed)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
