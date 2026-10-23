import argparse
import itertools
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "processed" / "engineered_dataset.csv"
DEFAULT_OUTPUT = ROOT / "reports" / "clustering"

SANCTION_FEATURES = (
    "termination",
    "suspension",
    "content_removal",
    "visibility_restriction",
)
AUTOMATION_FEATURE = "full_automation"
RAW_CODE_COLUMNS = (
    "automated_detection",
    "automated_decision",
    "decision_account",
    "decision_provision",
    "DECISION_VISIBILITY_CONTENT_REMOVED",
    "DECISION_VISIBILITY_CONTENT_DISABLED",
    "DECISION_VISIBILITY_CONTENT_DEMOTED",
    "DECISION_VISIBILITY_CONTENT_AGE_RESTRICTED",
    "DECISION_VISIBILITY_CONTENT_INTERACTION_RESTRICTED",
    "DECISION_VISIBILITY_CONTENT_LABELLED",
)
UNKNOWN = "UNKNOWN"


def _is_missing(value):
    return bool(pd.isna(value))


def _profile_value(value):
    if _is_missing(value):
        return UNKNOWN
    return str(value)


def _derived_state(value, column):
    if _is_missing(value):
        return UNKNOWN
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    normalized = str(value).strip().upper()
    if normalized in ("TRUE", "1", "1.0", "YES"):
        return "TRUE"
    if normalized in ("FALSE", "0", "0.0", "NO"):
        return "FALSE"
    if normalized == UNKNOWN:
        return UNKNOWN
    raise ValueError(
        f"Unexpected value {value!r} in derived column {column!r}; "
        "expected TRUE, FALSE, or UNKNOWN."
    )


def _validate_input(df, platform_column, category_column, count_column):
    required = (
        platform_column,
        category_column,
        count_column,
        *SANCTION_FEATURES,
        AUTOMATION_FEATURE,
    )
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            "Required input columns are missing: " + ", ".join(missing)
        )

    counts = pd.to_numeric(df[count_column], errors="coerce")
    if counts.isna().any():
        raise ValueError(f"{count_column!r} contains missing or non-numeric values.")
    if (counts < 0).any() or not counts.map(math.isfinite).all():
        raise ValueError(f"{count_column!r} must contain finite, non-negative weights.")

    if df.empty:
        raise ValueError("Cannot analyze an empty dataset.")

    return counts


def build_profiles(df, platform_column, category_column, count_column):
    counts = _validate_input(
        df,
        platform_column,
        category_column,
        count_column,
    )
    working = pd.DataFrame(
        {
            "_platform": df[platform_column].map(_profile_value),
            "_category": df[category_column].map(_profile_value),
            "_weight": counts,
        },
        index=df.index,
    )
    feature_states = {}
    features = (*SANCTION_FEATURES, AUTOMATION_FEATURE)
    for feature in features:
        state_column = f"_state_{feature}"
        working[state_column] = df[feature].map(
            lambda value: _derived_state(value, feature)
        )
        feature_states[feature] = state_column

    platforms = sorted(working["_platform"].unique())
    if len(platforms) > 3:
        raise ValueError(
            "The analysis is scoped to at most three platforms; filter the "
            "input to the intended platform set before grouping."
        )

    records = []
    for (platform, category), group in working.groupby(
        ["_platform", "_category"],
        sort=True,
        dropna=False,
    ):
        total_count = float(group["_weight"].sum())
        record = {
            "platform": platform,
            "violation_category": category,
            "source_rows": int(len(group)),
            "total_count": total_count,
        }
        for feature, state_column in feature_states.items():
            state_counts = {
                state: float(
                    group.loc[group[state_column] == state, "_weight"].sum()
                )
                for state in ("TRUE", "FALSE", UNKNOWN)
            }
            known_count = state_counts["TRUE"] + state_counts["FALSE"]
            record[f"{feature}_true_count"] = state_counts["TRUE"]
            record[f"{feature}_false_count"] = state_counts["FALSE"]
            record[f"{feature}_unknown_count"] = state_counts[UNKNOWN]
            record[f"{feature}_known_denominator"] = known_count
            record[f"{feature}_share_known"] = (
                state_counts["TRUE"] / known_count if known_count else None
            )
            record[f"{feature}_unknown_share_total"] = (
                state_counts[UNKNOWN] / total_count if total_count else None
            )
        records.append(record)

    return pd.DataFrame(records).sort_values(
        ["platform", "violation_category"],
        kind="stable",
    ).reset_index(drop=True)


