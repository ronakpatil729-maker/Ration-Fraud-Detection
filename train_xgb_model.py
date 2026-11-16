# -*- coding: utf-8 -*-
"""Training and retraining script for the XGBoost Ration Card Fraud Model.

Usage:
    python train_xgb_model.py [--dataset <path_to_csv>] [--output <path_to_pkl>]
"""

import os
import sys
import csv
import argparse
from pathlib import Path
import joblib
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score, confusion_matrix

DEFAULT_DATASET = Path(__file__).resolve().parent / "ration_card_fraud_dataset.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "best_xgb_model.pkl"
APP_ML_OUTPUT = Path(__file__).resolve().parent / "app" / "ml" / "best_xgb_model.pkl"

FEATURE_NAMES = [
    "Card_Type",
    "Family_Size",
    "Monthly_Income",
    "Allocated_Wheat_kg",
    "Availed_Wheat_kg",
    "Allocated_Rice_kg",
    "Availed_Rice_kg",
    "Biometric_Failures",
    "Monthly_Transactions",
]

CARD_TYPE_MAP = {
    "AAY": 0,
    "APL": 1,
    "BPL": 2,
}


def load_dataset(csv_path: Path):
    """Load and parse dataset into feature matrix X and target array y."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    X = []
    y = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = []
            for col in FEATURE_NAMES:
                val = row[col]
                if col == "Card_Type":
                    val = CARD_TYPE_MAP.get(str(val).strip().upper(), 1)
                features.append(float(val))
            X.append(features)
            y.append(int(row["Is_Fraud"]))

    return np.array(X), np.array(y)


def train_and_evaluate(dataset_path: Path, output_path: Path):
    """Train XGBoost model, evaluate test split, and save model artifact."""
    print(f"Loading dataset from: {dataset_path}")
    X, y = load_dataset(dataset_path)
    total_records = len(y)
    fraud_records = int(np.sum(y))
    print(f"Dataset loaded: {total_records} records ({fraud_records} fraud, {total_records - fraud_records} legitimate)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Split sizes: Train={len(y_train)}, Test={len(y_test)}")

    # Initialize XGBoost with balanced hyperparameters
    scale_pos_weight = (len(y_train) - np.sum(y_train)) / max(np.sum(y_train), 1)
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=1.0,
        random_state=42,
        eval_metric="logloss"
    )

    print("Fitting XGBoost Classifier...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    print("\n--- Test Set Evaluation Results ---")
    print(f"Accuracy: {acc:.4f}")
    print(f"F1 Score (Fraud Class): {f1:.4f}")
    print(f"Confusion Matrix:\n{cm}")
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred))

    # Save to root and app/ml
    joblib.dump(model, output_path)
    print(f"\nModel exported successfully to: {output_path}")

    try:
        APP_ML_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, APP_ML_OUTPUT)
        print(f"Model synchronized to application directory: {APP_ML_OUTPUT}")
    except Exception as e:
        print(f"Notice: Could not copy to app/ml: {e}")

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train XGBoost Ration Card Fraud Model")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to CSV dataset")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output PKL path")
    args = parser.parse_args()

    train_and_evaluate(args.dataset, args.output)

