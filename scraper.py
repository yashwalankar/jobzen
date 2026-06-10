"""
LinkedIn Job Scraper
====================
Uses JobSpy (github.com/speedyapply/JobSpy) to scrape LinkedIn job postings,
then applies filters: seen IDs, company blocklist, location check, repost detection.

Usage:
    python scraper.py
    python scraper.py --config config.json
    python scraper.py --dry-run        # print results, don't save
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from jobspy import scrape_jobs

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("output")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    # --- Search criteria ---
    "search_term": "software engineer",
    "location": "United States",
    "is_remote": True,
    "distance": None,         # miles radius from location (None = site default)
    "hours_old": 24,          # only jobs posted in the last N hours
    "results_per_source": 50, # max results to fetch per job board per search
    "job_type": "fulltime",   # fulltime | parttime | internship | contract | ""
    "searches": [],           # list of per-search override dicts; [] = run a single search using root-level keys

    # --- Filters ---
    "company_blocklist": [],  # e.g. ["Jobot", "Crossover"]
    "title_blocklist": [],    # e.g. ["Staff", "Principal", "Director"]
    "title_allowlist": [],    # if non-empty, only keep jobs whose title matches one of these
    "required_location_keywords": [],  # e.g. ["remote", "united states"] — location must contain at least one
    "excluded_location_keywords": [],  # e.g. ["canada", "windsor"] — drop jobs whose location contains any of these
    "description_blocklist": [],      # e.g. ["ts/sci", "security clearance"] — drop jobs whose description contains any of these
    "description_allowlist": [],      # if non-empty, only keep jobs whose description contains at least one keyword
    "disabled_filters": [],   # skip named filters: "seen", "company_blocklist", "title_blocklist",
                              #   "title_allowlist", "location", "location_exclusion",
                              #   "description_blocklist", "description_allowlist"

    # --- Storage ---
    "output_file": "output_jobs.json",
    "output_columns": [],     # columns to include in output; [] = all available columns
    "seen_ids_file": ".cache/seen_jobs.json",
    "global_blocklist_file": "global_blocklist.json",

    # --- Behaviour ---
    "fetch_description": True,          # slower but gives full description + direct URL
    "filtered_job_posts_minimum": 0,    # expand hours_old until this many filtered results (0 = disabled)
    "hours_old_max": 168,               # ceiling for hours_old expansion (default: 1 week)
    "hours_old_increment": 24,          # step size when expanding hours_old
}


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

_EXPECTED_TYPES: dict = {
    "search_term":                str,
    "location":                   str,
    "is_remote":                  bool,
    "hours_old":                  int,
    "results_per_source":         int,
    "job_type":                   str,
    "company_blocklist":          list,
    "title_blocklist":            list,
    "title_allowlist":            list,
    "required_location_keywords": list,
    "excluded_location_keywords": list,
    "description_blocklist":      list,
    "description_allowlist":      list,
    "fetch_description":          bool,
    "filtered_job_posts_minimum": int,
    "hours_old_max":              int,
    "hours_old_increment":        int,
    "disabled_filters":           list,
    "output_columns":             list,
    "searches":                   list,
}

_VALID_FILTER_NAMES = {
    "seen", "company_blocklist", "title_blocklist",
    "title_allowlist", "location", "location_exclusion", "remote",
    "description_blocklist", "description_allowlist",
}


def _validate_config(cfg: dict) -> None:
    for key, expected in _EXPECTED_TYPES.items():
        if key in cfg and not isinstance(cfg[key], expected):
            raise SystemExit(
                f"Config error: '{key}' must be {expected.__name__}, "
                f"got {type(cfg[key]).__name__} ({cfg[key]!r})"
            )
    for f in cfg.get("disabled_filters", []):
        if f not in _VALID_FILTER_NAMES:
            raise SystemExit(
                f"Config error: unknown filter '{f}' in disabled_filters. "
                f"Valid values: {sorted(_VALID_FILTER_NAMES)}"
            )
    for i, entry in enumerate(cfg.get("searches", [])):
        if not isinstance(entry, dict):
            raise SystemExit(f"Config error: searches[{i}] must be an object, got {type(entry).__name__}")
        for key, val in entry.items():
            if key in _EXPECTED_TYPES and not isinstance(val, _EXPECTED_TYPES[key]):
                raise SystemExit(
                    f"Config error: searches[{i}].'{key}' must be {_EXPECTED_TYPES[key].__name__}, "
                    f"got {type(val).__name__} ({val!r})"
                )


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            try:
                overrides = json.load(f)
            except json.JSONDecodeError as e:
                raise SystemExit(f"Config file '{config_path}' is not valid JSON: {e}") from e
        cfg.update(overrides)
        log.info("Loaded config from %s", config_path)
    else:
        log.info("No config file found — using defaults")
    _validate_config(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Seen-IDs persistence
# ---------------------------------------------------------------------------

def load_seen_ids(path: str) -> set:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise SystemExit(f"Seen-IDs file '{path}' is not valid JSON: {e}") from e
        log.info("Loaded %d seen job IDs from %s", len(data), p)
        return set(data)
    return set()


def save_seen_ids(seen: set, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(sorted(seen), f, indent=2)
    log.info("Saved %d seen job IDs to %s", len(seen), p)


# ---------------------------------------------------------------------------
# Global blocklist
# ---------------------------------------------------------------------------

def load_global_blocklist(path: str) -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise SystemExit(f"Global blocklist file '{path}' is not valid JSON: {e}") from e
        log.info(
            "Loaded global blocklist: %d companies, %d titles",
            len(data.get("company_blocklist", [])),
            len(data.get("title_blocklist", [])),
        )
        return data
    log.info("No global blocklist found at '%s' — skipping", path)
    return {}


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def fetch_jobs(cfg: dict) -> pd.DataFrame:
    log.info(
        "Searching LinkedIn for '%s' | location='%s' | remote=%s | hours_old=%d | results_per_source=%d",
        cfg["search_term"],
        cfg["location"],
        cfg["is_remote"],
        cfg["hours_old"],
        cfg["results_per_source"],
    )
    jobs = scrape_jobs(
        site_name=["linkedin"],
        search_term=cfg["search_term"],
        location=cfg["location"],
        is_remote=bool(cfg["is_remote"]),
        distance=cfg.get("distance") or None,
        hours_old=cfg["hours_old"],
        results_wanted=cfg["results_per_source"],
        job_type=cfg["job_type"] or None,
        linkedin_fetch_description=cfg.get("fetch_description", True),
        verbose=1,
    )
    log.info("Raw results from LinkedIn: %d", len(jobs))
    return jobs


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _norm(s) -> str:
    """Lowercase + strip for comparison."""
    return str(s).lower().strip() if s and str(s) != "nan" else ""


def filter_seen(df: pd.DataFrame, seen_ids: set) -> pd.DataFrame:
    if "id" not in df.columns:
        log.warning("No 'id' column — skipping seen-ID filter")
        return df
    before = len(df)
    df = df[~df["id"].astype(str).isin(seen_ids)]
    log.info("After seen-ID filter: %d → %d", before, len(df))
    return df


def filter_company_blocklist(df: pd.DataFrame, blocklist: list) -> pd.DataFrame:
    if not blocklist or "company" not in df.columns:
        return df
    blocked_lower = {b.lower().strip() for b in blocklist}
    before = len(df)
    df = df[~df["company"].apply(_norm).isin(blocked_lower)]
    log.info("After company blocklist filter: %d → %d", before, len(df))
    return df


def filter_title_blocklist(df: pd.DataFrame, blocklist: list) -> pd.DataFrame:
    if not blocklist or "title" not in df.columns:
        return df
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in blocklist]
    before = len(df)
    def is_blocked(title):
        t = str(title)
        return any(p.search(t) for p in patterns)
    df = df[~df["title"].apply(is_blocked)]
    log.info("After title blocklist filter: %d → %d", before, len(df))
    return df


def filter_title_allowlist(df: pd.DataFrame, allowlist: list) -> pd.DataFrame:
    if not allowlist or "title" not in df.columns:
        return df
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in allowlist]
    before = len(df)
    def is_allowed(title):
        t = str(title)
        return any(p.search(t) for p in patterns)
    df = df[df["title"].apply(is_allowed)]
    log.info("After title allowlist filter: %d → %d", before, len(df))
    return df


def filter_location(df: pd.DataFrame, required_keywords: list) -> pd.DataFrame:
    """Keep rows where location contains at least one required keyword."""
    if not required_keywords or "location" not in df.columns:
        return df
    kws_lower = [k.lower().strip() for k in required_keywords]
    before = len(df)
    def location_ok(loc):
        loc_lower = _norm(loc)
        return any(kw in loc_lower for kw in kws_lower)
    df = df[df["location"].apply(location_ok)]
    log.info("After location filter: %d → %d", before, len(df))
    return df


def filter_location_exclusion(df: pd.DataFrame, excluded_keywords: list) -> pd.DataFrame:
    """Drop rows where location contains any excluded keyword."""
    if not excluded_keywords or "location" not in df.columns:
        return df
    kws_lower = [k.lower().strip() for k in excluded_keywords]
    before = len(df)
    def location_excluded(loc):
        loc_lower = _norm(loc)
        return any(kw in loc_lower for kw in kws_lower)
    df = df[~df["location"].apply(location_excluded)]
    log.info("After location exclusion filter: %d → %d", before, len(df))
    return df


def filter_description_blocklist(df: pd.DataFrame, blocklist: list) -> pd.DataFrame:
    """Drop jobs whose description contains any blocked keyword (case-insensitive substring)."""
    if not blocklist or "description" not in df.columns:
        return df
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in blocklist]
    before = len(df)
    def is_blocked(desc):
        d = str(desc) if desc and str(desc) != "nan" else ""
        return any(p.search(d) for p in patterns)
    df = df[~df["description"].apply(is_blocked)]
    log.info("After description blocklist filter: %d → %d", before, len(df))
    return df


def filter_description_allowlist(df: pd.DataFrame, allowlist: list) -> pd.DataFrame:
    """Keep only jobs whose description contains at least one allowed keyword (case-insensitive substring)."""
    if not allowlist or "description" not in df.columns:
        return df
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in allowlist]
    before = len(df)
    def is_allowed(desc):
        d = str(desc) if desc and str(desc) != "nan" else ""
        return any(p.search(d) for p in patterns)
    df = df[df["description"].apply(is_allowed)]
    log.info("After description allowlist filter: %d → %d", before, len(df))
    return df


def filter_remote(df: pd.DataFrame, is_remote: bool) -> pd.DataFrame:
    """Drop jobs whose scraped is_remote field contradicts the search's is_remote setting."""
    if "is_remote" not in df.columns:
        return df
    before = len(df)
    df = df[df["is_remote"].apply(lambda v: bool(v) == is_remote if v is not None and str(v) != "nan" else True)]
    log.info("After remote filter (is_remote=%s): %d → %d", is_remote, before, len(df))
    return df


