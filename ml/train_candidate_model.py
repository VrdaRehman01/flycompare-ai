
from pathlib import Path
import json

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
CANDIDATE_PATH = MODEL_DIR / "fare_log_ridge_candidate.joblib"
METADATA_PATH = MODEL_DIR / "candidate_metadata.json"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"


def build_model():
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "cities_and_month",
                OneHotEncoder(handle_unknown="ignore"),
                FEATURES,
            )
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            ("regressor", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="raise")

    if df.empty:
        raise ValueError("No usable training rows.")

    fares = df[TARGET].to_numpy(dtype=float)

    if not np.isfinite(fares).all() or (fares < 0).any():
        raise ValueError("Fare targets must be finite and non-negative.")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    candidate = build_model()
    candidate.fit(df[FEATURES], np.log1p(fares))

    artifact = {
        "model": candidate,
        "features": FEATURES,
        "target": TARGET,
        "currency": "EUR",
        "target_transform": "log1p",
        "prediction_inverse_transform": "expm1",
        "model_name": "Log-Ridge candidate",
        "training_rows": int(len(df)),
        "training_months": sorted(df["departure_month"].unique().tolist()),
    }

    # Save only to the candidate path. Never overwrite production here.
    joblib.dump(artifact, CANDIDATE_PATH)

    # Verify the candidate artifact can be loaded.
    verified = joblib.load(CANDIDATE_PATH)
    if "model" not in verified:
        CANDIDATE_PATH.unlink(missing_ok=True)
        raise ValueError("Candidate artifact verification failed.")

    metadata = {
        "model_name": artifact["model_name"],
        "training_rows": artifact["training_rows"],
        "training_months": artifact["training_months"],
        "artifact": CANDIDATE_PATH.name,
        "status": "trained_not_evaluated",
    }

    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("Candidate model trained and verified.")
    print(f"Candidate: {CANDIDATE_PATH}")
    print(f"Metadata: {METADATA_PATH}")
    print("Production model was not changed.")
    print("The candidate has not been approved for promotion.")


if __name__ == "__main__":
    main()
