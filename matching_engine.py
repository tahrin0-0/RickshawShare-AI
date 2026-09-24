"""Candidate filtering and inference using the existing saved pipelines."""
from pathlib import Path
import joblib
import pandas as pd
from feature_engineering import build_pair_features
from models import RideRequest

ROOT=Path(__file__).resolve().parent
MODEL_DIR=ROOT/"models" if (ROOT/"models").is_dir() else ROOT
CLASS_FEATURES=["pickup_distance_km","time_difference_min","route_overlap_percent","detour_km","destination_compatibility","preference_compatible"]
REG_FEATURES=["pickup_distance_km","time_difference_min","route_overlap_percent","destination_compatibility","preference_compatible"]
_classifier=_regressor=None

def load_models():
    global _classifier,_regressor
    if _classifier is None:
        _classifier=joblib.load(MODEL_DIR/"best_rickshaw_classification_model.pkl")
        _regressor=joblib.load(MODEL_DIR/"best_rickshaw_regression_model.pkl")
        for pipeline in (_classifier,_regressor):
            for _,estimator in getattr(pipeline,"steps",[]):
                if hasattr(estimator,"n_jobs"): estimator.n_jobs=1
    return _classifier,_regressor

def score_pair(ride,candidate):
    f=build_pair_features(ride,candidate)
    if not f["preference_compatible"] or f["pickup_distance_km"]>5 or f["time_difference_min"]>30: return None
    classifier,regressor=load_models()
    detour=max(0.,float(regressor.predict(pd.DataFrame([f],columns=REG_FEATURES))[0]))
    class_data={**f,"detour_km":detour}; frame=pd.DataFrame([class_data],columns=CLASS_FEATURES)
    prediction=int(classifier.predict(frame)[0]); probability=float(classifier.predict_proba(frame)[0,list(classifier.classes_).index(1)])
    if prediction != 1: return None
    stored={k:f[k] for k in ("pickup_distance_km","time_difference_min","route_overlap_percent","destination_compatibility")}
    stored["estimated_detour_km"]=detour
    return {"ride":candidate,"probability":probability,"features":f,"estimated_detour_km":detour,"stored_features":stored}

def find_matches(ride):
    candidates=RideRequest.query.filter_by(status="waiting").filter(RideRequest.ride_id!=ride.ride_id,RideRequest.user_id!=ride.user_id).all()
    results=[result for c in candidates if (result:=score_pair(ride,c))]
    return sorted(results,key=lambda x:(-x["probability"],x["estimated_detour_km"]))