def filter_reposts(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicates by (title, company) — keeps the first occurrence."""
    if "title" not in df.columns or "company" not in df.columns:
        return df
    before = len(df)
    df = df.copy()
    df["_dedup_key"] = df["title"].apply(_norm) + "||" + df["company"].apply(_norm)
    df = df.drop_duplicates(subset="_dedup_key").drop(columns=["_dedup_key"])
    log.info("After repost dedup filter: %d → %d", before, len(df))
    return df


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

KEEP_COLUMNS = [
    "id", "site", "job_url", "job_url_direct",
    "title", "company", "location",
    "job_type", "date_posted", "salary_source",
    "interval", "min_amount", "max_amount", "currency",
    "is_remote", "job_level", "job_function",
    "listing_type", "emails", "description",
    "company_industry", "company_url", "company_url_direct",
    "company_addresses", "company_num_employees", "company_revenue",
    "company_description", "logo_photo_url", "banner_photo_url",
    "ceo_name", "ceo_photo_url",
]


def df_to_records(df: pd.DataFrame, columns: list | None = None) -> list:
    """Convert DataFrame to a list of clean dicts for JSON output."""
    cols_wanted = columns if columns else KEEP_COLUMNS
    cols = [c for c in cols_wanted if c in df.columns]
    out = []
    for _, row in df[cols].iterrows():
        record = {}
        for col in cols:
            val = row[col]
            # Convert pandas NA / NaT / float NaN to None for clean JSON
            if pd.isna(val) if not isinstance(val, (list, dict)) else False:
                record[col] = None
            elif hasattr(val, "isoformat"):          # datetime
                record[col] = val.isoformat()
            elif isinstance(val, float) and val == int(val):
                record[col] = int(val)
            else:
                record[col] = val
        raw_title = record.get("title")
        raw_url = record.get("job_url")
        if raw_title and raw_url:
            record["job_link"] = f"[{raw_title}]({raw_url})"
        record.pop("job_url", None)
        record.pop("title", None)
        out.append(record)
    return out


def save_output(path: str, records: list, search_cfgs: list) -> None:
    criteria = [
        {
            "search_term": s["search_term"],
            "location": s["location"],
            "is_remote": s["is_remote"],
            "hours_old": s["hours_old"],
            "job_type": s["job_type"],
        }
        for s in search_cfgs
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "search_criteria": criteria[0] if len(criteria) == 1 else criteria,
        "total_new_jobs": len(records),
        "jobs": records,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    log.info("Wrote %d jobs to %s", len(records), path)


# ---------------------------------------------------------------------------
# Multi-search helpers
# ---------------------------------------------------------------------------

def _merge_search_cfg(base: dict, override: dict) -> dict:
    """Merge a per-search override into the base config. Override keys replace base values."""
    return {**base, **override}


def _run_search(cfg: dict, seen_ids: set) -> tuple:
    """Fetch and filter one search config. Returns (raw_df, filtered_df)."""
    try:
        raw_df = fetch_jobs(cfg)
    except Exception as e:
        log.error("Fetch failed for search '%s': %s", cfg["search_term"], e)
        return pd.DataFrame(), pd.DataFrame()

    if raw_df.empty:
        return raw_df, raw_df

    disabled = set(cfg.get("disabled_filters", []))
    df = raw_df

    if "seen"                   not in disabled: df = filter_seen(df, seen_ids)
    if "company_blocklist"      not in disabled: df = filter_company_blocklist(df, cfg.get("company_blocklist", []))
    if "title_blocklist"        not in disabled: df = filter_title_blocklist(df, cfg.get("title_blocklist", []))
    if "title_allowlist"        not in disabled: df = filter_title_allowlist(df, cfg.get("title_allowlist", []))
    if "location"               not in disabled: df = filter_location(df, cfg.get("required_location_keywords", []))
    if "location_exclusion"     not in disabled: df = filter_location_exclusion(df, cfg.get("excluded_location_keywords", []))
    if "remote"                 not in disabled: df = filter_remote(df, bool(cfg.get("is_remote", True)))
    if "description_blocklist"  not in disabled: df = filter_description_blocklist(df, cfg.get("description_blocklist", []))
    if "description_allowlist"  not in disabled: df = filter_description_allowlist(df, cfg.get("description_allowlist", []))

    return raw_df, df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LinkedIn job scraper")
    parser.add_argument("--scraper-config", default="config.json", dest="config", help="Path to config JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print results, skip saving")
    parser.add_argument("--output-file", default=None, help="Override output file path from config")
    args = parser.parse_args()

    load_dotenv()  # load LINKEDIN_EMAIL / LINKEDIN_PASSWORD if needed

    cfg = load_config(args.config)
    if args.output_file:
        cfg["output_file"] = Path(args.output_file).name
    p = Path(cfg["output_file"])
    if p.parent == Path("."):
        cfg["output_file"] = str(OUTPUT_DIR / p)

    # Global blocklist is always additive — it prepends to whatever config.json specifies
    global_bl = load_global_blocklist(cfg["global_blocklist_file"])
    for key in ("company_blocklist", "title_blocklist"):
        cfg[key] = global_bl.get(key, []) + cfg.get(key, [])

    # Build per-search configs
    searches_overrides = cfg.pop("searches", None)
    if searches_overrides:
        search_cfgs = [_merge_search_cfg(cfg, override) for override in searches_overrides]
        log.info("Running %d searches", len(search_cfgs))
    else:
        search_cfgs = [cfg]

    # 1. Load seen IDs once for all searches
    seen_ids = load_seen_ids(cfg["seen_ids_file"])

    minimum       = cfg.get("filtered_job_posts_minimum", 0)
    hours_old_max = cfg.get("hours_old_max", 168)
    increment     = cfg.get("hours_old_increment", 24)
    current_hours = search_cfgs[0]["hours_old"]  # all searches share the same starting value

    combined_filtered = pd.DataFrame()
    this_run_ids: set = set()  # IDs collected across all passes this run

    while True:
        # Apply current hours_old to all search configs for this pass
        pass_cfgs = [{**s, "hours_old": current_hours} for s in search_cfgs]

        # Fetch + filter — skip IDs already collected this run
        effective_seen = seen_ids | this_run_ids
        pass_raw_dfs, pass_filtered_dfs = [], []
        for search_cfg in pass_cfgs:
            raw_df, filtered_df = _run_search(search_cfg, effective_seen)
            pass_raw_dfs.append(raw_df)
            pass_filtered_dfs.append(filtered_df)

        def _concat(dfs):
            non_empty = [d.dropna(axis=1, how="all") for d in dfs if not d.empty]
            return pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame()

        pass_raw      = _concat(pass_raw_dfs)
        pass_filtered = _concat(pass_filtered_dfs)

        if "id" in pass_raw.columns:
            this_run_ids |= set(pass_raw["id"].astype(str).tolist())

        if not pass_filtered.empty:
            combined_filtered = pd.concat([combined_filtered, pass_filtered], ignore_index=True)

        # Cross-search repost dedup on accumulated results
        deduped = filter_reposts(combined_filtered) if not combined_filtered.empty else combined_filtered

        if minimum <= 0 or len(deduped) >= minimum:
            combined_filtered = deduped
            break

        next_hours = current_hours + increment
        if next_hours > hours_old_max:
            log.warning(
                "Reached hours_old_max=%d with %d filtered results (minimum=%d) — stopping expansion.",
                hours_old_max, len(deduped), minimum,
            )
            combined_filtered = deduped
            break

        log.info(
            "Filtered results %d < minimum %d — expanding hours_old %d → %d",
            len(deduped), minimum, current_hours, next_hours,
        )
        current_hours = next_hours

    log.info("Final new jobs after all filters: %d (hours_old=%d)", len(combined_filtered), current_hours)

    if combined_filtered.empty:
        log.info("Nothing new to report.")
        if not args.dry_run:
            save_seen_ids(seen_ids | this_run_ids, cfg["seen_ids_file"])
        sys.exit(0)

    # 5. Convert to records
    output_columns = cfg.get("output_columns") or None
    records = df_to_records(combined_filtered, output_columns)

    if args.dry_run:
        print(json.dumps(records[:5], indent=2, default=str))
        log.info("Dry run — not saving. Showing first %d of %d jobs.", min(5, len(records)), len(records))
        return

    # 6. Save output
    save_output(cfg["output_file"], records, search_cfgs)

    # 7. Update seen IDs (mark ALL fetched jobs as seen, not just the filtered ones)
    save_seen_ids(seen_ids | this_run_ids, cfg["seen_ids_file"])


if __name__ == "__main__":
    main()
