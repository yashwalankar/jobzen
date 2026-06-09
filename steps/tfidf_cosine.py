import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def run(df: pd.DataFrame, resume_text: str, config: dict) -> pd.DataFrame:
    descriptions = df["description"].fillna("").astype(str).tolist()
    corpus = [resume_text] + descriptions

    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    resume_vec = tfidf_matrix[0:1]
    job_vecs = tfidf_matrix[1:]

    scores = cosine_similarity(resume_vec, job_vecs).flatten()
    df["tfidf_cosine_score"] = scores
    return df
