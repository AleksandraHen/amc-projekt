from pathlib import Path
import pandas as pd
from load_dataset import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "dataset_3_platforms_sep_01_29.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "cleaned_dataset.csv"


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    columns_to_drop = [
        "account_type",
        "incompatible_content_illegal",
        "content_language",
        "CONTENT_TYPE_APP",
        "CONTENT_TYPE_PRODUCT",
        "CONTENT_TYPE_LINK",
        "CONTENT_TYPE_STICKER",
        "CONTENT_TYPE_HASHTAG",
    ]

    existing_columns = [
        col for col in columns_to_drop
        if col in df.columns
    ]

    df = df.drop(columns=existing_columns)

    return df


if __name__ == "__main__":
    df = load_dataset(INPUT_PATH)
    print("Wczytano:", df.shape)
    df = clean_dataset(df)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print("Zapisano oczyszczone dane:", OUTPUT_PATH)
    print("Końcowy rozmiar:", df.shape)
