"""
Trains TF-IDF + LogisticRegression classifier.
Usage: python ml/train_classifier.py
Outputs: ml/models/clf.joblib
"""
import json
import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.pipeline import Pipeline

DATA_PATH = Path("data/labeled.jsonl")
MODEL_DIR = Path("ml/models")
MODEL_PATH = MODEL_DIR / "clf.joblib"


def load_data():
    texts, categories, sales, intents = [], [], [], []
    with DATA_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            categories.append(row["category"])
            sales.append(int(row["is_illegal_sale"]))
            intents.append(row.get("intent", "none"))
    return texts, categories, sales, intents


def build_vectorizer():
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=20000,
        sublinear_tf=True,
    )


def main():
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run: python ml/gen_synthetic.py", file=sys.stderr)
        sys.exit(1)

    print("Loading data...")
    texts, categories, sales, intents = load_data()
    print(f"  Total samples: {len(texts)}")

    X_train, X_test, y_cat_train, y_cat_test, y_sale_train, y_sale_test, y_int_train, y_int_test = (
        train_test_split(texts, categories, sales, intents, test_size=0.2, random_state=42, stratify=categories)
    )

    print("Fitting vectorizer...")
    vec = build_vectorizer()
    X_train_vec = vec.fit_transform(X_train)
    X_test_vec = vec.transform(X_test)

    print("Training category classifier...")
    cat_clf = LogisticRegression(max_iter=1000, C=5.0, random_state=42)
    cat_clf.fit(X_train_vec, y_cat_train)

    print("Training is_illegal_sale classifier...")
    sale_clf = LogisticRegression(max_iter=1000, C=5.0, random_state=42)
    sale_clf.fit(X_train_vec, y_sale_train)

    print("Training intent classifier...")
    intent_clf = LogisticRegression(max_iter=1000, C=5.0, random_state=42)
    intent_clf.fit(X_train_vec, y_int_train)

    # ── Метрики ──────────────────────────────────────────────────────────────
    cat_pred = cat_clf.predict(X_test_vec)
    sale_pred = sale_clf.predict(X_test_vec)

    print("\n=== Category Classification Report ===")
    print(classification_report(y_cat_test, cat_pred))
    cat_acc = accuracy_score(y_cat_test, cat_pred)
    print(f"Category accuracy: {cat_acc:.3f}")

    print("\n=== is_illegal_sale Classification Report ===")
    print(classification_report(y_sale_test, sale_pred))
    sale_acc = accuracy_score(y_sale_test, sale_pred)
    print(f"is_illegal_sale accuracy: {sale_acc:.3f}")

    # ── Сохранение ───────────────────────────────────────────────────────────
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "vectorizer": vec,
        "category_clf": cat_clf,
        "sale_clf": sale_clf,
        "intent_clf": intent_clf,
        "category_labels": list(cat_clf.classes_),
        "metrics": {
            "category_accuracy": cat_acc,
            "sale_accuracy": sale_acc,
            "n_train": len(X_train),
            "n_test": len(X_test),
        },
    }
    joblib.dump(payload, MODEL_PATH)
    print(f"\nModel saved -> {MODEL_PATH}")
    print(f"Summary: category_acc={cat_acc:.3f}, sale_acc={sale_acc:.3f}")


if __name__ == "__main__":
    main()
