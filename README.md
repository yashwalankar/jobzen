# LinkedIn Job Scraper & Scoring Pipeline

Scrapes LinkedIn job postings and ranks them against your resume using keyword matching, TF-IDF cosine similarity, and semantic embeddings.

---

## Installation

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
```

The first time `semantic_score` runs it will download the `BAAI/bge-large-en-v1.5` model (~1.3 GB).

---

## Setup

### 1. Resume

Place your resume at `about-me/resume.md`. The pipeline reads it as plain text — markdown formatting is stripped automatically.

### 2. Scraper config (`scraper_config.json`)

Controls what jobs are fetched from LinkedIn.

| Key | Default | Description |
|---|---|---|
| `search_term` | `"software engineer"` | LinkedIn search query |
| `location` | `"United States"` | Geographic target |
| `is_remote` | `true` | Remote jobs only |
| `hours_old` | `24` | Only jobs posted in the last N hours |
| `results_per_source` | `50` | Max results per search |
| `job_type` | `"fulltime"` | `fulltime`, `parttime`, `internship`, `contract` |
| `searches` | `[]` | List of per-search overrides (see below) |
| `company_blocklist` | `[]` | Companies to exclude (exact match) |
| `title_blocklist` | `[]` | Title substrings to exclude |
| `description_blocklist` | `[]` | Drop jobs whose description contains any of these |
| `excluded_location_keywords` | `[]` | Drop jobs whose location contains any of these |
| `output_file` | `"output/output_jobs.json"` | Where raw results are written |
| `seen_ids_file` | `".cache/seen_jobs.json"` | Persists seen job IDs across runs |
| `global_blocklist_file` | `"global_blocklist.json"` | Optional additive blocklist (never overridden) |

**Multi-search** — run several queries in one pass by adding a `searches` list. Each entry overrides any root-level key for that search only:

```json
{
  "hours_old": 48,
  "searches": [
    { "search_term": "backend engineer", "location": "New York", "is_remote": false },
    { "search_term": "software engineer", "location": "United States", "is_remote": true }
  ]
}
```

### 4. Pipeline config (`pipeline_config.json`)

Controls scoring and report generation.

```json
{
    "input_file": "output/output_jobs.json",
    "resume_file": "about-me/resume.md",
    "output_file": "output/report.csv",
    "output_columns": ["id", "title", "company", "job_url", "final_score", "description"],
    "steps": [
        { "name": "keyword_match",  "enabled": true, "weight": 0.25 },
        { "name": "tfidf_cosine",   "enabled": true, "weight": 0.25 },
        { "name": "semantic_score", "enabled": true, "weight": 0.50, "model": "bge-large" }
    ],
    "composite_score": {
        "enabled": true,
        "column": "final_score"
    }
}
```

| Key | Description |
|---|---|
| `input_file` | Raw jobs JSON produced by the scraper |
| `resume_file` | Path to your resume (markdown) |
| `output_file` | Where the scored CSV report is written (always inside `output/`) |
| `output_columns` | Columns to include in the report; `[]` = all |
| `steps` | Scoring steps to run, each with an optional `weight` |
| `composite_score.column` | Name of the final weighted score column |

**Scoring steps:**

| Step | Description |
|---|---|
| `keyword_match` | Tech-weighted keyword overlap using CountVectorizer. Tech terms count 70%, general words 30%. |
| `tfidf_cosine` | TF-IDF cosine similarity between job description and resume. |
| `semantic_score` | Semantic similarity via sentence embeddings. Model is configurable (see below). |

Weights are normalised automatically, so they don't need to sum to 1.

**`semantic_score` model options** — set via `"model"` in the step config:

| Key | Model | Size | Notes |
|---|---|---|---|
| `bge-large` | `BAAI/bge-large-en-v1.5` | ~1.3 GB | Default — best accuracy |
| `bge-base` | `BAAI/bge-base-en-v1.5` | ~440 MB | Good accuracy, 3x smaller |
| `bge-small` | `BAAI/bge-small-en-v1.5` | ~130 MB | Fastest, least accurate |
| `bge-m3` | `BAAI/bge-m3` | ~2.3 GB | Multilingual |
| `minilm` | `sentence-transformers/all-MiniLM-L6-v2` | ~80 MB | Very fast, popular general-purpose |
| `mpnet` | `sentence-transformers/all-mpnet-base-v2` | ~420 MB | Stronger than MiniLM |
| `mxbai` | `mixedbread-ai/mxbai-embed-large-v1` | ~1.3 GB | Competitive with bge-large |

Models are downloaded on first use and cached locally by `sentence-transformers`.

---

## Running the pipeline

`pipeline.py` runs the scraper and then scores the results in one command by default.

```bash
python pipeline.py
```

### Arguments

| Argument | Description |
|---|---|
| `--pipeline-config PATH` | Pipeline config file (default: `pipeline_config.json`) |
| `--scraper-config PATH` | Scraper config file (default: `scraper_config.json`) |
| `--report-name FILENAME` | Override the output report filename (written inside `output/`) |
| `--scrape-only` | Run the scraper only, skip scoring |
| `--score-only` | Score existing `input_file`, skip scraping |

### Examples

```bash
# Full run with defaults
python pipeline.py

# Use custom configs
python pipeline.py --pipeline-config pipeline_config.json --scraper-config scraper_config.json

# Save report under a custom name
python pipeline.py --report-name my_report.csv

# Only scrape (no scoring)
python pipeline.py --scrape-only --scraper-config scraper_config.json

# Only score an existing output_jobs.json
python pipeline.py --score-only
```

The scored report is written to `output/report.csv` (or the name passed via `--report-name`), sorted by `final_score` descending.

---

## Project structure

```
.
├── about-me/
│   └── resume.md               # Your resume
├── output/
│   ├── output_jobs.json        # Raw scraper results
│   └── report.csv              # Scored and ranked report
├── steps/
│   ├── keyword_match.py        # Tech-weighted keyword scoring
│   ├── tfidf_cosine.py         # TF-IDF cosine similarity
│   └── semantic_score.py       # Semantic embedding similarity
├── .cache/
│   └── seen_jobs.json          # Seen job ID cache (auto-managed)
├── global_blocklist.json       # Global company/title blocklist
├── scraper_config.json         # Scraper settings
├── pipeline_config.json        # Pipeline and scoring settings
├── scraper.py                  # LinkedIn scraper
├── pipeline.py                 # Orchestrates scraping + scoring
└── requirements.txt
```
