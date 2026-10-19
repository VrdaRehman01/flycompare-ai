
from pathlib import Path

import pandas as pd

# Project root is the parent of the "ml" directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

REQUIRED_COLUMNS = [
    "origin_city",
    "destination_city",
    "departure_month",
    "observations",
    "median_eur",
    "p10_eur",
    "min_eur",
]


def main():
    print("Loading flight fare dataset...")
    print(f"File: {DATA_PATH}")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    print("\n--- Dataset Overview ---")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Column names: {list(df.columns)}")

    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    print("\n--- Data Quality ---")
    print(f"Missing values: {int(df[REQUIRED_COLUMNS].isna().sum().sum()):,}")
    print(f"Duplicate rows: {int(df.duplicated().sum()):,}")

    route_month_key = [
        "origin_city",
        "destination_city",
        "departure_month",
    ]
    print(
        "Duplicate route-month records: "
        f"{int(df.duplicated(subset=route_month_key).sum()):,}"
    )

    print("\n--- Fare Statistics (EUR) ---")
    print(df[["median_eur", "p10_eur", "min_eur"]].describe().round(2))

    print("\n--- Departure Months ---")
    print(df["departure_month"].value_counts().sort_index().to_string())

    print("\n--- Global Route Coverage ---")
    print(f"Unique origin cities: {df['origin_city'].nunique():,}")
    print(f"Unique destination cities: {df['destination_city'].nunique():,}")
    print(
        "Unique origin-destination pairs: "
        f"{df[['origin_city', 'destination_city']].drop_duplicates().shape[0]:,}"
    )

    print("\n--- Validation Checks ---")
    checks = {
        "No missing required values": not df[REQUIRED_COLUMNS].isna().any().any(),
        "No duplicate route-month records": not df.duplicated(
            subset=route_month_key
        ).any(),
        "Fare values are positive": (
            (df[["median_eur", "p10_eur", "min_eur"]] > 0).all().all()
        ),
        "Lower percentile does not exceed median": (
            (df["p10_eur"] <= df["median_eur"]).all()
        ),
        "Minimum does not exceed median": (
            (df["min_eur"] <= df["median_eur"]).all()
        ),
    }

    for description, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {description}")

    if not all(checks.values()):
        raise ValueError("Dataset validation failed. Review the checks above.")

    print("\nDataset validation completed successfully.")


if __name__ == "__main__":
    main()
