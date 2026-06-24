import joblib
from pathlib import Path
from app.config import settings


class Classifier:
    _instance = None

    def __init__(self):
        model_path = Path(settings.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Run: python ml/train_classifier.py"
            )
        data = joblib.load(model_path)
        self._vec = data["vectorizer"]
        self._cat_clf = data["category_clf"]
        self._sale_clf = data["sale_clf"]
        self._intent_clf = data["intent_clf"]
        self._cat_labels = data["category_labels"]

    @classmethod
    def get(cls) -> "Classifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def classify(self, text: str) -> dict:
        X = self._vec.transform([text])
        category = self._cat_clf.predict(X)[0]
        is_illegal_sale = bool(self._sale_clf.predict(X)[0])
        intent = self._intent_clf.predict(X)[0]
        cat_proba = self._cat_clf.predict_proba(X)[0]
        confidence = float(max(cat_proba))
        return {
            "category": category,
            "is_illegal_sale": is_illegal_sale,
            "intent": intent,
            "confidence": confidence,
        }
