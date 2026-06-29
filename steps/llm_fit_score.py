import re
import pandas as pd

DEFAULT_MODEL = "llama3.1:8b"

_PROMPT = """\
Rate how well this candidate fits the job. Respond with exactly two lines:
SCORE: <integer 0-10>
REASON: <one sentence explaining the main fit or gap>

JOB DESCRIPTION:
{job}

CANDIDATE RESUME:
{resume}"""

_loaded_client = None


def _client():
    global _loaded_client
    if _loaded_client is None:
        import ollama
        _loaded_client = ollama
    return _loaded_client


def _ask(model: str, job: str, resume: str) -> tuple[float, str]:
    prompt = _PROMPT.format(job=job[:1800], resume=resume[:1800])
    resp = _client().chat(model=model, messages=[{"role": "user", "content": prompt}])
    text = resp.message.content

    score_match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)

    raw = float(score_match.group(1)) if score_match else _fallback_score(text)
    score = min(10.0, max(0.0, raw)) / 10.0
    reason = reason_match.group(1).strip() if reason_match else text.strip()[:200]
    return score, reason


def _fallback_score(text: str) -> float:
    for tok in re.findall(r"\b(\d+(?:\.\d+)?)\b", text):
        v = float(tok)
        if 0 <= v <= 10:
            return v
    return 5.0


def run(df: pd.DataFrame, resume_text: str, config: dict) -> pd.DataFrame:
    model = config.get("model", DEFAULT_MODEL)
    scores, rationales = [], []

    for i, desc in enumerate(df["description"]):
        if not desc or pd.isna(desc):
            scores.append(0.0)
            rationales.append("")
            continue
        try:
            s, r = _ask(model, str(desc), resume_text)
            scores.append(s)
            rationales.append(r)
        except Exception as e:
            scores.append(0.0)
            rationales.append(f"error: {e}")

    df["llm_fit_score"] = scores
    df["llm_fit_rationale"] = rationales
    return df
