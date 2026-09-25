"""Candidate filtering and inference using the existing saved pipelines."""
from pathlib import Path

import joblib
import pandas as pd

from feature_engineering import build_pair_features
from models import RideRequest

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models" if (ROOT / "models").is_dir() else ROOT
CLASS_FEATURES = [
    "pickup_distance_km", "time_difference_min", "route_overlap_percent",
    "detour_km", "destination_compatibility", "preference_compatible",
]
REG_FEATURES = [
    "pickup_distance_km", "time_difference_min", "route_overlap_percent",
    "destination_compatibility", "preference_compatible",
]
_classifier = _regressor = None


def load_models():
    global _classifier, _regressor
    if _classifier is None:
        _classifier = joblib.load(MODEL_DIR / "best_rickshaw_classification_model.pkl")
        _regressor = joblib.load(MODEL_DIR / "best_rickshaw_regression_model.pkl")
        # One-row predictions do not benefit from a process pool and can fail
        # to start one in restricted Windows environments.
        for pipeline in (_classifier, _regressor):
            for _, estimator in getattr(pipeline, "steps", []):
                if hasattr(estimator, "n_jobs"):
                    estimator.n_jobs = 1
    return _classifier, _regressor


def _score_pair(ride, candidate):
    features = build_pair_features(ride, candidate)
    if not features["preference_compatible"]:
        return None, "preference"
    if features["pickup_distance_km"] > 5:
        return None, "distance"
    if features["time_difference_min"] > 30:
        return None, "time"

    classifier, regressor = load_models()
    regression_input = pd.DataFrame([features], columns=REG_FEATURES)
    detour = max(0.0, float(regressor.predict(regression_input)[0]))
    class_data = {**features, "detour_km": detour}
    frame = pd.DataFrame([class_data], columns=CLASS_FEATURES)
    prediction = int(classifier.predict(frame)[0])
    probability = float(
        classifier.predict_proba(frame)[0,
            list(classifier.classes_).index(1)]
    )
    if prediction != 1:
        return None, "model"

    stored = {
        key: features[key]
        for key in (
            "pickup_distance_km", "time_difference_min", "route_overlap_percent",
            "destination_compatibility",
        )
    }
    stored["estimated_detour_km"] = detour
    return {
        "ride": candidate,
        "probability": probability,
        "features": features,
        "estimated_detour_km": detour,
        "stored_features": stored,
    }, None


def score_pair(ride, candidate):
    """Return a displayable candidate, preserving the original public API."""
    result, _reason = _score_pair(ride, candidate)
    return result


def find_matches(ride, with_diagnostics=False):
    candidates = (
        RideRequest.query.filter_by(status="waiting")
        .filter(RideRequest.ride_id != ride.ride_id)
        .filter(RideRequest.user_id != ride.user_id)
        .all()
    )
    results = []
    counts = {"preference": 0, "distance": 0, "time": 0, "model": 0}
    for candidate in candidates:
        result, reason = _score_pair(ride, candidate)
        if result:
            results.append(result)
        elif reason:
            counts[reason] += 1
    results.sort(key=lambda item: (-item["probability"], item["estimated_detour_km"]))
    if not with_diagnostics:
        return results
    return results, {"candidate_count": len(candidates), "excluded": counts}
