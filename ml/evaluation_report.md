# FlyCompare AI — Fare Model Evaluation

## Dataset and evaluation scope

- Dataset: international route-month fare observations.
- Target: median observed one-way fare in EUR.
- Monthly evaluation: expanding-window backtests.
- January comparison: saved predictions for seen and unseen routes.
- MAE measures average absolute prediction error.
- RMSE penalizes larger errors more heavily.

These are historical fare estimates, not live quotes or guarantees of current availability.

## Monthly backtest results

| test_month   |   train_rows |   test_rows | model           |   MAE_EUR |   RMSE_EUR |
|:-------------|-------------:|------------:|:----------------|----------:|-----------:|
| 2026-10      |        16374 |       45768 | Log-Ridge       |     80.03 |     110.55 |
| 2026-10      |        16374 |       45768 | Median Baseline |     91.25 |     119.68 |
| 2026-10      |        16374 |       45768 | Random Forest   |     71.16 |      96.09 |
| 2026-11      |        62142 |       37684 | Log-Ridge       |     67.21 |      93.76 |
| 2026-11      |        62142 |       37684 | Median Baseline |     91.44 |     113.43 |
| 2026-11      |        62142 |       37684 | Random Forest   |     76.32 |     102.67 |
| 2026-12      |        99826 |       28070 | Log-Ridge       |     65.69 |      90.19 |
| 2026-12      |        99826 |       28070 | Median Baseline |     89.53 |     110.75 |
| 2026-12      |        99826 |       28070 | Random Forest   |     75.79 |     101.39 |
| 2027-01      |       127896 |        2289 | Log-Ridge       |     59.77 |      81.18 |
| 2027-01      |       127896 |        2289 | Median Baseline |     78.19 |      90.80 |
| 2027-01      |       127896 |        2289 | Random Forest   |     55.95 |      72.63 |

## Average performance across evaluated months

| model           |   average_monthly_MAE_EUR |   average_monthly_RMSE_EUR |   months_evaluated |
|:----------------|--------------------------:|---------------------------:|-------------------:|
| Log-Ridge       |                     68.18 |                      93.92 |                  4 |
| Random Forest   |                     69.81 |                      93.19 |                  4 |
| Median Baseline |                     87.60 |                     108.66 |                  4 |

The averages give each evaluated month equal weight. They should not be interpreted as pooled prediction-level metrics.

## January 2027 route generalization

| group         | model           |   rows |   MAE_EUR |   RMSE_EUR |
|:--------------|:----------------|-------:|----------:|-----------:|
| All routes    | Log-Ridge       |   2289 |     59.77 |      81.18 |
| All routes    | Random Forest   |   2289 |     55.95 |      72.63 |
| All routes    | Hybrid          |   2289 |     55.45 |      72.03 |
| All routes    | Median baseline |   2289 |     78.19 |      90.80 |
| Seen routes   | Log-Ridge       |   2213 |     59.40 |      80.51 |
| Seen routes   | Random Forest   |   2213 |     54.92 |      70.94 |
| Seen routes   | Hybrid          |   2213 |     54.92 |      70.94 |
| Seen routes   | Median baseline |   2213 |     77.97 |      90.24 |
| Unseen routes | Log-Ridge       |     76 |     70.70 |      98.63 |
| Unseen routes | Random Forest   |     76 |     85.96 |     110.99 |
| Unseen routes | Hybrid          |     76 |     70.70 |      98.63 |
| Unseen routes | Median baseline |     76 |     84.77 |     105.91 |

## Interpretation

- Compare models across multiple months rather than selecting one solely from the January result.
- Random Forest performs strongly on routes represented in its training data, but its unseen-route performance needs attention.
- Log-Ridge is a candidate for unseen routes, based on the January experiment.
- The hybrid rule was developed after examining January results. Its January performance is exploratory and is not an unbiased final test of that selection strategy.
- The dataset has limited time coverage and uneven route coverage. Results may not generalize to future months or all international routes.

## Recommended next steps

1. Validate the route-based hybrid rule on additional time periods.
2. Keep a final test period untouched during model selection.
3. Check errors by fare range and route coverage.
4. Select and save the final model with its feature schema and evaluation metadata.
5. Integrate predictions into the backend only after validation.
