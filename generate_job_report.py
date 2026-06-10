#!/usr/bin/env python3
"""
generate_job_report.py
Usage: python generate_job_report.py <input.json> [output.html]
       python generate_job_report.py results.json
       python generate_job_report.py results.json my_report.html
"""

import json
import sys
import os
from pathlib import Path


def load_data(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def score_color(score: int) -> str:
    if score >= 80:
        return "#22c55e"   # green
    elif score >= 60:
        return "#f59e0b"   # amber
    elif score >= 40:
        return "#f97316"   # orange
    else:
        return "#ef4444"   # red


def score_badge_class(score: int) -> str:
    if score >= 80:
        return "badge-green"
    elif score >= 60:
        return "badge-amber"
    elif score >= 40:
        return "badge-orange"
    else:
        return "badge-red"


def recommendation_class(rec: str) -> str:
    return {
        "apply": "rec-apply",
        "skip":  "rec-skip",
    }.get(rec.lower(), "rec-neutral")


def build_rows_json(jobs: list) -> str:
    """Flatten each job into a plain dict for the JS data array."""
    rows = []
    for job in jobs:
        dims = job.get("dimensions", {})
        must = job.get("must_haves", {})
        rows.append({
            "job_id":          job.get("job_id", ""),
            "company":         job.get("company", ""),
            "job_link":        job.get("job_link", ""),
            "overall_score":   job.get("overall_score", 0),
            "technical":       dims.get("technical_skills", {}).get("score", 0),
            "experience":      dims.get("experience_level", {}).get("score", 0),
            "domain":          dims.get("domain_knowledge", {}).get("score", 0),
            "soft_skills":     dims.get("soft_skills", {}).get("score", 0),
            "recommendation":  job.get("recommendation", ""),
            "summary":         job.get("summary", ""),
            "strengths":       job.get("strengths", []),
            "gaps":            job.get("gaps", []),
            "must_met":        must.get("met", []),
            "must_missing":    must.get("missing", []),
            "tech_evidence":   dims.get("technical_skills", {}).get("evidence", []),
            "exp_evidence":    dims.get("experience_level", {}).get("evidence", []),
            "domain_evidence": dims.get("domain_knowledge", {}).get("evidence", []),
        })
    return json.dumps(rows, indent=2)


def generate_html(jobs: list, source_file: str) -> str:
    rows_json = build_rows_json(jobs)
    total     = len(jobs)
    applies   = sum(1 for j in jobs if j.get("recommendation", "").lower() == "apply")
    maybes    = sum(1 for j in jobs if j.get("recommendation", "").lower() == "maybe")
    skips     = sum(1 for j in jobs if j.get("recommendation", "").lower() == "skip")
    avg_score = round(sum(j.get("overall_score", 0) for j in jobs) / total) if total else 0

    filename = os.path.basename(source_file)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Job Match Report for {filename}</title>
  <style>
    /* ── Reset & tokens ─────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0f1117;
      --surface:   #1a1d27;
      --surface2:  #22263a;
      --border:    #2e3348;
      --text:      #e2e8f0;
      --text-dim:  #8892aa;
      --accent:    #6366f1;
      --accent-hi: #818cf8;
      --green:     #22c55e;
      --amber:     #f59e0b;
      --orange:    #f97316;
      --red:       #ef4444;
      --radius:    10px;
      --mono:      "JetBrains Mono", "Fira Mono", monospace;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: "Inter", system-ui, -apple-system, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      min-height: 100vh;
    }}

    /* ── Layout ─────────────────────────────────────── */
    .shell {{ max-width: 1400px; margin: 0 auto; padding: 28px 24px; }}

    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }}

    header h1 {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text);
    }}
    header h1 .label {{ color: var(--text-dim); font-weight: 400; }}
    header h1 .fname {{ color: var(--accent-hi); }}

    /* ── KPI cards ──────────────────────────────────── */
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
      margin-bottom: 28px;
    }}
    .kpi {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 20px;
    }}
    .kpi-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .7px;
      color: var(--text-dim);
      margin-bottom: 6px;
    }}
    .kpi-value {{
      font-size: 30px;
      font-weight: 800;
      line-height: 1;
      color: var(--text);
    }}
    .kpi-value.green {{ color: var(--green); }}
    .kpi-value.red   {{ color: var(--red); }}
    .kpi-value.amber {{ color: var(--amber); }}
    .kpi-value.purple {{ color: var(--accent-hi); }}

    /* ── Controls bar ───────────────────────────────── */
    .controls {{
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }}
    .search-wrap {{ position: relative; flex: 1; min-width: 200px; }}
    .search-wrap input {{
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 8px 10px 8px 34px;
      font-size: 13px;
      outline: none;
    }}
    .search-wrap input:focus {{ border-color: var(--accent); }}
    .search-icon {{
      position: absolute;
      left: 10px; top: 50%;
      transform: translateY(-50%);
      color: var(--text-dim);
      pointer-events: none;
    }}

    select {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 8px 10px;
      font-size: 13px;
      cursor: pointer;
      outline: none;
    }}
    select:focus {{ border-color: var(--accent); }}

    .results-count {{
      margin-left: auto;
      color: var(--text-dim);
      font-size: 12px;
      white-space: nowrap;
    }}

    /* ── Table ──────────────────────────────────────── */
    .table-wrap {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
    }}

    thead th {{
      padding: 11px 14px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .6px;
      color: var(--text-dim);
      text-align: left;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
      cursor: pointer;
      user-select: none;
      position: sticky;
      top: 0;
      background: var(--surface);
      z-index: 1;
    }}
    thead th:hover {{ color: var(--text); }}
    thead th.sort-asc::after  {{ content: " ▲"; color: var(--accent-hi); font-size: 9px; }}
    thead th.sort-desc::after {{ content: " ▼"; color: var(--accent-hi); font-size: 9px; }}

    tbody tr {{
      border-bottom: 1px solid var(--border);
      transition: background .12s;
      cursor: pointer;
    }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: var(--surface2); }}
    tbody tr.expanded {{ background: var(--surface2); }}

    td {{
      padding: 10px 14px;
      vertical-align: middle;
    }}

    .job-id {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--accent-hi);
    }}

    /* ── Score pill ─────────────────────────────────── */
    .score-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 700;
      font-size: 13px;
    }}
    .score-bar-bg {{
      width: 48px; height: 5px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
    }}
    .score-bar-fill {{ height: 100%; border-radius: 3px; }}

    /* ── Badges ─────────────────────────────────────── */
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .3px;
    }}
    .badge-green  {{ background: #14532d44; color: var(--green); border: 1px solid #166534aa; }}
    .badge-amber  {{ background: #7c2d1244; color: var(--amber); border: 1px solid #92400e88; }}
    .badge-orange {{ background: #7c2d1244; color: var(--orange); border: 1px solid #c2410c88; }}
    .badge-red    {{ background: #450a0a44; color: var(--red);   border: 1px solid #7f1d1d88; }}

    .rec-apply  {{ background: #14532d55; color: var(--green);  border: 1px solid #16653488; }}
    .rec-maybe  {{ background: #4c1d9555; color: #a78bfa;      border: 1px solid #5b21b688; }}
    .rec-skip   {{ background: #450a0a44; color: var(--red);    border: 1px solid #7f1d1d88; }}
    .rec-neutral {{ background: var(--surface2); color: var(--text-dim); border: 1px solid var(--border); }}

    /* ── Applied checkbox ───────────────────────────────── */
    .applied-cell {{
      width: 52px;
      text-align: center;
      vertical-align: middle;
    }}
    .cb-wrap {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }}
    .cb-wrap input[type="checkbox"] {{ display: none; }}
    .cb-custom {{
      width: 18px; height: 18px;
      border: 2px solid var(--border);
      border-radius: 4px;
      background: var(--surface2);
      display: flex; align-items: center; justify-content: center;
      transition: all .15s;
      flex-shrink: 0;
    }}
    .cb-wrap input:checked + .cb-custom {{
      background: var(--accent);
      border-color: var(--accent);
    }}
    .cb-wrap input:checked + .cb-custom::after {{
      content: "";
      display: block;
      width: 5px; height: 9px;
      border: 2px solid #fff;
      border-top: none;
      border-left: none;
      transform: rotate(45deg) translateY(-1px);
    }}
    .cb-wrap:hover .cb-custom {{ border-color: var(--accent-hi); }}

    /* ── Expand row ─────────────────────────────────── */
    .expand-cell {{ width: 28px; }}
    .expander {{
      width: 20px; height: 20px;
      border-radius: 4px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--text-dim);
      font-size: 11px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: all .15s;
    }}
    .expander:hover {{ background: var(--border); color: var(--text); }}

    /* ── Detail panel ───────────────────────────────── */
    .detail-row td {{ padding: 0; }}
    .detail-inner {{
      padding: 20px 20px 20px 42px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 20px;
      background: #131620;
      border-top: 1px solid var(--border);
    }}
    .detail-section h4 {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .6px;
      color: var(--text-dim);
      margin-bottom: 10px;
    }}
    .detail-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }}
    .detail-list li {{
      font-size: 12px;
      line-height: 1.5;
      color: var(--text);
      padding-left: 14px;
      position: relative;
    }}
    .detail-list li::before {{
      content: "·";
      position: absolute; left: 0;
      color: var(--text-dim);
    }}
    .detail-list.green li::before {{ color: var(--green); }}
    .detail-list.red   li::before {{ color: var(--red); }}

    .summary-text {{
      font-size: 12px;
      color: var(--text-dim);
      line-height: 1.6;
      grid-column: 1 / -1;
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }}

    /* ── Dim score cells ────────────────────────────── */
    .dim-grid {{
      display: grid;
      grid-template-columns: repeat(4, auto);
      gap: 4px 10px;
      font-size: 12px;
    }}
    .dim-label {{ color: var(--text-dim); }}
    .dim-value {{ font-weight: 600; }}

    /* ── Empty state ────────────────────────────────── */
    .empty {{
      text-align: center;
      padding: 48px 20px;
      color: var(--text-dim);
    }}
    .empty svg {{ margin-bottom: 12px; opacity: .4; }}
  </style>
</head>
<body>
<div class="shell">

  <header>
    <div>
      <h1>Job Match Report <span class="label">for</span> <span class="fname">{filename}</span></h1>
    </div>
  </header>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi">
      <div class="kpi-label">Total Jobs</div>
      <div class="kpi-value">{total}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Applied</div>
      <div class="kpi-value purple" id="kpi-applied">0</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Recommended</div>
      <div class="kpi-value green">{applies}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Maybe</div>
      <div class="kpi-value amber">{maybes}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Skip</div>
      <div class="kpi-value red">{skips}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Avg Score</div>
      <div class="kpi-value amber">{avg_score}</div>
    </div>
  </div>

  <!-- Controls -->
  <div class="controls">
    <div class="search-wrap">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input id="search" type="text" placeholder="Search company, job title, summary…" oninput="applyFilters()" />
    </div>
    <select id="rec-filter" onchange="applyFilters()">
      <option value="">All Recommendations</option>
      <option value="apply">Apply</option>
      <option value="maybe">Maybe</option>
      <option value="skip">Skip</option>
    </select>
    <select id="applied-filter" onchange="applyFilters()">
      <option value="">All (Applied &amp; Not)</option>
      <option value="yes">Applied ✓</option>
      <option value="no">Not Applied</option>
    </select>
    <select id="score-filter" onchange="applyFilters()">
      <option value="">All Scores</option>
      <option value="80">80+</option>
      <option value="60">60–79</option>
      <option value="40">40–59</option>
      <option value="0">Below 40</option>
    </select>
    <span class="results-count" id="results-count"></span>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <table id="main-table">
      <thead>
        <tr>
          <th onclick="sortBy('applied')" data-col="applied" title="Sort by Applied">Applied</th>
          <th class="expand-cell"></th>
          <th onclick="sortBy('company')"       data-col="company">Company</th>
          <th onclick="sortBy('job_link')"      data-col="job_link">Job</th>
          <th onclick="sortBy('overall_score')" data-col="overall_score">Overall</th>
          <th onclick="sortBy('technical')"     data-col="technical">Technical</th>
          <th onclick="sortBy('experience')"    data-col="experience">Experience</th>
          <th onclick="sortBy('domain')"        data-col="domain">Domain</th>
          <th onclick="sortBy('soft_skills')"   data-col="soft_skills">Soft Skills</th>
          <th onclick="sortBy('recommendation')" data-col="recommendation">Recommendation</th>
          <th>Summary</th>
        </tr>
      </thead>
      <tbody id="table-body"></tbody>
    </table>
    <div class="empty" id="empty-state" style="display:none">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <div>No jobs match the current filters.</div>
    </div>
  </div>

</div>

<script>
const RAW_DATA = {rows_json};

let filtered   = [...RAW_DATA];
let sortCol    = "overall_score";
let sortDir    = -1;           // -1 = desc, 1 = asc
let expanded   = new Set();
let applied    = new Set();    // tracks checked job IDs

/* ── Helpers ─────────────────────────────────────────── */
function scoreColor(s) {{
  if (s >= 80) return "#22c55e";
  if (s >= 60) return "#f59e0b";
  if (s >= 40) return "#f97316";
  return "#ef4444";
}}

function scoreBadgeClass(s) {{
  if (s >= 80) return "badge badge-green";
  if (s >= 60) return "badge badge-amber";
  if (s >= 40) return "badge badge-orange";
  return "badge badge-red";
}}

function scorePill(s) {{
  const col = scoreColor(s);
  return `
    <span class="score-pill">
      <strong style="color:${{col}}">${{s}}</strong>
      <span class="score-bar-bg">
        <span class="score-bar-fill" style="width:${{s}}%;background:${{col}}"></span>
      </span>
    </span>`;
}}

function recBadge(rec) {{
  const cls = rec === "apply" ? "badge rec-apply" :
              rec === "skip"  ? "badge rec-skip"  :
              rec === "maybe" ? "badge rec-maybe" : "badge rec-neutral";
  return `<span class="${{cls}}">${{rec}}</span>`;
}}

function esc(s) {{
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

function parseMarkdownLink(s) {{
  const m = String(s).match(/^\[(.+)\]\((.+)\)$/);
  return m
    ? `<a href="${{esc(m[2])}}" target="_blank" rel="noopener" style="color:var(--accent-hi)">${{esc(m[1])}}</a>`
    : esc(s);
}}

/* ── Applied KPI ──────────────────────────────────────── */
function updateAppliedKPI() {{
  document.getElementById("kpi-applied").textContent = applied.size;
}}

/* ── Render ───────────────────────────────────────────── */
function renderTable() {{
  const tbody = document.getElementById("table-body");
  const empty = document.getElementById("empty-state");

  if (!filtered.length) {{
    tbody.innerHTML = "";
    empty.style.display = "";
    return;
  }}
  empty.style.display = "none";

  const rows = filtered.map((row, i) => {{
    const id         = row.job_id;
    const isOpen     = expanded.has(id);
    const isApplied  = applied.has(id);
    const detailHtml = isOpen ? buildDetail(row) : "";

    return `
      <tr class="${{isOpen ? "expanded" : ""}}" onclick="toggleRow(event,'${{esc(id)}}')">
        <td class="applied-cell" onclick="event.stopPropagation()">
          <label class="cb-wrap" title="Mark as applied">
            <input type="checkbox" ${{isApplied ? "checked" : ""}}
              onchange="toggleApplied('${{esc(id)}}', this.checked)" />
            <span class="cb-custom"></span>
          </label>
        </td>
        <td class="expand-cell">
          <button class="expander" title="Details">${{isOpen ? "▲" : "▼"}}</button>
        </td>
        <td style="font-size:13px">${{esc(row.company)}}</td>
        <td style="font-size:13px">${{parseMarkdownLink(row.job_link)}}</td>
        <td>${{scorePill(row.overall_score)}}</td>
        <td><span class="${{scoreBadgeClass(row.technical)}}">${{row.technical}}</span></td>
        <td><span class="${{scoreBadgeClass(row.experience)}}">${{row.experience}}</span></td>
        <td><span class="${{scoreBadgeClass(row.domain)}}">${{row.domain}}</span></td>
        <td><span class="${{scoreBadgeClass(row.soft_skills)}}">${{row.soft_skills}}</span></td>
        <td>${{recBadge(row.recommendation)}}</td>
        <td style="max-width:340px;font-size:12px;color:var(--text-dim)">${{esc(row.summary)}}</td>
      </tr>
      ${{isOpen ? `<tr class="detail-row"><td colspan="11">${{detailHtml}}</td></tr>` : ""}}
    `;
  }}).join("");

  tbody.innerHTML = rows;
  document.getElementById("results-count").textContent =
    `Showing ${{filtered.length}} of ${{RAW_DATA.length}} job${{RAW_DATA.length !== 1 ? "s" : ""}}`;

  // Update sort arrows
  document.querySelectorAll("thead th[data-col]").forEach(th => {{
    th.classList.remove("sort-asc","sort-desc");
    if (th.dataset.col === sortCol) {{
      th.classList.add(sortDir === 1 ? "sort-asc" : "sort-desc");
    }}
  }});
}}

function buildDetail(row) {{
  const list = (items, cls="") =>
    items.length
      ? `<ul class="detail-list ${{cls}}">${{items.map(i=>`<li>${{esc(i)}}</li>`).join("")}}</ul>`
      : `<span style="color:var(--text-dim);font-size:12px">—</span>`;

  return `
    <div class="detail-inner">
      <div class="detail-section">
        <h4>✅ Strengths</h4>
        ${{list(row.strengths, "green")}}
      </div>
      <div class="detail-section">
        <h4>⚠️ Gaps</h4>
        ${{list(row.gaps, "red")}}
      </div>
      <div class="detail-section">
        <h4>Must-Haves Met</h4>
        ${{list(row.must_met, "green")}}
      </div>
      <div class="detail-section">
        <h4>Must-Haves Missing</h4>
        ${{list(row.must_missing, "red")}}
      </div>
      <div class="detail-section">
        <h4>Technical Evidence</h4>
        ${{list(row.tech_evidence)}}
      </div>
      <div class="detail-section">
        <h4>Experience Evidence</h4>
        ${{list(row.exp_evidence)}}
      </div>
      ${{row.summary ? `<div class="summary-text">${{esc(row.summary)}}</div>` : ""}}
    </div>`;
}}

/* ── Applied toggle ───────────────────────────────────── */
function toggleApplied(id, checked) {{
  checked ? applied.add(id) : applied.delete(id);
  updateAppliedKPI();
  // Re-sort if sorting by applied
  if (sortCol === "applied") {{ sortData(); renderTable(); }}
}}

/* ── Filter & Sort ────────────────────────────────────── */
function applyFilters() {{
  const q   = document.getElementById("search").value.toLowerCase();
  const rec = document.getElementById("rec-filter").value;
  const sc  = document.getElementById("score-filter").value;
  const ap  = document.getElementById("applied-filter").value;

  filtered = RAW_DATA.filter(row => {{
    if (rec && row.recommendation !== rec) return false;

    if (sc !== "") {{
      const min = parseInt(sc);
      const max = min === 80 ? 100 : min === 60 ? 79 : min === 40 ? 59 : 39;
      if (row.overall_score < min || row.overall_score > max) return false;
    }}

    if (ap === "yes" && !applied.has(row.job_id)) return false;
    if (ap === "no"  &&  applied.has(row.job_id)) return false;

    if (q) {{
      const hay = [row.company, row.job_link, row.summary, row.recommendation,
                   ...row.strengths, ...row.gaps].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }}

    return true;
  }});

  sortData();
  renderTable();
}}

function sortBy(col) {{
  if (sortCol === col) {{
    sortDir *= -1;
  }} else {{
    sortCol = col;
    sortDir = (col === "company" || col === "job_link" || col === "recommendation") ? 1 : -1;
  }}
  sortData();
  renderTable();
}}

function sortData() {{
  filtered.sort((a, b) => {{
    // Special case: sort by applied checkbox state
    if (sortCol === "applied") {{
      const va = applied.has(a.job_id) ? 1 : 0;
      const vb = applied.has(b.job_id) ? 1 : 0;
      return (va - vb) * sortDir;
    }}
    const va = a[sortCol] ?? "";
    const vb = b[sortCol] ?? "";
    if (typeof va === "number") return (va - vb) * sortDir;
    return String(va).localeCompare(String(vb)) * sortDir;
  }});
}}

/* ── Expand ───────────────────────────────────────────── */
function toggleRow(event, id) {{
  if (event.target.closest("button") || event.target.closest(".applied-cell")) return;
  expanded.has(id) ? expanded.delete(id) : expanded.add(id);
  renderTable();
}}

/* ── Init ─────────────────────────────────────────────── */
applyFilters();
</script>
</body>
</html>"""
    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_job_report.py <input.json> [output.html]")
        sys.exit(1)

    input_file  = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else \
                  Path(input_file).stem + "_report.html"

    print(f"Reading: {input_file}")
    jobs = load_data(input_file)
    print(f"Found {len(jobs)} job(s)")

    html = generate_html(jobs, input_file)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written → {output_file}")


if __name__ == "__main__":
    main()