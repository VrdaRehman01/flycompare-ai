
from pathlib import Path
import json
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "fare_log_ridge_model.joblib"

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


def evaluate_candidate(df):
    months = sorted(df["departure_month"].unique())

    if len(months) < 2:
        raise ValueError("At least two departure months are required.")

    test_month = months[-1]
    train = df[df["departure_month"] < test_month]
    test = df[df["departure_month"] == test_month]

    if train.empty or test.empty:
        raise ValueError("The temporal evaluation split is empty.")

    candidate = build_model()
    candidate.fit(
        train[FEATURES],
        np.log1p(train[TARGET].astype(float)),
    )

    actual = test[TARGET].astype(float).to_numpy()
    predicted = np.maximum(
        0,
        np.expm1(candidate.predict(test[FEATURES])),
    )

    baseline = np.full(len(test), train[TARGET].median())

    return {
        "test_month": test_month,
        "training_rows": int(len(train)),
        "test_rows": int(len(test)),
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(np.sqrt(mean_squared_error(actual, predicted))),
        "baseline_mae_eur": float(mean_absolute_error(actual, baseline)),
        "baseline_rmse_eur": float(
            np.sqrt(mean_squared_error(actual, baseline))
        ),
    }


def save_model_atomically(artifact):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file in the same directory, then replace.
    # If writing fails, the existing model remains untouched.
    fd, temporary_name = tempfile.mkstemp(
        prefix="fare-model-",
        suffix=".tmp",
        dir=MODEL_DIR,
    )
    os.close(fd)
    temporary_path = Path(temporary_name)

    try:
        joblib.dump(artifact, temporary_path)
        joblib.load(temporary_path)  # Verify the artifact can be loaded.
        os.replace(temporary_path, MODEL_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="raise")

    if df.empty:
        raise ValueError("No usable training rows.")
    if not np.isfinite(df[TARGET].to_numpy()).all():
        raise ValueError("Fare targets contain invalid numeric values.")
    if (df[TARGET] < 0).any():
        raise ValueError("Fare targets must be non-negative.")

    metrics = evaluate_candidate(df)

    print("\n--- Candidate Evaluation ---")
    print(f"Test month: {metrics['test_month']}")
    print(f"Training rows: {metrics['training_rows']:,}")
    print(f"Test rows: {metrics['test_rows']:,}")
    print(f"Candidate MAE: €{metrics['mae_eur']:.2f}")
    print(f"Baseline MAE: €{metrics['baseline_mae_eur']:.2f}")
    print(f"Candidate RMSE: €{metrics['rmse_eur']:.2f}")
    print(f"Baseline RMSE: €{metrics['baseline_rmse_eur']:.2f}")

    # Require improvement on both metrics before accepting the candidate.
    if not (
        metrics["mae_eur"] < metrics["baseline_mae_eur"]
        and metrics["rmse_eur"] < metrics["baseline_rmse_eur"]
    ):
        raise RuntimeError(
            "Candidate failed acceptance checks. Existing model was not changed."
        )

    print("\nAcceptance checks passed. Training final model on all available rows.")

    final_model = build_model()
    final_model.fit(
        df[FEATURES],
        np.log1p(df[TARGET].astype(float)),
    )

    artifact = {
        "model": final_model,
        "features": FEATURES,
        "target": TARGET,
        "currency": "EUR",
        "target_description": "Historical monthly median one-way fare",
        "training_months": sorted(df["departure_month"].unique().tolist()),
        "training_rows": int(len(df)),
        "target_transform": "log1p",
        "prediction_inverse_transform": "expm1",
        "model_name": "Log-Ridge",
        "evaluation": metrics,
        "evaluation_method": "Latest-month temporal holdout",
    }

    save_model_atomically(artifact)

    report_path = MODEL_DIR / "latest_evaluation.json"
    report_path.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved model: {MODEL_PATH}")
    print(f"Saved evaluation report: {report_path}")
    print("Training completed successfully.")
    print("Predictions are estimates, not live fares.")


if __name__ == "__main__":
    main()
