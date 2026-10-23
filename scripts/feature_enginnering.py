import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "processed" / "cleaned_dataset.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "engineered_dataset.csv"
CODEBOOK_PATH = ROOT / "config" / "codebook.json"

UNKNOWN = "UNKNOWN"

def check_rule(row, rule):
    column = rule["variable"]

    if column not in row.index or pd.isna(row[column]):
        return UNKNOWN

    value = row[column]

    if "equals" in rule:
        expected = rule["equals"]

        if isinstance(expected, bool):
            value = str(value).strip().lower()

            if value in ("true", "yes"):
                value = True
            elif value in ("false", "no"):
                value = False
            else:
                return UNKNOWN

        return value == expected

    if "starts_with" in rule:
        return str(value).strip().startswith(rule["starts_with"])

    return UNKNOWN


def evaluate(row, rules, operator="OR"):
    results = [check_rule(row, rule) for rule in rules]

    if operator == "OR":
        if True in results:
            return True
        if all(value is False for value in results):
            return False
        return False

    if operator == "AND":
        if False in results:
            return False
        if all(value is True for value in results):
            return True
        return False

    raise ValueError(f"Unknown operator: {operator}")


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Nie znaleziono danych: {INPUT_PATH}")

    if not CODEBOOK_PATH.exists():
        raise FileNotFoundError(f"Nie znaleziono codebooka: {CODEBOOK_PATH}")

    with open(CODEBOOK_PATH, encoding="utf-8") as f:
        codebook = json.load(f)

    df = pd.read_csv(INPUT_PATH)
    print("Wczytano dane:", df.shape)

    automation = codebook["automation"]

    rules = [
        {
            "variable": "automated_detection",
            "equals": automation["rule"]["automated_detection"],
        },
        {
            "variable": "automated_decision",
            "equals": automation["rule"]["automated_decision"],
        },
    ]

    df[automation["output_variable"]] = df.apply(
        lambda row: evaluate(row, rules, "AND"),
        axis=1,
    )

    for name, definition in codebook["derived_variables"].items():
        df[name] = df.apply(
            lambda row: evaluate(
                row,
                definition["rules"],
                definition.get("operator", "OR"),
            ),
            axis=1,
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")



if __name__ == "__main__":
    main()
