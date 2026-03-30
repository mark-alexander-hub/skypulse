"""Train and serve ML models for flight delay prediction.

Models:
  1. Classification — will the flight be delayed? (Random Forest)
  2. Regression — if delayed, how many minutes? (XGBoost)

Features: COUNTRY, AIRLINE, ORIGIN, Month, Weekday (as int), Hour
Target:   is_delayed (binary), delay_minutes (continuous)
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from xgboost import XGBRegressor

from config import WEEKDAY_ORDER

MODEL_DIR = Path("models")
CLF_PATH = MODEL_DIR / "delay_classifier.pkl"
REG_PATH = MODEL_DIR / "delay_regressor.pkl"
ENCODERS_PATH = MODEL_DIR / "encoders.pkl"

FEATURE_COLS = ["COUNTRY", "AIRLINE", "ORIGIN", "Month", "Hour", "Weekday_num"]


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features needed for training."""
    out = df.copy()
    # Convert weekday name to number (0=Sunday, 6=Saturday)
    weekday_map = {day: i for i, day in enumerate(WEEKDAY_ORDER)}
    out["Weekday_num"] = out["Weekday"].map(weekday_map).fillna(3).astype(int)
    return out


def train_models(data_path: str = "data/unified_flights.csv"):
    """Train both classifier and regressor on the unified dataset."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df = pd.read_csv(data_path, low_memory=False)
    print(f"  {len(df):,} rows loaded.")

    df = _prepare_features(df)

    # --- Encode categorical features ---
    # We need encoders that can transform new data at prediction time
    cat_cols = ["COUNTRY", "AIRLINE", "ORIGIN"]
    encoders = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    # Save encoders
    with open(ENCODERS_PATH, "wb") as f:
        pickle.dump(encoders, f)
    print("  Encoders saved.")

    X = df[FEATURE_COLS]

    # =========================================================================
    # Model 1: Classifier — will the flight be significantly delayed?
    # We define "significant delay" as Sum_Delay_Min >= 30 minutes
    # =========================================================================
    print("\nTraining delay classifier (Random Forest)...")
    df["is_delayed_30"] = (df["Sum_Delay_Min"] >= 30).astype(int)
    y_clf = df["is_delayed_30"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_clf, test_size=0.2, random_state=42, stratify=y_clf
    )

    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=50,
        n_jobs=-1,
        random_state=42,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"  Accuracy: {acc:.3f}")
    print(f"  Baseline (always majority): {1 - y_clf.mean():.3f}")

    with open(CLF_PATH, "wb") as f:
        pickle.dump(clf, f)
    print(f"  Saved → {CLF_PATH}")

    # =========================================================================
    # Model 2: Regressor — predict delay minutes
    # Trained only on delayed flights (Sum_Delay_Min > 0)
    # =========================================================================
    print("\nTraining delay regressor (XGBoost)...")
    y_reg = df["Sum_Delay_Min"]

    X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(
        X, y_reg, test_size=0.2, random_state=42
    )

    reg = XGBRegressor(
        n_estimators=300,
        max_depth=8,
        learning_rate=0.1,
        min_child_weight=50,
        n_jobs=-1,
        random_state=42,
    )
    reg.fit(X_train_r, y_train_r)

    y_pred_r = reg.predict(X_test_r)
    mae = mean_absolute_error(y_test_r, y_pred_r)
    print(f"  MAE: {mae:.1f} minutes")
    print(f"  Baseline (always mean): {(y_reg - y_reg.mean()).abs().mean():.1f} minutes")

    with open(REG_PATH, "wb") as f:
        pickle.dump(reg, f)
    print(f"  Saved → {REG_PATH}")

    # --- Feature importance ---
    print("\nFeature Importance (Classifier):")
    for feat, imp in sorted(
        zip(FEATURE_COLS, clf.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"  {feat:15s} {imp:.3f}")

    print("\nDone! Models saved to models/")


def load_models():
    """Load trained models and encoders. Returns (classifier, regressor, encoders)."""
    with open(CLF_PATH, "rb") as f:
        clf = pickle.load(f)
    with open(REG_PATH, "rb") as f:
        reg = pickle.load(f)
    with open(ENCODERS_PATH, "rb") as f:
        encoders = pickle.load(f)
    return clf, reg, encoders


def predict(
    country: str,
    airline: str,
    origin: str,
    month: int,
    hour: int,
    weekday: str,
) -> dict:
    """Predict delay probability and expected minutes for a single flight.

    Returns dict with keys:
      - delay_probability: float 0-1
      - expected_minutes: float
      - risk_level: str ("Low", "Medium", "High")
    """
    clf, reg, encoders = load_models()

    weekday_map = {day: i for i, day in enumerate(WEEKDAY_ORDER)}
    weekday_num = weekday_map.get(weekday, 3)

    # Encode categoricals — handle unseen labels gracefully
    def safe_encode(encoder, value):
        if value in encoder.classes_:
            return encoder.transform([value])[0]
        # Fallback: use the most common class
        return 0

    row = pd.DataFrame([{
        "COUNTRY": safe_encode(encoders["COUNTRY"], country),
        "AIRLINE": safe_encode(encoders["AIRLINE"], airline),
        "ORIGIN": safe_encode(encoders["ORIGIN"], origin),
        "Month": month,
        "Hour": hour,
        "Weekday_num": weekday_num,
    }])

    # Predict
    delay_prob = clf.predict_proba(row)[0][1]  # probability of class 1 (delayed)
    expected_min = float(reg.predict(row)[0])
    expected_min = max(0, expected_min)  # floor at 0

    # Risk level
    if delay_prob < 0.3:
        risk = "Low"
    elif delay_prob < 0.6:
        risk = "Medium"
    else:
        risk = "High"

    return {
        "delay_probability": round(delay_prob, 3),
        "expected_minutes": round(expected_min, 1),
        "risk_level": risk,
    }


if __name__ == "__main__":
    train_models()
