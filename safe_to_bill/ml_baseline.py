"""Pipeline B: TF-IDF + logistic regression predicting the MDM level straight from the note text.

Trained on generated notes only. Its confidence gate is a probability threshold tuned on the
generated dev split: the lowest threshold with zero wrong auto-bills there.

    python -m safe_to_bill.ml_baseline        # trains and writes models/ml_baseline.joblib
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .mdm import CODES, LEVEL_NAMES

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "ml_baseline.joblib"
NAME_TO_LEVEL = {v: k for k, v in LEVEL_NAMES.items()}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class MLBaseline:
    def __init__(self, pipeline, threshold: float = 0.9):
        self.pipeline = pipeline
        self.threshold = threshold

    @classmethod
    def train(cls, rows: list[dict]) -> "MLBaseline":
        pipe = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True),
            LogisticRegression(max_iter=3000, C=4.0),
        )
        pipe.fit([r["note"] for r in rows], [NAME_TO_LEVEL[r["label"]["level"]] for r in rows])
        return cls(pipe)

    def predict(self, note: str) -> tuple[int, float]:
        proba = self.pipeline.predict_proba([note])[0]
        i = int(np.argmax(proba))
        return int(self.pipeline.classes_[i]), float(proba[i])

    def tune_threshold(self, rows: list[dict]) -> dict:
        preds = [self.predict(r["note"]) for r in rows]
        best = None
        for t in np.arange(0.40, 1.0, 0.01):
            wrong = auto = 0
            for r, (lvl, p) in zip(rows, preds):
                if p >= t and CODES[r["patient_type"]][lvl] == r["billed_code"]:
                    auto += 1
                    wrong += r["billed_code"] != r["label"]["code"]
            if wrong == 0:
                best = {"threshold": round(float(t), 2), "auto_bills": auto}
                break
        self.threshold = best["threshold"] if best else 0.99
        return best or {"threshold": 0.99, "auto_bills": 0}

    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "threshold": self.threshold}, path)

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "MLBaseline":
        obj = joblib.load(path)
        return cls(obj["pipeline"], obj["threshold"])


def main() -> None:
    gen = ROOT / "data" / "generated"
    model = MLBaseline.train(load_jsonl(gen / "train.jsonl"))
    info = model.tune_threshold(load_jsonl(gen / "dev.jsonl"))
    model.save()
    print(f"trained on generated/train.jsonl; threshold tuned on generated/dev.jsonl: {info}")


if __name__ == "__main__":
    main()