def _wilson_interval(successes, denominator):
    if denominator <= 0 or not float(denominator).is_integer():
        return None, None
    n = int(denominator)
    p = successes / n
    z = 1.959963984540054
    scale = 1 + z * z / n
    center = (p + z * z / (2 * n)) / scale
    margin = (
        z
        * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        / scale
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def build_comparisons(profiles):
    records = []
    features = (*SANCTION_FEATURES, AUTOMATION_FEATURE)
    for category, category_profiles in profiles.groupby(
        "violation_category",
        sort=True,
    ):
        category_profiles = category_profiles.set_index("platform")
        platforms = sorted(category_profiles.index)
        for platform_a, platform_b in itertools.combinations(platforms, 2):
            left = category_profiles.loc[platform_a]
            right = category_profiles.loc[platform_b]
            for feature in features:
                low, high = _wilson_interval(
                    left[f"{feature}_true_count"],
                    left[f"{feature}_known_denominator"],
                )
                records.append(
                    {
                        "violation_category": category,
                        "feature": feature,
                        "platform_a": platform_a,
                        "platform_b": platform_b,
                        "platform_a_share_known": left[f"{feature}_share_known"],
                        "platform_b_share_known": right[f"{feature}_share_known"],
                        "share_difference_a_minus_b": (
                            left[f"{feature}_share_known"]
                            - right[f"{feature}_share_known"]
                            if pd.notna(left[f"{feature}_share_known"])
                            and pd.notna(right[f"{feature}_share_known"])
                            else None
                        ),
                        "platform_a_true_count": left[f"{feature}_true_count"],
                        "platform_a_known_denominator": left[
                            f"{feature}_known_denominator"
                        ],
                        "platform_a_unknown_count": left[
                            f"{feature}_unknown_count"
                        ],
                        "platform_a_total_count": left["total_count"],
                        "platform_a_wilson95_low": low,
                        "platform_a_wilson95_high": high,
                        "platform_b_true_count": right[f"{feature}_true_count"],
                        "platform_b_known_denominator": right[
                            f"{feature}_known_denominator"
                        ],
                        "platform_b_unknown_count": right[
                            f"{feature}_unknown_count"
                        ],
                        "platform_b_total_count": right["total_count"],
                        "platform_b_wilson95_low": _wilson_interval(
                            right[f"{feature}_true_count"],
                            right[f"{feature}_known_denominator"],
                        )[0],
                        "platform_b_wilson95_high": _wilson_interval(
                            right[f"{feature}_true_count"],
                            right[f"{feature}_known_denominator"],
                        )[1],
                    }
                )
    return pd.DataFrame(records)


def build_raw_code_report(df, platform_column, category_column, count_column):
    available = [column for column in RAW_CODE_COLUMNS if column in df.columns]
    columns = [
        "platform",
        "violation_category",
        "source_variable",
        "raw_value",
        "source_rows",
        "weighted_count",
    ]
    if not available:
        return pd.DataFrame(columns=columns)

    working = pd.DataFrame(
        {
            "platform": df[platform_column].map(_profile_value),
            "violation_category": df[category_column].map(_profile_value),
            "weighted_count": pd.to_numeric(df[count_column], errors="raise"),
        },
        index=df.index,
    )
    records = []
    for variable in available:
        raw_values = df[variable].map(
            lambda value: "<MISSING>" if _is_missing(value) else str(value)
        )
        working["_raw_value"] = raw_values
        grouped = working.groupby(
            ["platform", "violation_category", "_raw_value"],
            sort=True,
            dropna=False,
        )
        for (platform, category, raw_value), group in grouped:
            records.append(
                {
                    "platform": platform,
                    "violation_category": category,
                    "source_variable": variable,
                    "raw_value": raw_value,
                    "source_rows": int(len(group)),
                    "weighted_count": float(group["weighted_count"].sum()),
                }
            )
    return pd.DataFrame(records, columns=columns)


def _rms_distance(left, right):
    differences = [
        (a - b) ** 2
        for a, b in zip(left, right)
        if a is not None and b is not None
    ]
    if not differences:
        return None, 0
    return math.sqrt(sum(differences) / len(differences)), len(differences)


def cluster_profiles(profiles, features, distance_threshold, variant):
    if distance_threshold < 0 or not math.isfinite(distance_threshold):
        raise ValueError("Distance threshold must be finite and non-negative.")

    valid_indices = []
    vectors = {}
    excluded = {}
    for index, row in profiles.iterrows():
        values = [row[f"{feature}_share_known"] for feature in features]
        vector = [
            None if pd.isna(value) else float(value)
            for value in values
        ]
        if all(value is None for value in vector):
            excluded[index] = "no_known_feature_shares"
            continue
        valid_indices.append(index)
        vectors[index] = vector

    assignments = []
    for index, row in profiles.iterrows():
        assignments.append(
            {
                "variant": variant,
                "platform": row["platform"],
                "violation_category": row["violation_category"],
                "source_rows": row["source_rows"],
                "total_count": row["total_count"],
                "cluster_id": "",
                "assignment_status": excluded.get(index, "clustered"),
            }
        )

    if not valid_indices:
        return pd.DataFrame(), pd.DataFrame(assignments)

    active = {f"leaf-{index + 1:05d}": {index} for index in valid_indices}
    history = []
    step = 0

    while len(active) > 1:
        candidates = []
        names = sorted(active)
        for name_a, name_b in itertools.combinations(names, 2):
            members_a = active[name_a]
            members_b = active[name_b]
            distances = [
                _rms_distance(vectors[left], vectors[right])
                for left in members_a
                for right in members_b
            ]
            comparable = [pair for pair in distances if pair[0] is not None]
            if not comparable:
                continue
            distance = sum(pair[0] for pair in comparable) / len(comparable)
            members = tuple(sorted(members_a | members_b))
            shared_features = [pair[1] for pair in comparable]
            candidates.append(
                (
                    distance,
                    members,
                    name_a,
                    name_b,
                    min(shared_features),
                    max(shared_features),
                    sum(shared_features) / len(shared_features),
                )
            )

        if not candidates:
            break

        (
            distance,
            members,
            name_a,
            name_b,
            minimum_shared_features,
            maximum_shared_features,
            average_shared_features,
        ) = min(candidates)
        step += 1
        merged_name = f"node-{step:05d}"
        member_labels = [
            {
                "profile_index": int(index),
                "platform": profiles.loc[index, "platform"],
                "violation_category": profiles.loc[
                    index, "violation_category"
                ],
            }
            for index in members
        ]
        history.append(
            {
                "variant": variant,
                "step": step,
                "left_node": name_a,
                "right_node": name_b,
                "merged_node": merged_name,
                "average_linkage_distance": distance,
                "profiles_in_merged_node": len(members),
                "minimum_shared_features": minimum_shared_features,
                "maximum_shared_features": maximum_shared_features,
                "average_shared_features": average_shared_features,
                "members": json.dumps(member_labels, ensure_ascii=False),
            }
        )

        del active[name_a]
        del active[name_b]
        active[merged_name] = set(members)

    membership = {index: {index} for index in valid_indices}
    for entry in history:
        if entry["average_linkage_distance"] > distance_threshold:
            continue
        member_labels = json.loads(entry["members"])
        matched = [member["profile_index"] for member in member_labels]
        merged = set(matched)
        for index in merged:
            membership[index] = merged

    cluster_members = {}
    for index in valid_indices:
        members = tuple(sorted(membership[index]))
        cluster_members.setdefault(members, []).append(index)
    ordered_clusters = sorted(cluster_members, key=lambda members: members)
    cluster_ids = {
        members: f"C{cluster_number:03d}"
        for cluster_number, members in enumerate(ordered_clusters, start=1)
    }
    for assignment in assignments:
        matching_indices = [
            index
            for index in valid_indices
            if profiles.loc[index, "platform"] == assignment["platform"]
            and profiles.loc[index, "violation_category"]
            == assignment["violation_category"]
        ]
        if matching_indices:
            members = tuple(sorted(membership[matching_indices[0]]))
            assignment["cluster_id"] = cluster_ids[members]

    return pd.DataFrame(history), pd.DataFrame(assignments)


def run_analysis(
    data_path,
    output_dir,
    platform_column,
    category_column,
    count_column,
    distance_threshold,
):
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Input data not found: {data_path}")
    headers = pd.read_csv(data_path, nrows=0).columns
    required_columns = {
        platform_column,
        category_column,
        count_column,
        *SANCTION_FEATURES,
        AUTOMATION_FEATURE,
        *(column for column in RAW_CODE_COLUMNS if column in headers),
    }
    df = pd.read_csv(
        data_path,
        usecols=lambda column: column in required_columns,
        low_memory=False,
    )
    profiles = build_profiles(
        df,
        platform_column,
        category_column,
        count_column,
    )
    comparisons = build_comparisons(profiles)
    raw_codes = build_raw_code_report(
        df,
        platform_column,
        category_column,
        count_column,
    )

    cluster_history = []
    cluster_assignments = []
    variants = {
        "sanctions_only": SANCTION_FEATURES,
        "sanctions_plus_automation": (*SANCTION_FEATURES, AUTOMATION_FEATURE),
    }
    for variant, features in variants.items():
        history, assignments = cluster_profiles(
            profiles,
            features,
            distance_threshold,
            variant,
        )
        cluster_history.append(history)
        cluster_assignments.append(assignments)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(output_dir / "weighted_profiles.csv", index=False)
    comparisons.to_csv(output_dir / "platform_comparisons.csv", index=False)
    raw_codes.to_csv(output_dir / "raw_code_counts.csv", index=False)
    pd.concat(cluster_history, ignore_index=True).to_csv(
        output_dir / "hierarchical_merges.csv",
        index=False,
    )
    pd.concat(cluster_assignments, ignore_index=True).to_csv(
        output_dir / "cluster_assignments.csv",
        index=False,
    )

    summary = {
        "input_file": str(data_path.resolve()),
        "platform_column": platform_column,
        "category_column": category_column,
        "count_column": count_column,
        "weight_definition": (
            "Every source row contributes its count-column value to weighted "
            "numerators and denominators."
        ),
        "count_interpretation": (
            "The project plan describes count as the number of decisions "
            "represented by an aggregate row; the prepared local Parquet has "
            "a non-null Int64 count column."
        ),
        "profile_rows": int(len(profiles)),
        "source_rows": int(len(df)),
        "total_weighted_count": float(
            pd.to_numeric(df[count_column], errors="raise").sum()
        ),
        "platforms": profiles["platform"].drop_duplicates().tolist(),
        "observed_platform_count": int(profiles["platform"].nunique()),
        "violation_categories": (
            profiles["violation_category"].drop_duplicates().tolist()
        ),
        "distance_metric": (
            "Root mean squared Euclidean distance over features known for "
            "both profiles; average linkage of profile-pair distances."
        ),
        "distance_threshold": distance_threshold,
        "distance_threshold_note": (
            "The threshold is supplied by the analyst; inspect merge heights "
            "and sensitivity before interpreting cluster assignments."
        ),
        "clustering_features": {
            variant: list(features) for variant, features in variants.items()
        },
        "unknown_handling": (
            "UNKNOWN weight is reported separately; shares use known weighted "
            "count (TRUE + FALSE) as the denominator. Pairwise clustering "
            "distances use only features with known shares for both profiles; "
            "profiles with no known feature shares are excluded."
        ),
        "confidence_intervals": (
            "Wilson 95% intervals are reported only for integer denominators; "
            "they treat represented decisions as independent and are "
            "descriptive, not a test of platform differences."
        ),
        "limitations": [
            "At most three platforms are included; clustering platforms "
            "themselves is not a reliable typology.",
            "Clusters are exploratory and do not establish causality.",
            "Sanction indicators may co-occur and are not a single-class label.",
            "Platform and violation-category labels are not clustering features.",
            "No prediction model is implemented.",
        ],
    }
    with (output_dir / "analysis_summary.json").open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(summary, output_file, ensure_ascii=False, indent=2)
    return summary


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create count-weighted platform-by-category profiles and "
            "exploratory hierarchical clusters."
        )
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--platform-column", required=True)
    parser.add_argument("--category-column", required=True)
    parser.add_argument("--count-column", required=True)
    parser.add_argument("--distance-threshold", type=float, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    summary = run_analysis(
        args.data,
        args.out,
        args.platform_column,
        args.category_column,
        args.count_column,
        args.distance_threshold,
    )
    print(
        f"Saved count-weighted profiles and exploratory clustering "
        f"({summary['profile_rows']} platform-category profiles) to {args.out}"
    )


if __name__ == "__main__":
    main()
