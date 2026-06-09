import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MODELS = {
    # BGE family — use query prefixes for better accuracy
    "bge-large":  ("BAAI/bge-large-en-v1.5",              True),
    "bge-base":   ("BAAI/bge-base-en-v1.5",               True),
    "bge-small":  ("BAAI/bge-small-en-v1.5",              True),
    "bge-m3":     ("BAAI/bge-m3",                         True),
    # sentence-transformers — no prefix needed
    "minilm":     ("sentence-transformers/all-MiniLM-L6-v2",   False),
    "mpnet":      ("sentence-transformers/all-mpnet-base-v2",   False),
    "mxbai":      ("mixedbread-ai/mxbai-embed-large-v1",        False),
}

DEFAULT_MODEL = "bge-large"

_loaded: dict = {}  # cache loaded models by key


def _get_model(key: str) -> tuple:
    if key not in MODELS:
        raise ValueError(
            f"Unknown semantic model '{key}'. Valid options: {list(MODELS)}"
        )
    if key not in _loaded:
        model_id, use_prefix = MODELS[key]
        _loaded[key] = (SentenceTransformer(model_id), use_prefix)
    return _loaded[key]


def semantic_score(job_posting: str, resume: str, model_key: str = DEFAULT_MODEL) -> float:
    model, use_prefix = _get_model(model_key)
    if use_prefix:
        inputs = [
            f"Represent this job posting: {job_posting}",
            f"Represent this resume: {resume}",
        ]
    else:
        inputs = [job_posting, resume]
    embeddings = model.encode(inputs)
    return float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])


def run(df: pd.DataFrame, resume_text: str, config: dict) -> pd.DataFrame:
    model_key = config.get("model", DEFAULT_MODEL)
    df["semantic_score"] = df["description"].apply(
        lambda desc: semantic_score(str(desc), resume_text, model_key)
        if desc and not pd.isna(desc)
        else 0.0
    )
    return df
