"""Train and evaluate the Rickshaw Share classification and regression models."""

from pathlib import Path
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, mean_absolute_error, mean_squared_error,
                             precision_score, r2_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

ROOT = Path(__file__).resolve().parent
DATA_PATH = next((path for path in (
    ROOT / "rickshaw_matching_dataset.csv",
    ROOT / "data" / "rickshaw_matching_dataset.csv",
) if path.is_file()), ROOT / "rickshaw_matching_dataset.csv")
MODEL_DIR = ROOT / "models" if (ROOT / "models").is_dir() else ROOT
MODEL_DIR.mkdir(exist_ok=True)
CLASSIFICATION_MODEL_PATH = MODEL_DIR / "best_rickshaw_classification_model.pkl"
REGRESSION_MODEL_PATH = MODEL_DIR / "best_rickshaw_regression_model.pkl"

CLASSIFICATION_FEATURES = ["pickup_distance_km", "time_difference_min", "route_overlap_percent",
                           "detour_km", "destination_compatibility", "preference_compatible"]
REGRESSION_FEATURES = ["pickup_distance_km", "time_difference_min", "route_overlap_percent",
                       "destination_compatibility", "preference_compatible"]
TARGET_CLASSIFICATION = "match"
TARGET_REGRESSION = "detour_km"


def make_pipeline(model, scale=True):
    """Put scaling inside a pipeline so it is fitted only on training data."""
    return Pipeline([("scaler", StandardScaler()), ("model", model)]) if scale else Pipeline([("model", model)])


def inspect_data(df):
    print("\n=== DATA INSPECTION ===")
    print("First 5 rows:\n", df.head())
    print("\nShape:", df.shape)
    print("\nColumns:", list(df.columns))
    print("\nData types:\n", df.dtypes)
    print("\nDataset information:")
    df.info()
    print("\nDescriptive statistics:\n", df.describe())
    print("\nMissing values:\n", df.isna().sum())
    print("\nDuplicate rows:", df.duplicated().sum())
    print("\nTarget class distribution:\n", df[TARGET_CLASSIFICATION].value_counts().sort_index())


