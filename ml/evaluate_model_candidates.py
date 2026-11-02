
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
OUTPUT_PATH = PROJECT_ROOT / "ml" / "models" / "candidate_evaluation.json"

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


def metrics(actual, predicted):
    return {
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(
            np.sqrt(mean_squared_error(actual, predicted))
        ),
    }


def main():
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="raise")

    fares = df[TARGET].to_numpy(dtype=float)

    if df.empty:
        raise ValueError("Dataset contains no usable rows.")

    if not np.isfinite(fares).all() or (fares < 0).any():
        raise ValueError("Fare targets must be finite and non-negative.")

    months = sorted(df["departure_month"].unique())

    if len(months) < 4:
        raise ValueError("At least four distinct months are required.")

    # Evaluate November onward. Each fold uses only earlier months.
    test_months = months[2:]
    fold_results = []

    for test_month in test_months:
        train = df[df["departure_month"] < test_month]
        test = df[df["departure_month"] == test_month]

        if train.empty or test.empty:
            raise ValueError(f"Empty temporal split for {test_month}.")

        reference = build_model(REFERENCE_ALPHA)
        candidate = build_model(CANDIDATE_ALPHA)

        y_train = train[TARGET].to_numpy(dtype=float)
        actual = test[TARGET].to_numpy(dtype=float)

        # Both configurations learn from exactly the same training rows.
        reference.fit(train[FEATURES], np.log1p(y_train))
        candidate.fit(train[FEATURES], np.log1p(y_train))

        reference_predictions = predict_fares(reference, test)
        candidate_predictions = predict_fares(candidate, test)

        fold_results.append({
            "test_month": test_month,
            "training_months": sorted(
                train["departure_month"].unique().tolist()
            ),
            "training_rows": int(len(train)),
            "test_rows": int(len(test)),
            "reference": metrics(actual, reference_predictions),
            "candidate": metrics(actual, candidate_predictions),
        })

    # Candidate must improve both metrics in aggregate and on every
    # individual test month to pass this conservative initial rule.
    reference_mae = np.average(
        [f["reference"]["mae_eur"] for f in fold_results],
        weights=[f["test_rows"] for f in fold_results],
    )
    candidate_mae = np.average(
        [f["candidate"]["mae_eur"] for f in fold_results],
        weights=[f["test_rows"] for f in fold_results],
    )

    # Calculate aggregate RMSE from per-fold RMSE values and row counts.
    reference_rmse = np.sqrt(np.average(
        [f["reference"]["rmse_eur"] ** 2 for f in fold_results],
        weights=[f["test_rows"] for f in fold_results],
    ))
    candidate_rmse = np.sqrt(np.average(
        [f["candidate"]["rmse_eur"] ** 2 for f in fold_results],
        weights=[f["test_rows"] for f in fold_results],
    ))

    wins_every_month = all(
        f["candidate"]["mae_eur"] < f["reference"]["mae_eur"]
        and f["candidate"]["rmse_eur"] < f["reference"]["rmse_eur"]
        for f in fold_results
    )

    results = {
        "evaluation_method": "Expanding-window temporal backtest",
        "reference_model": f"Log-Ridge alpha={REFERENCE_ALPHA:g}",
        "candidate_model": f"Log-Ridge alpha={CANDIDATE_ALPHA:g}",
        "test_months": test_months,
        "total_test_rows": sum(f["test_rows"] for f in fold_results),
        "folds": fold_results,
        "aggregate": {
            "reference": {
                "mae_eur": float(reference_mae),
                "rmse_eur": float(reference_rmse),
            },
            "candidate": {
                "mae_eur": float(candidate_mae),
                "rmse_eur": float(candidate_rmse),
            },
        },
        "candidate_passes": bool(
            candidate_mae < reference_mae
            and candidate_rmse < reference_rmse
            and wins_every_month
        ),
        "promotion_performed": False,
        "note": (
            "This evaluates fresh model configurations, not the saved "
            "production artifact. Passing does not authorize promotion."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("\n--- Candidate Evaluation ---")
    for fold in fold_results:
        print(
            f"{fold['test_month']}: "
            f"reference MAE EUR {fold['reference']['mae_eur']:.2f}, "
            f"candidate MAE EUR {fold['candidate']['mae_eur']:.2f}"
        )

    print(f"\nReference MAE: EUR {reference_mae:.2f}")
    print(f"Candidate MAE: EUR {candidate_mae:.2f}")
    print(f"Reference RMSE: EUR {reference_rmse:.2f}")
    print(f"Candidate RMSE: EUR {candidate_rmse:.2f}")
    print(f"Candidate passes all checks: {results['candidate_passes']}")
    print("Production model changed: No")
    print(f"Report saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
