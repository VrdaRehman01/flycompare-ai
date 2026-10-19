
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]

MONTHLY_PATH = ROOT / "ridge_forest_monthly_comparison.csv"
HYBRID_PATH = ROOT / "hybrid_model_predictions.csv"

REPORT_PATH = ROOT / "ml" / "evaluation_report.md"
SUMMARY_PATH = ROOT / "ml" / "evaluation_summary.csv"


def calculate_metrics(actual, predicted):
    return {
        "MAE_EUR": mean_absolute_error(actual, predicted),
        "RMSE_EUR": np.sqrt(mean_squared_error(actual, predicted)),
    }


def main():
    # 1. Load the existing monthly backtest results.
    monthly = pd.read_csv(MONTHLY_PATH)

    required_columns = {
        "test_month",
        "train_rows",
        "test_rows",
        "model",
        "MAE_EUR",
        "RMSE_EUR",
    }

    missing = required_columns - set(monthly.columns)
    if missing:
        raise ValueError(
            f"Monthly comparison CSV is missing columns: {sorted(missing)}"
        )

    monthly["MAE_EUR"] = pd.to_numeric(monthly["MAE_EUR"])
    monthly["RMSE_EUR"] = pd.to_numeric(monthly["RMSE_EUR"])

    # Average performance across months. These are monthly averages,
    # not metrics calculated by pooling every prediction together.
    averages = (
        monthly.groupby("model", as_index=False)
        .agg(
            average_monthly_MAE_EUR=("MAE_EUR", "mean"),
            average_monthly_RMSE_EUR=("RMSE_EUR", "mean"),
            months_evaluated=("test_month", "nunique"),
        )
        .sort_values("average_monthly_MAE_EUR")
    )

    averages.to_csv(SUMMARY_PATH, index=False)

    # 2. Evaluate the saved January hybrid predictions.
    hybrid = pd.read_csv(HYBRID_PATH)

    prediction_columns = {
        "actual_eur",
        "seen_route",
        "log_ridge_eur",
        "random_forest_eur",
        "hybrid_eur",
        "baseline_eur",
    }

    missing = prediction_columns - set(hybrid.columns)
    if missing:
        raise ValueError(
            f"Hybrid predictions CSV is missing columns: {sorted(missing)}"
        )

    actual = hybrid["actual_eur"].to_numpy()
    seen = hybrid["seen_route"].astype(bool).to_numpy()

    groups = {
        "All routes": np.ones(len(hybrid), dtype=bool),
        "Seen routes": seen,
        "Unseen routes": ~seen,
    }

    prediction_map = {
        "Log-Ridge": "log_ridge_eur",
        "Random Forest": "random_forest_eur",
        "Hybrid": "hybrid_eur",
        "Median baseline": "baseline_eur",
    }

    hybrid_rows = []

    for group_name, mask in groups.items():
        for model_name, column in prediction_map.items():
            if not mask.any():
                continue

            metrics = calculate_metrics(
                actual[mask],
                hybrid[column].to_numpy()[mask],
            )

            hybrid_rows.append({
                "group": group_name,
                "model": model_name,
                "rows": int(mask.sum()),
                **metrics,
            })

    hybrid_summary = pd.DataFrame(hybrid_rows)

    # 3. Write a readable Markdown report.
    lines = [
        "# FlyCompare AI — Fare Model Evaluation",
        "",
        "## Dataset and evaluation scope",
        "",
        "- Dataset: international route-month fare observations.",
        "- Target: median observed one-way fare in EUR.",
        "- Monthly evaluation: expanding-window backtests.",
        "- January comparison: saved predictions for seen and unseen routes.",
        "- MAE measures average absolute prediction error.",
        "- RMSE penalizes larger errors more heavily.",
        "",
        "These are historical fare estimates, not live quotes or guarantees "
        "of current availability.",
        "",
        "## Monthly backtest results",
        "",
        monthly.sort_values(["test_month", "model"]).to_markdown(
            index=False, floatfmt=".2f"
        ),
        "",
        "## Average performance across evaluated months",
        "",
        averages.to_markdown(index=False, floatfmt=".2f"),
        "",
        "The averages give each evaluated month equal weight. They should "
        "not be interpreted as pooled prediction-level metrics.",
        "",
        "## January 2027 route generalization",
        "",
        hybrid_summary.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## Interpretation",
        "",
        "- Compare models across multiple months rather than selecting "
        "one solely from the January result.",
        "- Random Forest performs strongly on routes represented in its "
        "training data, but its unseen-route performance needs attention.",
        "- Log-Ridge is a candidate for unseen routes, based on the "
        "January experiment.",
        "- The hybrid rule was developed after examining January results. "
        "Its January performance is exploratory and is not an unbiased "
        "final test of that selection strategy.",
        "- The dataset has limited time coverage and uneven route coverage. "
        "Results may not generalize to future months or all international "
        "routes.",
        "",
        "## Recommended next steps",
        "",
        "1. Validate the route-based hybrid rule on additional time periods.",
        "2. Keep a final test period untouched during model selection.",
        "3. Check errors by fare range and route coverage.",
        "4. Select and save the final model with its feature schema and "
        "evaluation metadata.",
        "5. Integrate predictions into the backend only after validation.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("Evaluation report generated successfully.")
    print(f"Markdown report: {REPORT_PATH}")
    print(f"Model summary CSV: {SUMMARY_PATH}")
    print("\nAverage monthly metrics:")
    print(averages.to_string(index=False))
    print("\nJanuary hybrid evaluation:")
    print(hybrid_summary.to_string(index=False))


if __name__ == "__main__":
    main()
