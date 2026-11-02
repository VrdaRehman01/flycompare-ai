
import json
from pathlib import Path

import importlib.util
import joblib
import pytest
from sklearn.dummy import DummyRegressor


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "ml" / "validate_model_promotion.py"


def create_test_files(tmp_path, report=None, metadata=None):
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    # A tiny valid sklearn model artifact for testing only.
    dummy = DummyRegressor(strategy="constant", constant=1.0)
    dummy.fit([[0], [1]], [1.0, 1.0])

    artifact = {
        "model": dummy,
        "training_rows": 2,
        "training_months": ["2026-09", "2026-10"],
    }
    joblib.dump(artifact, model_dir / "test_candidate.joblib")

    if report is None:
        report = {
            "evaluation_method": "Expanding-window temporal backtest",
            "test_months": ["2026-11"],
            "promotion_performed": False,
            "candidate_passes": True,
            "aggregate": {
                "reference": {"mae_eur": 10.0, "rmse_eur": 12.0},
                "candidate": {"mae_eur": 9.0, "rmse_eur": 11.0},
                "baseline": {"mae_eur": 15.0, "rmse_eur": 18.0},
            },
        }

    if metadata is None:
        metadata = {
            "artifact": "test_candidate.joblib",
            "training_rows": 2,
            "training_months": ["2026-09", "2026-10"],
            "status": "trained_not_evaluated",
        }

    report_path = tmp_path / "candidate_comparison.json"
    metadata_path = tmp_path / "candidate_metadata.json"

    report_path.write_text(json.dumps(report), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    return report_path, metadata_path, model_dir


def run_guard(report_path, metadata_path, model_dir):
    spec = importlib.util.spec_from_file_location(
        "validate_model_promotion", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.main(
        report_path=report_path,
        metadata_path=metadata_path,
        model_dir=model_dir,
    )


def test_valid_artifacts_pass_without_promoting(tmp_path, capsys):
    report, metadata, model_dir = create_test_files(tmp_path)

    assert run_guard(report, metadata, model_dir) == 0

    output = capsys.readouterr().out
    assert "No model was approved or promoted." in output


def test_missing_report_is_rejected(tmp_path):
    report, metadata, model_dir = create_test_files(tmp_path)
    report.unlink()

    with pytest.raises(FileNotFoundError):
        run_guard(report, metadata, model_dir)


def test_malformed_report_is_rejected(tmp_path):
    report, metadata, model_dir = create_test_files(tmp_path)
    report.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        run_guard(report, metadata, model_dir)


def test_candidate_metadata_mismatch_is_rejected(tmp_path):
    report, metadata_path, model_dir = create_test_files(tmp_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["training_rows"] = 999
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="training row count"):
        run_guard(report, metadata_path, model_dir)


def test_candidate_that_fails_evaluation_is_rejected(tmp_path):
    report, metadata, model_dir = create_test_files(tmp_path)

    data = json.loads(report.read_text(encoding="utf-8"))
    data["candidate_passes"] = False
    report.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Candidate failed evaluation"):
        run_guard(report, metadata, model_dir)
