# -*- coding: utf-8 -*-
"""Utility for loading the exported XGBoost model.

The model file is stored at ``app/ml/best_xgb_model.pkl`` and was generated
from the synthetic ration‑card dataset described in the project summary.
It expects nine numeric features (the ``Card_ID`` column was excluded during
training).
"""

import joblib
from pathlib import Path
from typing import Any

import os
from pathlib import Path
from typing import Any, Dict

# Candidate paths for the model and dataset
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = Path(__file__).resolve().parents[1]

_CANDIDATE_MODEL_PATHS = [
    _PROJECT_ROOT / "best_xgb_model.pkl",
    _APP_ROOT / "ml" / "best_xgb_model.pkl",
]

_CANDIDATE_DATASET_PATHS = [
    _PROJECT_ROOT / "ration_card_fraud_dataset.csv",
    _APP_ROOT / "ml" / "ration_card_fraud_dataset.csv",
]

# Cached model instance – loaded once per process
_model: Any | None = None


def get_model_path() -> Path:
    """Return the first existing path to the serialized XGBoost model."""
    for path in _CANDIDATE_MODEL_PATHS:
        if path.is_file():
            return path
    return _CANDIDATE_MODEL_PATHS[0]


def get_dataset_path() -> Path:
    """Return the path to the 20,000-record synthetic ration card fraud dataset."""
    for path in _CANDIDATE_DATASET_PATHS:
        if path.is_file():
            return path
    return _CANDIDATE_DATASET_PATHS[0]


def load_xgb_model() -> Any:
    """Load and cache the XGBoost model.

    Returns:
        The deserialized model object (an ``xgboost.XGBClassifier``).
    """
    global _model
    if _model is None:
        model_path = get_model_path()
        if not model_path.is_file():
            raise FileNotFoundError(f"XGBoost model not found at {model_path}")
        _model = joblib.load(model_path)
    return _model


def get_feature_order() -> list[str]:
    """Return the ordered list of feature names expected by the model.

    The training pipeline performed label‑encoding on ``Card_Type`` and then
    used the following columns (in this exact order) as input:

    1. ``Card_Type`` – integer after label‑encoding (e.g. 0=AAY, 1=APL, 2=BPL)
    2. ``Family_Size`` – number of family members
    3. ``Monthly_Income`` – numeric income in currency units
    4. ``Allocated_Wheat_kg``
    5. ``Availed_Wheat_kg``
    6. ``Allocated_Rice_kg``
    7. ``Availed_Rice_kg``
    8. ``Biometric_Failures`` – count of biometric mismatches
    9. ``Monthly_Transactions`` – number of transactions in the month

    If your data schema differs, adjust this list accordingly.
    """
    return [
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

