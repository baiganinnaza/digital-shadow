"""
Evaluates the trained classifier on holdout data.
Usage: python ml/eval.py
"""
import json
import sys
from pathlib import Path

import joblib
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support

MODEL_PATH = Path("ml/models/clf.joblib")
DATA_PATH = Path("data/labeled.jsonl")


def main():
    if not MODEL_PATH.exists():
        print(f"ERROR: Model not found at {MODEL_PATH}. Run: python ml/train_classifier.py", file=sys.stderr)
        sys.exit(1)

    data = joblib.load(MODEL_PATH)
    vec = data["vectorizer"]
    cat_clf = data["category_clf"]
    sale_clf = data["sale_clf"]

    texts, categories, sales = [], [], []
    with DATA_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            categories.append(row["category"])
            sales.append(int(row["is_illegal_sale"]))

    # Use last 20% as holdout (same split as training)
    n = len(texts)
    split = int(n * 0.8)
    X_test = texts[split:]
    y_cat = categories[split:]
    y_sale = sales[split:]

    X_vec = vec.transform(X_test)
    cat_pred = cat_clf.predict(X_vec)
    sale_pred = sale_clf.predict(X_vec)

    print(f"Holdout size: {len(X_test)} samples\n")

    print("=== Category — Precision / Recall / F1 ===")
    print(classification_report(y_cat, cat_pred))

    print("=== is_illegal_sale — Precision / Recall / F1 ===")
    print(classification_report(y_sale, sale_pred, target_names=["legal", "illegal"]))

    print("=== Confusion Matrix (category) ===")
    labels = sorted(set(y_cat))
    cm = confusion_matrix(y_cat, cat_pred, labels=labels)
    header = f"{'':12s}" + "  ".join(f"{l:10s}" for l in labels)
    print(header)
    for i, row in enumerate(cm):
        print(f"{labels[i]:12s}" + "  ".join(f"{v:10d}" for v in row))

    cat_acc = accuracy_score(y_cat, cat_pred)
    sale_acc = accuracy_score(y_sale, sale_pred)
    p, r, f, _ = precision_recall_fscore_support(y_cat, cat_pred, average="macro")
    print(f"\nSummary:")
    print(f"  category_accuracy : {cat_acc:.3f}")
    print(f"  category_precision: {p:.3f}")
    print(f"  category_recall   : {r:.3f}")
    print(f"  category_f1       : {f:.3f}")
    print(f"  sale_accuracy     : {sale_acc:.3f}")


if __name__ == "__main__":
    main()
