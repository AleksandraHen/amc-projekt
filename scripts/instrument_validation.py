import argparse
import json
from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
MISSING = "<NA>"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(value):
    if value is None or pd.isna(value):
        return MISSING

    value = str(value).strip().upper()

    if value in ("YES", "TRUE"):
        return "TRUE"
    if value in ("NO", "FALSE"):
        return "FALSE"
    if value in ("NONE", "NAN", "<NA>"):
        return MISSING
    if value == "UNKNOWN":
        return "UNKNOWN"

    value = value.replace("AUTOMATED_DECISION_", "")

    if value == "FULLY_AUTOMATED":
        return "FULLY"
    if value == "PARTIALLY_AUTOMATED":
        return "PARTIALLY"

    return value


def main():
    parser = argparse.ArgumentParser(
        description="Porównanie dataset z gold standard."
    )
    parser.add_argument("--data",default=ROOT / "data/processed/engineered_dataset.csv",)
    parser.add_argument("--codebook",default=ROOT / "config/codebook.json",)
    parser.add_argument("--gold", default=ROOT / "data/gold_standard/gold_standard.json",)
    parser.add_argument("--out",default=ROOT / "reports/instrument_validation",)

    args = parser.parse_args()

    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.data, low_memory=False)
    codebook = load_json(args.codebook)
    gold = load_json(args.gold)

    default_variable = codebook.get("automation", {}).get("output_variable", "full_automation")

    results = []

    for case in gold.get("test_cases", []):
        case_id = case.get("id", case.get("test_case_id"))
        inputs = case.get("inputs") or {}
        expected = case.get("expected", case.get("expected_output"))

        if expected is None:
            results.append({
                "case": case_id,
                "variable": case.get("variable", default_variable),
                "status": "MISSING_EXPECTED",
                "rows": 0,
                "error": "No expected value in gold standard.",
            })
            continue

        if isinstance(expected, dict):
            expected_values = expected
        else:
            variable = case.get("variable", default_variable)
            expected_values = {variable: expected}

        for variable, expected_value in expected_values.items():
            result = {
                "case": case_id,
                "variable": variable,
                "expected": normalize(expected_value),
                "actual_values": "",
                "status": "",
                "rows": 0,
                "matching_rows": 0,
                "mismatching_rows": 0,
                "error": "",
            }

            if variable not in df.columns:
                result["status"] = "MISSING_COLUMN"
                result["error"] = f"Column '{variable}' not found."
                results.append(result)
                continue

            mask = pd.Series(True, index=df.index)
            missing_columns = []

            for column, value in inputs.items():
                if column not in df.columns:
                    missing_columns.append(column)
                    continue

                mask &= df[column].map(normalize).eq(normalize(value))

            if missing_columns:
                result["status"] = "MISSING_INPUT_COLUMN"
                result["error"] = (
                    "Missing input columns: " + ", ".join(missing_columns)
                )
                results.append(result)
                continue

            values = df.loc[mask, variable].map(normalize)
            result["rows"] = len(values)

            if values.empty:
                result["status"] = "NOT_OBSERVED"
                result["error"] = "No rows matched the test inputs."
                results.append(result)
                continue

            result["actual_values"] = json.dumps(
                values.value_counts(dropna=False).to_dict(),
                ensure_ascii=False,
            )

            matches = values.eq(normalize(expected_value))
            result["matching_rows"] = int(matches.sum())
            result["mismatching_rows"] = int((~matches).sum())

            if matches.all():
                result["status"] = "PASS"
            else:
                result["status"] = "FAIL"
                result["error"] = (
                    f"{result['mismatching_rows']} of {len(values)} "
                    "rows did not match the expected value."
                )

            results.append(result)

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        output / "gold_vs_dataset.csv",
        index=False,
        encoding="utf-8-sig",
    )

    counts = results_df["status"].value_counts().to_dict()

    failed = {
        "FAIL",
        "MISSING_COLUMN",
        "MISSING_INPUT_COLUMN",
        "MISSING_EXPECTED",
    }

    if results_df.empty:
        verdict = "NO_RESULTS"
    elif results_df["status"].isin(failed).any():
        verdict = "FAIL"
    elif (results_df["status"] == "NOT_OBSERVED").any():
        verdict = "WARN"
    else:
        verdict = "PASS"

    summary = {
        "verdict": verdict,
        "dataset_rows": len(df),
        "gold_cases": len(gold.get("test_cases", [])),
        "validation_results": len(results),
        "status_counts": counts,
        "results": results,
    }

    with open(output / "validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Liczba testów: {len(results)}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")

    print(f"Raport zapisano w: {output}")

    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
