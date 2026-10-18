from pathlib import Path
import polars as pl

INPUT_PATH = r".\data\aggregated-complete.parquet\**\*.parquet"
OUTPUT_PATH = r".\data\dataset_3_platforms_sep_01_29.parquet"

PLATFORMS = ["TikTok", "Instagram", "YouTube"]
START_DATE = pl.datetime(2026, 9, 1)
END_DATE_EXCLUSIVE = pl.datetime(2026, 9, 30)


df = pl.read_parquet(INPUT_PATH)


print("Dataset źródłowy:", df.shape)


dataset = (
    df
    .filter(
        pl.col("platform_name").is_in(PLATFORMS)
        & (pl.col("application_date") >= START_DATE)
        & (pl.col("application_date") < END_DATE_EXCLUSIVE)
    )
)

Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
dataset.write_parquet(OUTPUT_PATH)


print("\n=== WYNIK ===")
print("Wiersze:", dataset.height)
print("Platformy:", dataset["platform_name"].n_unique())
print("Suma count:", dataset["count"].sum())


print("\n=== PLATFORMY ===")
print(
    dataset.group_by("platform_name")
    .agg([
        pl.len().alias("aggregated_rows"),
        pl.col("count").sum().alias("sor_count"),
        pl.col("application_date").min().alias("first_date"),
        pl.col("application_date").max().alias("last_date"),
    ])
    .sort("sor_count", descending=True)
)


print("\nZapisano:", OUTPUT_PATH)
