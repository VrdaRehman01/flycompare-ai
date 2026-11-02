
from pathlib import Path
import json
import math
import sys

import joblib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
REPORT_PATH = MODEL_DIR / "candidate_comparison.json"
METADATA_PATH = MODEL_DIR / "candidate_metadata.json"


def main(
    report_path=REPORT_PATH,
    metadata_path=METADATA_PATH,
    model_dir=MODEL_DIR,
):
    report_path = Path(report_path)
    metadata_path = Path(metadata_path)
    model_dir = Path(model_dir)

    for path in (report_path, metadata_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if report.get("evaluation_method") != "Expanding-window temporal backtest":
        raise ValueError("Unexpected evaluation method.")

    if report.get("promotion_performed") is not False:
        raise ValueError("Evaluation report must not claim promotion occurred.")

    test_months = report.get("test_months")
    if (
        not isinstance(test_months, list)
        or not test_months
        or not all(isinstance(month, str) and month for month in test_months)
    ):
        raise ValueError("Evaluation test months are missing or invalid.")

    aggregate = report.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ValueError("Aggregate metrics are missing.")

    
    if report.get("candidate_passes") is not True:
        raise ValueError(
            "Candidate failed evaluation. Production must remain unchanged."
        )


    for name in ("reference", "candidate", "baseline"):
        metrics = aggregate.get(name)
        if not isinstance(metrics, dict):
            raise ValueError(f"Missing metrics for {name}.")

        for metric in ("mae_eur", "rmse_eur"):
            value = metrics.get(metric)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"Invalid {metric} for {name}.")

    artifact_name = metadata.get("artifact")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise ValueError("Candidate artifact name is missing.")

    # Only allow a filename inside the configured model directory.
    if Path(artifact_name).name != artifact_name:
        raise ValueError("Candidate artifact must be a filename, not a path.")

    candidate_path = model_dir / artifact_name

    if not candidate_path.is_file():
        raise FileNotFoundError(
            f"Candidate artifact not found: {candidate_path}"
        )

    if metadata.get("status") != "trained_not_evaluated":
        raise ValueError(
            "Candidate metadata status is unexpected. "
            "This guard does not approve or promote models."
        )

    artifact = joblib.load(candidate_path)

    if not isinstance(artifact, dict) or "model" not in artifact:
        raise ValueError("Candidate artifact has no valid model entry.")

    if artifact.get("training_rows") != metadata.get("training_rows"):
        raise ValueError(
            "Candidate training row count does not match metadata."
        )

    if artifact.get("training_months") != metadata.get("training_months"):
        raise ValueError(
            "Candidate training months do not match metadata."
        )

    print("Report and candidate artifact checks passed.")
    print(f"Candidate artifact: {candidate_path.name}")
    print(f"Training rows: {metadata['training_rows']:,}")
    print(f"Training months: {', '.join(metadata['training_months'])}")
    print("Candidate status: trained, not evaluated.")
    print("No model was approved or promoted.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
