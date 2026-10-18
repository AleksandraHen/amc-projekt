def clean_dataset(df):
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

    cols_to_drop = [
        col for col in df.columns
        if col.startswith((
            "STATEMENT_CATEGORY_",
            "KEYWORD_",
        ))
    ]

    df = df.drop(columns=cols_to_drop)

    df.to_csv("cleaned_dataset.csv", index=False)


    print("Usunięto kolumny stałe:", len(cols_to_drop))
    print("Usunięto pozostałe kolumny:", len(existing_columns))
    print("Pozostałe kolumny:", df.shape[1])

    return df