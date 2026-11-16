"""
Isolation Forest Anomaly Detection Model for Public Distribution Transactions.
Implements the Liu, Ting, and Zhou (2008) Isolation Forest algorithm in pure Python
to guarantee cross-platform execution without native binary/DLL dependency issues.
Features robust missing value imputation, insufficient training data safeguards,
and human-understandable reason generation for flagged outliers.
"""
import math
import random
import os
import pickle
from typing import List, Dict, Any, Tuple, Optional

FEATURE_NAMES = [
    'quantity',
    'quota_ratio',
    'hour_of_day',
    'biometric_score',
    'is_manual'
]

# Baseline feature statistics used for missing value imputation and explanation
FEATURE_DEFAULTS = {
    'quantity': 20.0,
    'quota_ratio': 1.0,
    'hour_of_day': 12.0,
    'biometric_score': 0.85,
    'is_manual': 0.0
}


def _c_factor(n: int) -> float:
    """Average path length of unsuccessful search in a binary search tree."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    euler_gamma = 0.5772156649
    return 2.0 * (math.log(n - 1) + euler_gamma) - (2.0 * (n - 1) / n)


class IsolationTreeNode:
    def __init__(self, size: int):
        self.size = size
        self.is_leaf = True
        self.feature_idx = None
        self.split_val = None
        self.left = None
        self.right = None


class IsolationTree:
    def __init__(self, max_height: int):
        self.max_height = max_height
        self.root = None

    def fit(self, X: List[List[float]], current_height: int = 0) -> IsolationTreeNode:
        n_samples = len(X)
        if n_samples <= 1 or current_height >= self.max_height:
            return IsolationTreeNode(size=n_samples)

        n_features = len(X[0])
        # Find features that have varying values
        valid_features = []
        feature_min_max = {}
        for f_idx in range(n_features):
            vals = [row[f_idx] for row in X]
            min_v, max_v = min(vals), max(vals)
            if min_v < max_v:
                valid_features.append(f_idx)
                feature_min_max[f_idx] = (min_v, max_v)

        if not valid_features:
            return IsolationTreeNode(size=n_samples)

        # Select random feature and random split point
        f_idx = random.choice(valid_features)
        min_v, max_v = feature_min_max[f_idx]
        split_val = random.uniform(min_v, max_v)

        left_X = [row for row in X if row[f_idx] < split_val]
        right_X = [row for row in X if row[f_idx] >= split_val]

        node = IsolationTreeNode(size=n_samples)
        node.is_leaf = False
        node.feature_idx = f_idx
        node.split_val = split_val
        node.left = self.fit(left_X, current_height + 1)
        node.right = self.fit(right_X, current_height + 1)
        return node

    def path_length(self, x: List[float], node: IsolationTreeNode, current_depth: int = 0) -> float:
        if node.is_leaf:
            return current_depth + _c_factor(node.size)
        if x[node.feature_idx] < node.split_val:
            return self.path_length(x, node.left, current_depth + 1)
        else:
            return self.path_length(x, node.right, current_depth + 1)


class PDSIsolationForest:
    """
    Isolation Forest for PDS transactions.
    Detects statistical outliers across multi-dimensional numerical features.
    """
    def __init__(self, n_estimators: int = 100, max_samples: int = 256,
                 contamination: float = 0.08, random_state: int = 42):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.random_state = random_state
        self.trees: List[IsolationTree] = []
        self.subsample_size = 0
        self.is_fitted = False
        self.min_training_samples = 15

    def _impute_features(self, x: List[Any]) -> List[float]:
        """Impute missing (None or NaN) numerical values using domain defaults."""
        cleaned = []
        for i, val in enumerate(x):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                col_name = FEATURE_NAMES[i] if i < len(FEATURE_NAMES) else 'quantity'
                cleaned.append(FEATURE_DEFAULTS.get(col_name, 0.0))
            else:
                cleaned.append(float(val))
        return cleaned

    def fit(self, X: List[List[Any]]) -> 'PDSIsolationForest':
        """
        Train the Isolation Forest on transaction feature matrix X.
        Handles missing values and protects against insufficient training data.
        """
        if self.random_state is not None:
            random.seed(self.random_state)

        # Clean and impute missing values
        cleaned_X = [self._impute_features(row) for row in X]
        n_samples = len(cleaned_X)

        if n_samples < self.min_training_samples:
            # Insufficient training data safeguard:
            # Augment with baseline synthetic reference distribution to allow safe inference
            synthetic_baseline = self._generate_synthetic_baseline(50)
            cleaned_X.extend(synthetic_baseline)
            n_samples = len(cleaned_X)

        self.subsample_size = min(self.max_samples, n_samples)
        max_height = math.ceil(math.log2(max(self.subsample_size, 2)))

        self.trees = []
        for _ in range(self.n_estimators):
            subsample = random.sample(cleaned_X, self.subsample_size)
            tree = IsolationTree(max_height=max_height)
            tree.root = tree.fit(subsample)
            self.trees.append(tree)

        self.is_fitted = True
        return self

    def score_sample(self, x: List[Any]) -> float:
        """
        Compute anomaly score for single sample.
        Returns a score in range [0, 1].
        Scores > 0.60 typically indicate anomalous behavior.
        """
        if not self.is_fitted:
            # Auto-fit with synthetic baseline if called before explicit fit
            self.fit([])

        cleaned_x = self._impute_features(x)
        c = _c_factor(self.subsample_size)
        if c == 0.0:
            return 0.5

        total_path_length = sum(
            tree.path_length(cleaned_x, tree.root) for tree in self.trees
        )
        avg_path_length = total_path_length / len(self.trees)
        anomaly_score = 2.0 ** (-avg_path_length / c)
        return float(anomaly_score)

    def predict(self, x: List[Any], threshold: float = 0.60) -> Tuple[int, float, Dict[str, Any]]:
        """
        Classify transaction as anomaly (-1) or normal (1).
        Returns:
            (prediction: -1 or 1, anomaly_score: float, explanation_dict: dict)
        """
        cleaned_x = self._impute_features(x)
        score = self.score_sample(cleaned_x)
        is_anomaly = score >= threshold
        pred = -1 if is_anomaly else 1

        explanation = self._explain_sample(cleaned_x, score, is_anomaly)
        return pred, score, explanation

    def _explain_sample(self, x: List[float], score: float, is_anomaly: bool) -> Dict[str, Any]:
        """
        Generates plain-language, non-accusatory reasons for the statistical anomaly score.
        Explicitly notes that statistical outliers do not constitute proof of fraud.
        """
        qty = x[0]
        ratio = x[1]
        hour = int(x[2]) % 24
        bio_score = x[3]
        is_manual = bool(x[4] > 0.5)

        triggers = []
        if ratio > 1.5:
            triggers.append(f"Quantity ({qty:.1f}kg) is {ratio:.1f}x higher than the monthly card entitlement")
        if hour < 7 or hour > 20:
            triggers.append(f"Transaction occurred outside standard operating hours ({hour:02d}:00)")
        if is_manual:
            triggers.append("Transaction used manual biometric override")
        if bio_score < 0.40:
            triggers.append(f"Sub-optimal biometric match score ({bio_score:.2f})")

        if is_anomaly:
            if triggers:
                details = "; ".join(triggers)
                reason = f"Statistical Anomaly (Isolation Forest Score: {score:.2f}): {details}."
            else:
                reason = f"Statistical Outlier (Isolation Forest Score: {score:.2f}): Rare combination of transaction dimensions."
            
            disclaimer = (
                "NOTE: This outlier was flagged by statistical anomaly detection. "
                "Outliers reflect statistical rarity and require administrative verification; "
                "they do not constitute conclusive proof of fraud."
            )
            severity = 'HIGH' if score >= 0.72 else 'MEDIUM'
        else:
            reason = f"Transaction within expected distribution patterns (Isolation Forest Score: {score:.2f})."
            disclaimer = ""
            severity = 'LOW'

        return {
            'is_anomaly': is_anomaly,
            'score': round(score, 3),
            'severity': severity,
            'reason': reason,
            'disclaimer': disclaimer,
            'features': {
                'quantity': qty,
                'quota_ratio': ratio,
                'hour_of_day': hour,
                'biometric_score': bio_score,
                'is_manual': is_manual
            }
        }

    def _generate_synthetic_baseline(self, n_samples: int = 100) -> List[List[float]]:
        """Generate realistic baseline distribution for training & fallback."""
        samples = []
        for _ in range(n_samples):
            # Normal transactions: modest quota ratio (0.5 - 1.0), daytime hours (8 - 18), high biometric score
            qty = random.uniform(5.0, 35.0)
            ratio = random.uniform(0.3, 1.0)
            hour = random.uniform(8.0, 18.0)
            bio = random.uniform(0.80, 0.99)
            is_manual = 1.0 if random.random() < 0.05 else 0.0
            samples.append([qty, ratio, hour, bio, is_manual])

        # Add a few outliers (5%)
        n_outliers = max(2, int(n_samples * 0.05))
        for _ in range(n_outliers):
            qty = random.uniform(70.0, 300.0)
            ratio = random.uniform(2.5, 8.0)
            hour = random.choice([1.0, 2.0, 3.0, 23.0])
            bio = random.uniform(0.10, 0.35)
            is_manual = 1.0
            samples.append([qty, ratio, hour, bio, is_manual])

        return samples

    def save(self, filepath: str) -> None:
        """Persist model to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str) -> 'PDSIsolationForest':
        """Load persisted model from disk."""
        with open(filepath, 'rb') as f:
            return pickle.load(f)


_global_model: Optional[PDSIsolationForest] = None


def get_isolation_forest_model(model_path: Optional[str] = None) -> PDSIsolationForest:
    """Singleton getter for the Isolation Forest model; auto-trains and persists if missing."""
    global _global_model
    if _global_model is not None:
        return _global_model

    if model_path is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        model_path = os.path.join(base_dir, 'instance', 'models', 'isolation_forest.pkl')

    if os.path.exists(model_path):
        try:
            _global_model = PDSIsolationForest.load(model_path)
            return _global_model
        except Exception:
            # If load fails due to corrupt file, re-fit
            pass

    # Fit new model on baseline synthetic distribution
    model = PDSIsolationForest(n_estimators=100, contamination=0.08, random_state=42)
    model.fit([])  # will auto-generate synthetic baseline
    try:
        model.save(model_path)
    except Exception:
        pass
    _global_model = model
    return _global_model

