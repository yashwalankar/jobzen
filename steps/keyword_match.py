import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

TECH_KEYWORDS = {
    # Languages
    "python", "java", "javascript", "typescript", "golang", "rust", "scala",
    "kotlin", "swift", "ruby", "php", "csharp", "cplusplus",
    # Web / frontend
    "react", "angular", "vue", "nextjs", "html", "css", "webpack",
    # Backend / infra
    "nodejs", "django", "fastapi", "flask", "spring", "rails",
    # Cloud / DevOps
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "helm",
    "ansible", "jenkins", "github", "gitlab", "circleci",
    # Data / ML
    "spark", "kafka", "airflow", "pytorch", "tensorflow", "sklearn",
    "pandas", "numpy", "dbt", "snowflake", "databricks",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "sqlite",
    # Other
    "graphql", "grpc", "rest", "linux", "git",
}

_analyzer = CountVectorizer(stop_words="english").build_analyzer()


def keyword_score(job_posting: str, resume_words: set) -> float:
    job_words = set(_analyzer(job_posting))

    job_tech    = job_words & TECH_KEYWORDS
    job_regular = job_words - TECH_KEYWORDS

    tech_score    = len(job_tech    & resume_words) / max(len(job_tech),    1)
    regular_score = len(job_regular & resume_words) / max(len(job_regular), 1)

    return 0.7 * tech_score + 0.3 * regular_score


def run(df: pd.DataFrame, resume_text: str, config: dict) -> pd.DataFrame:
    resume_words = set(_analyzer(resume_text)) if resume_text else set()

    def score(description):
        if not description or pd.isna(description):
            return 0.0
        return keyword_score(str(description), resume_words)

    df["keyword_match_score"] = df["description"].apply(score)
    return df
