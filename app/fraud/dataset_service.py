# -*- coding: utf-8 -*-
"""Dataset management and evaluation service for Ration Card Fraud Detection.

Connects the 20,000-record synthetic dataset (``ration_card_fraud_dataset.csv``)
with the application services and XGBoost model.
"""

import csv
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

from .model_loader import get_dataset_path, load_xgb_model, get_feature_order


class DatasetService:
    """Provides structured access, analytics, and verification for the dataset."""

    _summary_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def get_dataset_summary(cls) -> Dict[str, Any]:
        """Return dataset metadata, row counts, and fraud distribution."""
        if cls._summary_cache is not None:
            return cls._summary_cache

        csv_path = get_dataset_path()
        if not csv_path.is_file():
            return {
                "exists": False,
                "path": str(csv_path),
                "total_records": 0,
                "fraud_count": 0,
                "legitimate_count": 0,
            }

        total_records = 0
        fraud_count = 0
        card_types = {"AAY": 0, "APL": 0, "BPL": 0}

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            for row in reader:
                total_records += 1
                if row.get("Is_Fraud") == "1":
                    fraud_count += 1
                c_type = row.get("Card_Type", "").upper()
                if c_type in card_types:
                    card_types[c_type] += 1

        legitimate_count = total_records - fraud_count
        fraud_percent = round((fraud_count / total_records * 100), 2) if total_records else 0.0

        cls._summary_cache = {
            "exists": True,
            "path": str(csv_path),
            "total_records": total_records,
            "fraud_count": fraud_count,
            "legitimate_count": legitimate_count,
            "fraud_percentage": fraud_percent,
            "card_types": card_types,
            "columns": columns,
        }
        return cls._summary_cache

    @classmethod
    def get_sample_records(cls, limit: int = 5, is_fraud: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch sample records from the dataset for demonstration or testing."""
        csv_path = get_dataset_path()
        if not csv_path.is_file():
            return []

        samples = []
        target_str = str(is_fraud) if is_fraud is not None else None

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if target_str is not None and row.get("Is_Fraud") != target_str:
                    continue
                samples.append(row)
                if len(samples) >= limit:
                    break

        return samples

    @classmethod
    def find_by_card_id(cls, card_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single record in the dataset by Card_ID."""
        csv_path = get_dataset_path()
        if not csv_path.is_file():
            return None

        clean_id = card_id.strip().upper()
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Card_ID", "").strip().upper() == clean_id:
                    return row
        return None

    @classmethod
    def evaluate_model(cls) -> Dict[str, Any]:
        """Compute performance metrics of the cached XGBoost model against the dataset."""
        csv_path = get_dataset_path()
        if not csv_path.is_file():
            return {"error": "Dataset file not found"}

        model = load_xgb_model()
        features = get_feature_order()
        card_map = {"AAY": 0, "APL": 1, "BPL": 2}

        X = []
        y_true = []

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vec = []
                for col in features:
                    val = row[col]
                    if col == "Card_Type":
                        val = card_map.get(str(val).upper(), 1)
                    vec.append(float(val))
                X.append(vec)
                y_true.append(int(row["Is_Fraud"]))

        X_arr = np.array(X)
        y_true_arr = np.array(y_true)
        y_pred_arr = model.predict(X_arr)

        # Basic metrics calculation without strict external dependencies
        total = len(y_true_arr)
        tp = int(np.sum((y_true_arr == 1) & (y_pred_arr == 1)))
        tn = int(np.sum((y_true_arr == 0) & (y_pred_arr == 0)))
        fp = int(np.sum((y_true_arr == 0) & (y_pred_arr == 1)))
        fn = int(np.sum((y_true_arr == 1) & (y_pred_arr == 0)))

        accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        return {
            "total_records": total,
            "accuracy": accuracy,
            "precision_fraud": precision,
            "recall_fraud": recall,
            "f1_fraud": f1,
            "confusion_matrix": {
                "true_negative": tn,
                "false_positive": fp,
                "false_negative": fn,
                "true_positive": tp,
            },
        }

