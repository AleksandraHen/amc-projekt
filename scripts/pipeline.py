import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run dataset preparation, feature engineering, and reports."
    )
    parser.add_argument(
        "--platform-column",
        help="Actual platform column name from the source data schema.",
    )
    parser.add_argument(
        "--category-column",
        help="Actual violation-category column name from the source schema.",
    )
    parser.add_argument(
        "--count-column",
        help="Actual aggregate decision-count column name from the source schema.",
    )
    parser.add_argument(
        "--cluster-distance-threshold",
        type=float,
        help="Chosen hierarchical-clustering cut distance for this data.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    clustering_options = (
        args.platform_column,
        args.category_column,
        args.count_column,
        args.cluster_distance_threshold,
    )
    if any(value is not None for value in clustering_options) and not all(
        value is not None for value in clustering_options
    ):
        raise SystemExit(
            "Clustering requires --platform-column, --category-column, "
            "--count-column, and --cluster-distance-threshold together."
        )

    steps = [
        (
            "Unit tests",
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ],
        ),
        *[
            (
                step_name,
                [sys.executable, "-X", "utf8", str(script_path)],
            )
            for step_name, script_path in [
                ("Load dataset", SCRIPTS_DIR / "load_dataset.py"),
                ("Clean dataset", SCRIPTS_DIR / "clean_dataset.py"),
                ("Gold standard tests", SCRIPTS_DIR / "gold_standard.py"),
                (
                    "Feature engineering",
                    SCRIPTS_DIR / "feature_enginnering.py",
                ),
                (
                    "Instrument validation",
                    SCRIPTS_DIR / "instrument_validation.py",
                ),
            ]
        ],
    ]

    if all(value is not None for value in clustering_options):
        steps.append(
            (
                "Profile and cluster",
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(SCRIPTS_DIR / "clustering.py"),
                    "--platform-column",
                    args.platform_column,
                    "--category-column",
                    args.category_column,
                    "--count-column",
                    args.count_column,
                    "--distance-threshold",
                    str(args.cluster_distance_threshold),
                ],
            )
        )

    for step_number, (step_name, command) in enumerate(steps, start=1):
        print(f"[{step_number}/{len(steps)}] {step_name}")
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
        )
        print(f"Completed: {step_name}")

    if not all(value is not None for value in clustering_options):
        print(
            "Clustering skipped: supply the actual schema column names and "
            "a reviewed distance threshold to enable it."
        )


if __name__ == "__main__":
    main()