def exploratory_analysis(df):
    """Create simple EDA plots and print the correlation matrix."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    plots = [(TARGET_CLASSIFICATION, "Match Class Distribution", "bar"),
             ("route_overlap_percent", "Route Overlap Distribution", "hist"),
             ("pickup_distance_km", "Pickup Distance Distribution", "hist"),
             ("time_difference_min", "Time Difference Distribution", "hist"),
             ("detour_km", "Detour Distribution", "hist")]
    for ax, (column, title, kind) in zip(axes.flat, plots):
        if kind == "bar":
            df[column].value_counts().sort_index().plot(kind="bar", ax=ax, color=["#e76f51", "#2a9d8f"])
            ax.set_xlabel("Match (0 = No, 1 = Yes)")
        else:
            df[column].plot(kind="hist", bins=20, ax=ax, color="#457b9d", edgecolor="white")
            ax.set_xlabel(column)
        ax.set_title(title)
        ax.set_ylabel("Count")
    axes.flat[-1].axis("off")
    fig.tight_layout()
    plt.show()
    print("\nCorrelation matrix:\n", df.corr(numeric_only=True).round(3))


def train_classification(df):
    X, y = df[CLASSIFICATION_FEATURES], df[TARGET_CLASSIFICATION]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    models = {
        "Logistic Regression": make_pipeline(LogisticRegression(max_iter=1000)),
        "KNN": make_pipeline(KNeighborsClassifier(n_neighbors=5)),
        "Decision Tree": make_pipeline(DecisionTreeClassifier(random_state=42, max_depth=6), scale=False),
        "Random Forest": make_pipeline(RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1), scale=False),
    }
    rows = []
    for name, model in models.items():
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None
        rows.append({"Model": name, "Accuracy": accuracy_score(y_test, predictions),
                     "Precision": precision_score(y_test, predictions, zero_division=0),
                     "Recall": recall_score(y_test, predictions, zero_division=0),
                     "F1 Score": f1_score(y_test, predictions, zero_division=0),
                     "ROC AUC": roc_auc_score(y_test, probabilities) if probabilities is not None else np.nan})
        print(f"\n=== {name} ===\nConfusion Matrix:\n{confusion_matrix(y_test, predictions)}")
        print(classification_report(y_test, predictions, zero_division=0))
    comparison = pd.DataFrame(rows).sort_values(["F1 Score", "ROC AUC"], ascending=False).reset_index(drop=True)
    print("\nClassification comparison:\n", comparison.round(4).to_string(index=False))
    best_name = comparison.iloc[0]["Model"]
    best_model = models[best_name]
    joblib.dump(best_model, CLASSIFICATION_MODEL_PATH)
    print(f"\nBest classification model: {best_name} (saved to {CLASSIFICATION_MODEL_PATH.name})")
    return best_model, best_name, comparison


def train_regression(df):
    X, y = df[REGRESSION_FEATURES], df[TARGET_REGRESSION]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
    models = {
        "Linear Regression": make_pipeline(LinearRegression()),
        "KNN Regressor": make_pipeline(KNeighborsRegressor(n_neighbors=5)),
        "Decision Tree Regressor": make_pipeline(DecisionTreeRegressor(random_state=42, max_depth=8), scale=False),
        "Random Forest Regressor": make_pipeline(RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1), scale=False),
    }
    rows, predictions_by_model = [], {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        predictions_by_model[name] = predictions
        mse = mean_squared_error(y_test, predictions)
        rows.append({"Model": name, "MAE": mean_absolute_error(y_test, predictions), "MSE": mse,
                     "RMSE": np.sqrt(mse), "R2": r2_score(y_test, predictions)})
    comparison = pd.DataFrame(rows).sort_values(["RMSE", "MAE", "R2"], ascending=[True, True, False]).reset_index(drop=True)
    print("\nRegression comparison:\n", comparison.round(4).to_string(index=False))
    best_name = comparison.iloc[0]["Model"]
    best_model = models[best_name]
    joblib.dump(best_model, REGRESSION_MODEL_PATH)
    print(f"\nBest regression model: {best_name} (saved to {REGRESSION_MODEL_PATH.name})")
    best_predictions = predictions_by_model[best_name]
    plt.figure(figsize=(7, 5))
    plt.scatter(y_test, best_predictions, alpha=0.55, color="#2a9d8f")
    line_min, line_max = min(y_test.min(), best_predictions.min()), max(y_test.max(), best_predictions.max())
    plt.plot([line_min, line_max], [line_min, line_max], "--", color="#e76f51", label="Perfect prediction")
    plt.xlabel("Actual Detour (km)"); plt.ylabel("Predicted Detour (km)")
    plt.title(f"Actual vs Predicted Detour — {best_name}"); plt.legend(); plt.tight_layout(); plt.show()
    return best_model, best_name, comparison


def prediction_demo(classification_model, regression_model):
    sample = pd.DataFrame([{**{"pickup_distance_km": 0.8, "time_difference_min": 5,
                             "route_overlap_percent": 82, "detour_km": 0.7,
                             "destination_compatibility": 0.90, "preference_compatible": 1}}])
    match = classification_model.predict(sample[CLASSIFICATION_FEATURES])[0]
    probability = classification_model.predict_proba(sample[CLASSIFICATION_FEATURES])[0, 1]
    detour = regression_model.predict(sample[REGRESSION_FEATURES])[0]
    print("\n=== PREDICTION DEMO ===")
    print("Prediction:", "Suitable Match" if match == 1 else "Not Suitable Match")
    print(f"Match Probability: {probability:.2%}")
    print(f"Estimated Detour: {detour:.2f} km")
    print("\nThe classification model checks compatibility first. For a suitable pair, the regression model estimates the additional detour.")


def main():
    print(f"Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    expected = set(CLASSIFICATION_FEATURES + [TARGET_CLASSIFICATION])
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
    inspect_data(df)
    exploratory_analysis(df)
    classification_model, _, _ = train_classification(df)
    regression_model, _, _ = train_regression(df)
    prediction_demo(classification_model, regression_model)


if __name__ == "__main__":
    main()
