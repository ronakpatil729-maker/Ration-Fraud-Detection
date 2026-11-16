# -*- coding: utf-8 -*-
"""XGBoost prediction wrapper for the ration‑card fraud model.

The model was trained on synthetic data (see project summary) and expects the
nine numeric features returned by ``get_feature_order`` in
``app.fraud.model_loader``.  This module provides a thin convenience
function that validates input, builds the feature vector in the correct order,
and returns the class probability (fraud score) and predicted label.
"""

from typing import Dict, Any
import numpy as np

from .model_loader import load_xgb_model, get_feature_order


def predict_fraud(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Predict fraud probability for a single record.

    Parameters
    ----------
    payload: dict
        Mapping of feature names to numeric values.  Missing features raise a
        ``KeyError`` with a clear message.  Extra keys are ignored.

    Returns
    -------
    dict
        ``{"probability": float, "prediction": int}``
        * ``probability`` – model's predicted probability for the positive
          (fraud) class.
        * ``prediction`` – binary label (1 = fraud, 0 = legitimate).
    """
    # Map card type strings to label encoded integers if string provided
    CARD_TYPE_MAP = {
        'AAY': 0,
        'APL': 1,
        'BPL': 2,
    }

    # Ensure required features are present and in the correct order
    ordered_features = []
    for name in get_feature_order():
        if name not in payload:
            raise KeyError(f"Missing required feature '{name}' in payload")
        val = payload[name]
        if name == "Card_Type" and isinstance(val, str):
            val_upper = val.strip().upper()
            if val_upper in CARD_TYPE_MAP:
                val = CARD_TYPE_MAP[val_upper]
        ordered_features.append(float(val))

    # Convert to 2‑D array expected by scikit‑learn / xgboost predict methods
    X = np.asarray([ordered_features])

    model = load_xgb_model()
    # ``predict_proba`` returns [[prob_neg, prob_pos]]
    prob = float(model.predict_proba(X)[0][1])
    pred = int(model.predict(X)[0])
    return {"probability": prob, "prediction": pred}

