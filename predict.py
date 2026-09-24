"""Load the saved Rickshaw Share models and make one passenger-pair prediction."""
from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models" if (ROOT / "models").is_dir() else ROOT
classification_model = joblib.load(MODEL_DIR / "best_rickshaw_classification_model.pkl")
regression_model = joblib.load(MODEL_DIR / "best_rickshaw_regression_model.pkl")

pair = pd.DataFrame([{
    "pickup_distance_km": 0.8, "time_difference_min": 5, "route_overlap_percent": 82,
    "detour_km": 0.7, "destination_compatibility": 0.90, "preference_compatible": 1,
}])
classification_features = ["pickup_distance_km", "time_difference_min", "route_overlap_percent", "detour_km", "destination_compatibility", "preference_compatible"]
regression_features = ["pickup_distance_km", "time_difference_min", "route_overlap_percent", "destination_compatibility", "preference_compatible"]
prediction_input = pair[classification_features]
# Saved forests may request multiple worker processes; limit parallelism for a
# one-row interactive prediction and avoid unnecessary process startup.
for model in (classification_model, regression_model):
    for _, estimator in getattr(model, "steps", []):
        if hasattr(estimator, "n_jobs"):
            estimator.n_jobs = 1
prediction = classification_model.predict(prediction_input)[0]
probability = classification_model.predict_proba(prediction_input)[0, 1]
estimated_detour = regression_model.predict(pair[regression_features])[0]
print("Prediction:", "Suitable Match" if prediction == 1 else "Not Suitable Match")
print(f"Match Probability: {probability:.2%}")
print(f"Estimated Detour: {estimated_detour:.2f} km")
