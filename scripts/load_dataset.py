import pandas as pd

def load_dataset(path):
    return pd.read_parquet(path)


if __name__ == "__main__":
    df = load_dataset(
        r".\data\dataset_3_platforms_sep_01_29.parquet")
    print("Wczytano:", df.shape)