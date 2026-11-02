
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
OUTPUT_PATH = PROJECT_ROOT / "ml" / "models" / "candidate_comparison.json"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"

REFERENCE_ALPHA = 10.0
CANDIDATE_ALPHA = 1.0


def build_model(alpha: float) -> Pipeline:
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
            ("regressor", Ridge(alpha=alpha, solver="lsqr")),
        ]
    )


def predict_fares(model: Pipeline, rows: pd.DataFrame) -> np.ndarray:
    log_predictions = np.asarray(
        model.predict(rows[FEATURES]), dtype=float
    )

    if not np.isfinite(log_predictions).all():
        raise ValueError("Model produced invalid predictions.")

    return np.maximum(0.0, np.expm1(log_predictions))


def calculate_metrics(actual, predicted):
    return {
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(
            np.sqrt(mean_squared_error(actual, predicted))
        ),
    }


def main():
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="raise")

    fares = df[TARGET].to_numpy(dtype=float)

    if len(df) == 0:
        raise ValueError("Dataset contains no usable rows.")

    if not np.isfinite(fares).all() or (fares < 0).any():
        raise ValueError("Fare targets must be finite and non-negative.")

    months = sorted(df["departure_month"].unique())

    if len(months) < 4:
        raise ValueError(
            "At least four months are required for this evaluation."
        )

    # Start at the third month so every test month has at least
    # two earlier months available for training.
    test_months = months[2:]
    fold_results = []

    all_actual = []
    all_reference_predictions = []
    all_candidate_predictions = []
    all_baseline_predictions = []

    for test_month in test_months:
        train = df[df["departure_month"] < test_month]
        test = df[df["departure_month"] == test_month]

        if train.empty or test.empty:
            raise ValueError(f"Empty train/test split for {test_month}.")

        reference = build_model(REFERENCE_ALPHA)
        candidate = build_model(CANDIDATE_ALPHA)

        y_train = train[TARGET].astype(float).to_numpy()
        actual = test[TARGET].astype(float).to_numpy()

        reference.fit(train[FEATURES], np.log1p(y_train))
        candidate.fit(train[FEATURES], np.log1p(y_train))

        reference_predictions = predict_fares(reference, test)
        candidate_predictions = predict_fares(candidate, test)

        # Simple baseline: predict the median fare in the training data.
        baseline_predictions = np.full(len(test), np.median(y_train))

        fold_results.append({
            "test_month": test_month,
            "training_months": sorted(
                train["departure_month"].unique().tolist()
            ),
            "training_rows": int(len(train)),
            "test_rows": int(len(test)),
            "reference": calculate_metrics(
                actual, reference_predictions
            ),
            "candidate": calculate_metrics(
                actual, candidate_predictions
            ),
            "baseline": calculate_metrics(
                actual, baseline_predictions
            ),
        })

        all_actual.extend(actual)
        all_reference_predictions.extend(reference_predictions)
        all_candidate_predictions.extend(candidate_predictions)
        all_baseline_predictions.extend(baseline_predictions)

    # Aggregate all out-of-time predictions, weighting each row equally.
    actual = np.asarray(all_actual)
    reference_predictions = np.asarray(all_reference_predictions)
    candidate_predictions = np.asarray(all_candidate_predictions)
    baseline_predictions = np.asarray(all_baseline_predictions)

    reference_metrics = calculate_metrics(actual, reference_predictions)
    candidate_metrics = calculate_metrics(actual, candidate_predictions)
    baseline_metrics = calculate_metrics(actual, baseline_predictions)

    results = {
        "evaluation_method": "Expanding-window temporal backtest",
        "reference_model": f"Log-Ridge alpha={REFERENCE_ALPHA:g}",
        "candidate_model": f"Log-Ridge alpha={CANDIDATE_ALPHA:g}",
        "test_months": test_months,
        "total_test_rows": int(len(actual)),
        "folds": fold_results,
        "aggregate": {
            "reference": reference_metrics,
            "candidate": candidate_metrics,
            "baseline": baseline_metrics,
        },
        "candidate_passes": bool(
    candidate_metrics["mae_eur"] < reference_metrics["mae_eur"]
    and candidate_metrics["rmse_eur"] < reference_metrics["rmse_eur"]
    and candidate_metrics["mae_eur"] < baseline_metrics["mae_eur"]
    and candidate_metrics["rmse_eur"] < baseline_metrics["rmse_eur"]
    and all(
        fold["candidate"]["mae_eur"] < fold["reference"]["mae_eur"]
        and fold["candidate"]["rmse_eur"] < fold["reference"]["rmse_eur"]
        and fold["candidate"]["mae_eur"] < fold["baseline"]["mae_eur"]
        and fold["candidate"]["rmse_eur"] < fold["baseline"]["rmse_eur"]
        for fold in fold_results
    )
),
        "promotion_performed": False,
        "note": (
            "This evaluates fresh configurations using historical "
            "time-based folds. It does not evaluate or replace the "
            "currently deployed model."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("\n--- Expanding-Window Model Evaluation ---")
    for fold in fold_results:
        print(
            f"{fold['test_month']}: "
            f"train={fold['training_rows']:,}, "
            f"test={fold['test_rows']:,}, "
            f"reference MAE EUR {fold['reference']['mae_eur']:.2f}, "
            f"candidate MAE EUR {fold['candidate']['mae_eur']:.2f}"
        )

    print(f"\nTotal test rows: {len(actual):,}")
    print(
        f"Reference: MAE EUR {reference_metrics['mae_eur']:.2f}, "
        f"RMSE EUR {reference_metrics['rmse_eur']:.2f}"
    )
    print(
        f"Candidate: MAE EUR {candidate_metrics['mae_eur']:.2f}, "
        f"RMSE EUR {candidate_metrics['rmse_eur']:.2f}"
    )
    print(
        f"Baseline: MAE EUR {baseline_metrics['mae_eur']:.2f}, "
        f"RMSE EUR {baseline_metrics['rmse_eur']:.2f}"
    )
    print(f"Candidate passes all evaluation checks: {results['candidate_passes']}")
    print("Production model changed: No")
    print(f"Report saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
