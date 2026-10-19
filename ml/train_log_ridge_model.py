
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "fare_log_ridge_model.joblib"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)

    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)

    # Train the final artifact on all currently available observations.
    X = df[FEATURES]
    y = df[TARGET].astype(float)

    if (y < 0).any():
        raise ValueError("Fare targets must be non-negative.")

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "cities_and_month",
                OneHotEncoder(handle_unknown="ignore"),
                FEATURES,
            )
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            ("regressor", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )

    # Train in log space; inference must reverse this with expm1().
    pipeline.fit(X, np.log1p(y))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": pipeline,
            "features": FEATURES,
            "target": TARGET,
            "currency": "EUR",
            "target_description": (
                "Historical monthly median one-way fare"
            ),
            "training_months": sorted(
                df["departure_month"].unique().tolist()
            ),
            "training_rows": len(df),
            "target_transform": "log1p",
            "prediction_inverse_transform": "expm1",
            "model_name": "Log-Ridge",
        },
        MODEL_PATH,
    )

    print(f"Training rows: {len(df):,}")
    print(f"Training months: {sorted(df['departure_month'].unique())}")
    print(f"Saved model to: {MODEL_PATH}")
    print("Training complete.")
    print("Important: predictions are estimates, not live fares.")


if __name__ == "__main__":
    main()
