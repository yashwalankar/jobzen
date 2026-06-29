import numpy as np
import pandas as pd
from sentence_transformers import CrossEncoder

MODELS = {
    "bge-reranker-v2-m3":  "BAAI/bge-reranker-v2-m3",
    "bge-reranker-large":  "BAAI/bge-reranker-large",
    "ms-marco-l12":        "cross-encoder/ms-marco-MiniLM-L-12-v2",
    "ms-marco-l6":         "cross-encoder/ms-marco-MiniLM-L-6-v2",
}

DEFAULT_MODEL = "bge-reranker-v2-m3"

_loaded: dict = {}


def _get_model(key: str) -> CrossEncoder:
    if key not in MODELS:
        raise ValueError(f"Unknown cross-encoder model '{key}'. Valid: {list(MODELS)}")
    if key not in _loaded:
        _loaded[key] = CrossEncoder(MODELS[key])
    return _loaded[key]


def run(df: pd.DataFrame, resume_text: str, config: dict) -> pd.DataFrame:
    model_key = config.get("model", DEFAULT_MODEL)
    model = _get_model(model_key)

    pairs = [
        (str(desc)[:2000], resume_text[:2000])
        if desc and not pd.isna(desc)
        else ("", resume_text[:2000])
        for desc in df["description"]
    ]

    raw_scores = model.predict(pairs)
    # raw logits → [0, 1] via sigmoid
    df["cross_encoder_score"] = (1 / (1 + np.exp(-raw_scores))).tolist()
    return df
