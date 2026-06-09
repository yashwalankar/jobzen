import argparse
import importlib
import json
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SCORE_SUFFIX = "_score"

_md = MarkdownIt()


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_resume(path: str) -> str:
    with open(path) as f:
        raw = f.read()
    html = _md.render(raw)
    return BeautifulSoup(html, "html.parser").get_text(separator=" ")


def load_jobs(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        print(f"Input file not found: {path}. Run without --score-only first.")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    jobs = data.get("jobs", [])
    if not jobs:
        print("No jobs found in input file.")
        sys.exit(0)
    return pd.DataFrame(jobs)


def run_scraper(scraper_args: list) -> None:
    cmd = [sys.executable, "scraper.py"] + scraper_args
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("Scraper exited with errors.")
        sys.exit(result.returncode)


def compute_composite(df: pd.DataFrame, steps: list, composite_cfg: dict) -> pd.DataFrame:
    enabled_score_cols = [
        f"{s['name']}{SCORE_SUFFIX}"
        for s in steps
        if s.get("enabled", True) and f"{s['name']}{SCORE_SUFFIX}" in df.columns
    ]
    if not enabled_score_cols:
        return df

    weights = {
        f"{s['name']}{SCORE_SUFFIX}": s.get("weight", 1.0)
        for s in steps
        if s.get("enabled", True)
    }
    total_weight = sum(weights[c] for c in enabled_score_cols)

    col = composite_cfg.get("column", "final_score")
    df[col] = sum(df[c] * weights[c] for c in enabled_score_cols) / total_weight
    return df


def select_columns(df: pd.DataFrame, output_columns: list, sort_col: str) -> pd.DataFrame:
    score_cols = [c for c in df.columns if c.endswith(SCORE_SUFFIX) or c == sort_col]
    if not output_columns:
        return df
    base = [c for c in output_columns if c in df.columns]
    extras = [c for c in score_cols if c not in base and c in df.columns]
    return df[base + extras]


def main():
    parser = argparse.ArgumentParser(description="Job scoring pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scrape-only", action="store_true", help="Run scraper only, skip scoring")
    mode.add_argument("--score-only", action="store_true", help="Score existing output, skip scraping")
    parser.add_argument("--pipeline-config", default="pipeline_config.json", dest="pipeline_config", help="Pipeline config file")
    parser.add_argument("--scraper-config", default=None, help="Config file to pass to scraper.py")
    parser.add_argument("--report-name", default=None, help="Override output report filename (written inside output/)")
    args = parser.parse_args()

    cfg = load_config(args.pipeline_config)

    if args.report_name:
        cfg["output_file"] = str(Path("output") / Path(args.report_name).name)

    scraper_args = ["--scraper-config", args.scraper_config] if args.scraper_config else []

    # If a scraper config is provided, its output_file takes precedence over pipeline input_file
    if args.scraper_config and not args.score_only:
        scraper_cfg = load_config(args.scraper_config)
        if "output_file" in scraper_cfg:
            cfg["input_file"] = scraper_cfg["output_file"]

    if args.scrape_only:
        run_scraper(scraper_args)
        return

    if not args.score_only:
        run_scraper(scraper_args)

    resume_text = load_resume(cfg["resume_file"])
    df = load_jobs(cfg["input_file"])

    for step_cfg in cfg.get("steps", []):
        if not step_cfg.get("enabled", True):
            log.info("Step '%s' skipped (disabled)", step_cfg["name"])
            continue
        name = step_cfg["name"]
        module = importlib.import_module(f"steps.{name}")
        log.info("Step '%s' starting", name)
        try:
            df = module.run(df, resume_text, step_cfg)
        except Exception as e:
            log.error("Step '%s' failed: %s", name, e)
            raise
        log.info("Step '%s' complete", name)

    composite_cfg = cfg.get("composite_score", {})
    if composite_cfg.get("enabled", True):
        df = compute_composite(df, cfg.get("steps", []), composite_cfg)

    sort_col = composite_cfg.get("column", "final_score")
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    df = select_columns(df, cfg.get("output_columns", []), sort_col)
    out_path = Path(cfg["output_file"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Report written to {cfg['output_file']} ({len(df)} jobs)")


if __name__ == "__main__":
    main()
