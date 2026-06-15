# Redrob — Intelligent Candidate Discovery & Ranking

> **Hackathon:** Redrob Intelligent Candidate Discovery & Ranking Challenge
> **Goal:** Read a job description, evaluate 100,000 candidate profiles, and output a ranked CSV of the top 100 best-fit candidates — CPU-only, fully offline, under 5 minutes.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [The Challenge & Dataset](#2-the-challenge--dataset)
3. [Project File Map](#3-project-file-map)
4. [How to Run Everything](#4-how-to-run-everything)
5. [System Architecture](#5-system-architecture)
6. [Code Files — Detailed Explanation](#6-code-files--detailed-explanation)
7. [Scoring Methodology](#7-scoring-methodology)
8. [Honeypot Detection Rules](#8-honeypot-detection-rules)
9. [Design Decisions (Interview Q&A)](#9-design-decisions-interview-qa)
10. [Compute Constraints Compliance](#10-compute-constraints-compliance)
11. [Output Format](#11-output-format)

---

## 1. What This Project Does

This is an AI-powered candidate ranking pipeline. Given:
- A **job description** (Senior AI Engineer at Redrob AI)
- **100,000 candidate profiles** (structured JSON with career history, skills, education, behavioral signals)

It produces a **ranked CSV of the top 100 candidates**, with a 1–2 sentence reasoning for each, in under 5 minutes on a standard CPU laptop.

The system combines three kinds of intelligence:
- **Semantic understanding** — sentence-transformer embeddings to understand what the JD *means*, not just what keywords it contains
- **Structured scoring** — rule-based evaluation of skills depth, career trajectory, education, and certifications
- **Behavioral signals** — 23 platform signals (last active date, response rate, notice period, GitHub activity, etc.) to assess whether a candidate is actually reachable and placeable

---

## 2. The Challenge & Dataset

### The Hackathon

The **Redrob Intelligent Candidate Discovery & Ranking Challenge** requires participants to:
1. Read a detailed job description (Senior AI Engineer, Redrob AI, Pune/Noida)
2. Rank 100,000 candidates from best to worst fit
3. Submit a CSV with the top 100 candidates: `candidate_id, rank, score, reasoning`
4. The ranking is scored against a hidden ground truth using `0.50×NDCG@10 + 0.30×NDCG@50 + 0.15×MAP + 0.05×P@10`

**Key trap in the JD:** The job description explicitly warns that keyword-matching is a trap. A candidate listing "RAG" and "Pinecone" as skills but whose title is "Marketing Manager" is NOT a fit. A candidate with a career history of building recommendation systems at product companies IS a fit — even without the buzzwords.

### Dataset Files

| File | Size | Description |
|------|------|-------------|
| `candidates.jsonl` | 465 MB | 100,000 candidate profiles, one JSON per line |
| `sample_candidates.json` | 293 KB | First 50 candidates — for fast development/testing |
| `candidate_schema.json` | 8.6 KB | JSON Schema (Draft-07) defining the candidate record structure |
| `job_description.docx` | 39 KB | The target JD: Senior AI Engineer — Founding Team |
| `redrob_signals_doc.docx` | 36 KB | Explains all 23 behavioral signals + honeypot patterns |
| `submission_spec.docx` | 42 KB | Full submission rules, scoring formula, evaluation stages |
| `sample_submission.csv` | 9 KB | Format reference (100 rows, not a quality ranking) |
| `submission_metadata_template.yaml` | 5 KB | Team metadata template for portal submission |
| `validate_submission.py` | 5 KB | Official validator — run this before submitting |

### Candidate Data Structure

Each of the 100,000 candidates is a JSON object with these top-level sections:

```
{
  "candidate_id": "CAND_0042871",   ← unique key, format CAND_XXXXXXX

  "profile": {                       ← basic identity
    "headline": "...",               ← one-line professional summary (free text)
    "summary": "...",                ← multi-sentence bio (richest semantic signal)
    "years_of_experience": 7.2,
    "current_title": "ML Engineer",
    "current_company": "...",
    "current_company_size": "501-1000",
    "current_industry": "Software",
    "location": "Bangalore", "country": "India"
  },

  "career_history": [ ... ],         ← 1–9 past/current roles with descriptions
  "education":      [ ... ],         ← 1–2 degrees with institution tier (tier_1–tier_4)
  "skills":         [ ... ],         ← list of {name, proficiency, duration_months, endorsements}
  "certifications": [ ... ],         ← optional, sparse (only 25% have any)
  "languages":      [ ... ],         ← language proficiencies

  "redrob_signals": { ... }          ← 23 platform behavioral signals (see Section 7)
}
```

### Key Dataset Facts (from our analysis)

- **133 unique skill names** — uniformly distributed (~12k candidates each). Simple skill presence is not informative; you must use depth signals.
- **75% have no certifications**, 76% have no skill assessment scores, 65% have no GitHub linked
- **~80 honeypot profiles** — subtly impossible (e.g., expert in 10 skills with 0 months use). Ranking any in top-100 at >10% rate = disqualification.
- **Countries:** India 75%, USA 10%, others 2–3% each
- **Industries:** IT Services 30%, Software 22%, Manufacturing 22%
- **Experience:** 1–17 years, mean 7.2

---

## 3. Project File Map

```
India_runs_data_and_ai_challenge/
│
├── 📄 DATASET (do not modify)
│   ├── candidates.jsonl              ← 100k profiles (main input)
│   ├── sample_candidates.json        ← 50-profile subset for dev
│   ├── candidate_schema.json         ← schema definition
│   ├── job_description.docx          ← the JD we're ranking against
│   ├── redrob_signals_doc.docx       ← behavioral signals reference
│   ├── submission_spec.docx          ← rules & scoring
│   ├── sample_submission.csv         ← format reference only
│   ├── submission_metadata_template.yaml
│   └── validate_submission.py        ← official format validator
│
├── 🐍 PIPELINE CODE
│   ├── config.py                     ← all constants & weights (tune here)
│   ├── data_loader.py                ← load data, parse JD, precompute aggregates
│   ├── honeypot_filter.py            ← detect impossible/trap profiles
│   ├── hard_gate.py                  ← experience, IT-services, coding-recency gates
│   ├── structured_scorer.py          ← skills, career, education, cert scoring
│   ├── behavioral_scorer.py          ← 23 platform signals
│   ├── semantic_scorer.py            ← MiniLM sentence-transformer similarity
│   ├── reasoning_generator.py        ← template-based reasoning strings
│   ├── final_ranker.py               ← orchestrates the two-stage funnel
│   ├── main.py                       ← CLI entry point (full 100k run)
│   └── test_on_sample.py             ← fast test on 50-candidate sample
│
├── 📦 SETUP
│   ├── requirements.txt              ← pinned Python dependencies
│   └── README.md                     ← this file
│
└── 📊 OUTPUT
    ├── submission.csv                ← your ranked top-100 (generated by main.py)
    ├── sample_submission.csv         ← test output (generated by test_on_sample.py)
    └── dataset_analysis.md           ← full data exploration report
```

---

## 4. How to Run Everything

### Prerequisites

- Python 3.11+
- 16 GB RAM (pipeline uses ~2–3 GB peak)
- CPU only — no GPU needed or used

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Download the embedding model (once, needs internet)

```bash
python semantic_scorer.py
```

This downloads `all-MiniLM-L6-v2` (~80 MB) to your local HuggingFace cache. All subsequent runs are **fully offline**.

### Step 3 — Test on the 50-candidate sample

```bash
python test_on_sample.py
```

Fast iteration mode (~9 seconds). Runs the full pipeline on `sample_candidates.json` and prints ranked output to console. Produces `sample_submission.csv`. Use this after any code change before running on the full dataset.

To skip semantic scoring for even faster tests:
```bash
python test_on_sample.py --no-semantic
```

### Step 4 — Full run on 100,000 candidates

```bash
python main.py
```

Produces `submission.csv` in ~75 seconds. Prints timing breakdown per stage, pre-screen cutoff score, honeypot stats, and first 10 ranked rows.

**Options:**
```bash
python main.py --candidates candidates.jsonl   # explicit file path
python main.py --output my_team.csv           # custom output name
python main.py --no-semantic                  # skip semantic (faster, lower quality)
python main.py --prescreen-cutoff 5000        # override from config
```

### Step 5 — Validate before submitting

```bash
python validate_submission.py submission.csv
```

This is the **official validator** from the hackathon bundle. Fix any issues it reports before uploading.

### Single reproduce command (Stage 3 verification)

```bash
python main.py --candidates candidates.jsonl --output submission.csv
```

---

## 5. System Architecture

### The Core Problem with Naive Approaches

**Why not just do keyword matching?** The JD explicitly warns: "find candidates whose skills section contains the most AI keywords — that's a trap." With 133 skill names uniformly distributed across 100k candidates (each skill appears ~12k times), keyword presence tells you almost nothing.

**Why not embed all 100k with a transformer?** `all-MiniLM-L6-v2` on CPU processes ~400 tokens/second. 100k candidates × 300 tokens average = ~300s just for embedding — the entire 5-minute budget gone before any scoring.

### The Two-Stage Funnel

```
100,000 candidates
       │
       ▼  ══════════════ STAGE 1: Fast Pre-Screen (~50s) ══════════════
       │
       ├─ honeypot_filter.py  ──→  Exclude ~80 impossible profiles (rules H1–H6)
       │
       ├─ hard_gate.py        ──→  gate_score = gate_exp × gate_career × gate_recency
       │                           (experience Gaussian × IT-services penalty × coding-recency)
       │
       ├─ structured_scorer.py ─→  structured_score: skills + career + edu + certs
       │
       ├─ behavioral_scorer.py ─→  behavioral_score: 23 platform signals
       │
       └─ pre_screen_score = gate × (0.40×struct + 0.15×beh + 0.10×assess)
              │
              ▼  Top 3,000 selected by pre_screen_score
       │
       ▼  ══════════════ STAGE 2: Semantic Re-Rank (~15s) ══════════════
       │
       ├─ semantic_scorer.py  ──→  MiniLM cosine similarity (JD text ↔ candidate text)
       │                           (only 3,000 candidates embedded, not 100k)
       │
       └─ final_score = gate × (0.40×struct + 0.35×sem + 0.15×beh + 0.10×assess)
              │
              ▼  Top 150 candidates
       │
       ▼  ══════════════ STAGE 3: Output (~1s) ══════════════
       │
       ├─ reasoning_generator.py → 1–2 sentence reasoning per candidate
       │
       └─ submission.csv (top 100, ranked 1–100)
```

**Total: ~75 seconds.** 4× headroom under the 5-minute budget.

---

## 6. Code Files — Detailed Explanation

---

### `config.py` — Central Configuration

**What it does:** Single source of truth for every constant, weight, threshold, and list used across the pipeline. Tune weights here between runs without touching any scoring code.

**Key contents:**

| Section | What's defined |
|---------|---------------|
| Pipeline topology | `PRESCREEN_CUTOFF=3000`, `REASONING_POOL=150`, `TOP_N=100` |
| Honeypot thresholds | H1–H6 rule thresholds (e.g., `HONEYPOT_EXPERT_COUNT_THRESHOLD=8`) |
| Gate multipliers | `IT_SERVICES_FULL_PENALTY=0.25`, experience Gaussian params |
| Final score weights | `WEIGHT_STRUCTURED=0.40`, `WEIGHT_SEMANTIC=0.35`, etc. |
| Structured sub-weights | `STRUCT_WEIGHT_SKILLS=0.40`, `STRUCT_WEIGHT_CAREER=0.30`, etc. |
| Behavioral sub-weights | per-signal weights for all 23 signals |
| JD skill lists | `REQUIRED_SKILLS` and `PREFERRED_SKILLS` dicts with relevance scores (0–1) |
| IT services firm list | 20+ known IT services firm name patterns |
| Education tier scores | `EDU_TIER_SCORE = {tier_1: 1.0, tier_2: 0.75, ...}` |
| Cert relevance scores | DeepLearning.AI=0.90, Google Cloud=0.75, AWS=0.70, Scrum=0.25 |
| Breakpoint tables | `NOTICE_PERIOD_SCORES` and `RECENCY_DECAY` for interpolation |

---

### `data_loader.py` — Data Loading & Preprocessing

**What it does:** Loads all input data and precomputes per-candidate aggregates that are reused across all scoring modules (so nothing is computed twice).

**Key functions:**

| Function | Description |
|----------|-------------|
| `load_candidates(path)` | Stream-reads `.jsonl` or `.jsonl.gz`, injects `_meta` dict per candidate |
| `load_candidates_from_json(path)` | Loads the 50-candidate `sample_candidates.json` array |
| `_precompute_meta(candidate)` | Runs once per candidate; computes all derived values (see below) |
| `load_job_description(path)` | Parses `job_description.docx`, extracts structured fields + embedding text |
| `build_candidate_text(candidate)` | Assembles headline + summary + career descriptions for embedding |

**What `_meta` contains (precomputed once per candidate):**
- `total_career_months` — sum of all `career_history[].duration_months`
- `skill_names` — set of skill names (fast O(1) lookup)
- `skill_map` — dict of skill name → skill object
- `expert_skill_count` — count of skills with `proficiency == "expert"`
- `all_career_text` — concatenated lowercase career descriptions (for keyword scanning)
- `career_companies` — lowercase company names (for IT-services matching)
- `current_role_desc` / `current_role_title` — most recent role (for G4 gate)
- `career_date_ranges` — parsed date pairs for overlap detection (H5)
- `best_edu_score`, `best_degree_bonus` — precomputed education signals
- `relevant_assessments` — filtered `skill_assessment_scores` for JD-relevant topics

---

### `honeypot_filter.py` — Trap Profile Detection

**What it does:** Detects candidates with internally inconsistent or impossible profiles before they enter the scoring pipeline. All ~80 honeypots documented in the spec are targeted by at least one rule.

**Six independent rules — any one fires = honeypot:**

| Rule | Condition | Example Catch |
|------|-----------|---------------|
| **H1** | Any `proficiency=="expert"` with `duration_months==0` | "Expert Python, 0 months used" |
| **H2** | `claimed_years > career_years × 1.6 + 2.0` | "13.7yr claimed, 0.9yr career history" |
| **H3** | `count(expert skills) >= 8` | "11 skills all rated expert" |
| **H4** | Any `skill.duration_months > max(career_months, claimed_exp_months) + 36` | "Kubeflow: 200 months, career: 12 months" |
| **H5** | Two non-current roles overlap by > 3 months | "Two full-time jobs simultaneously for 8 months" |
| **H6** | Future `end_date` on non-current role, or graduated in the future with high experience | "Ended job in 2029; graduated 2028 but claims 10yr exp" |

**Key functions:**

| Function | Returns |
|----------|---------|
| `check_honeypot(candidate)` | `HoneypotResult(is_honeypot, flags, reasons)` |
| `filter_honeypots(candidates)` | `(clean_candidates, honeypot_results_dict)` |
| `honeypot_summary(results)` | Stats dict: total, flagged count, per-rule counts |

---

### `hard_gate.py` — Hard Requirement Gates

**What it does:** Computes `gate_score ∈ [0, 1]` per candidate, applied as a **multiplicative penalty** on the final score. A candidate who fails all gates gets score ~ 0.01 (not zero — they don't disappear, they just rank extremely low).

```
gate_score = gate_exp × gate_career × gate_recency
```

**Three gate components:**

**G1 — Experience Gaussian (`gate_exp`):**
```
gate_exp = exp(−0.5 × ((years_exp − 7.0) / 2.5)²)
gate_exp = max(0.20, gate_exp)   # floor: nobody gets zeroed on experience alone
```
JD prefers 5–9 years (ideal 6–8). The Gaussian peaks at 7yr, σ=2.5. At 5yr or 9yr → 0.78. At 2yr or 14yr → 0.27. Floor at 0.20.

**G3 — IT Services Career Penalty (`gate_career`):**
```
it_fraction = (months at IT services firms) / total_career_months

if it_fraction == 1.0:  → 0.25×   (entire career at TCS/Infosys/Wipro/etc.)
if it_fraction >= 0.75: → 0.50×
if it_fraction >= 0.50: → 0.75×
else:                   → 1.00×   (mostly product companies — no penalty)
```
The JD explicitly says: "People who have only worked at consulting firms in their entire career — we've had bad fit experiences." The 20-firm list is in `config.IT_SERVICES_FIRMS`.

**G4 — Coding Recency (`gate_recency`):**
Checks whether the candidate's current/most-recent role shows hands-on coding evidence. JD says "hasn't written production code in 18 months → not a fit."
- Coding keywords in description (`implemented`, `built`, `deployed`, etc.) → 1.00
- Pure managerial keywords only (`stakeholder`, `roadmap`, `OKR`, `P&L`) → 0.60
- Ambiguous → 0.85

---

### `structured_scorer.py` — Rule-Based Profile Scoring

**What it does:** Produces `structured_score ∈ [0, 1]` using explicit JD matching logic. This is the **primary pre-screen signal** — all 100k candidates go through this. It is also Stage 1 of the two-stage funnel.

**Five components (weighted sum):**

| Component | Weight | How it works |
|-----------|--------|--------------|
| **Skills match** | 40% | For each JD-relevant skill in candidate's profile: `proficiency_weight × duration_weight × jd_relevance`. Normalized against theoretical max. Python absence caps score at 0.40. |
| **Career trajectory** | 30% | (a) Title relevance: ML Engineer=1.0, Data Scientist=0.85, Backend Eng=0.55, Manager=0.20, etc. Weighted by recency. (b) ML keyword density in career descriptions: `embedding`, `retrieval`, `RAG`, `ranking`, `NDCG`, etc. |
| **Experience curve** | 20% | Same Gaussian as G1 — used as a positive signal here (not a penalty). |
| **Education tier** | 6% | `best_edu_score × best_degree_bonus`. PhD gets 1.2× bonus, M.Tech 1.1×, MBA 0.9×. |
| **Certifications** | 4% | Positive-only bonus. DeepLearning.AI / Google Cloud certs → 0.75–0.90. Scrum → 0.25. No certs → 0.0 (no penalty). |

**Skills scoring detail:**
```python
contribution = jd_relevance × proficiency_weight × duration_weight × (1 + endorsement_boost)
# proficiency:  beginner=0.25, intermediate=0.50, advanced=0.85, expert=1.00
# duration_weight = min(duration_months / 48, 1.0)   # capped at 4 years
# endorsement_boost = min(endorsements / 50, 0.10)   # max +10%
```

---

### `behavioral_scorer.py` — Platform Signal Scoring

**What it does:** Scores candidate availability and engagement using the 23 `redrob_signals` fields. This is a **modifier on top of fit** — it answers "is this candidate actually reachable and placeable right now?" not "are they technically qualified?"

**Weight=0.15 in final score — intentionally smaller than structured (0.40) and semantic (0.35).**

**Signal handling policy:**

| Value | Meaning | Handling |
|-------|---------|----------|
| `github_activity_score = -1` | No GitHub linked | → 0.30 (slight negative — absence of code trail is mildly concerning for AI Engineer) |
| `offer_acceptance_rate = -1` | No offer history | → 0.50 (neutral — no signal) |
| Any `None` / missing field | Unknown | → 0.50 (neutral — never penalized) |

**All 7 behavioral sub-scores:**

| Signal | Weight | Score mapping |
|--------|--------|---------------|
| `open_to_work_flag` | 20% | True → 1.0; False → 0.40 (passive candidates still viable) |
| `last_active_date` recency | 20% | Linear decay: ≤30d→1.0, 90d→0.60, 180d→0.30, 365d→0.10 |
| `recruiter_response_rate` | 20% | Direct [0, 1]; missing → 0.50 |
| `notice_period_days` | 15% | 0–30d→1.0, 60d→0.80, 90d→0.60, 120d→0.40, 150d→0.25 |
| `interview_completion_rate` | 10% | Direct [0, 1]; missing → 0.50 |
| `github_activity_score` | 10% | -1→0.30; 0–100 → normalized to [0, 1] |
| verified email + phone | 5% | Both → 1.0; one → 0.70; neither → 0.40 |

Also computes `assessment_boost` separately (used as its own 0.10 weight in final score): mean of `skill_assessment_scores` for JD-relevant skills, normalized to [0, 1]. Missing → 0.50 neutral.

---

### `semantic_scorer.py` — Sentence-Transformer Similarity

**What it does:** Embeds the JD text and candidate texts using `all-MiniLM-L6-v2` and computes cosine similarity. Applied **only to the top 3,000 candidates** from the pre-screen.

**Why this model?**
- 80 MB on disk — lightweight enough for offline use
- Max sequence length 384 tokens — fits career descriptions cleanly
- Strong performance on English professional text
- CPU inference speed: ~30–50 candidates/second (3,000 in ~15s)

**How candidate text is built for embedding:**
```
[headline] + [professional summary] + [Role: title. description] × each job + [Skills: skill1, skill2, ...]
```

**JD text used for embedding:**
```
Role: Senior AI Engineer at Redrob AI
Experience: 5-9 years
Required: [required skills section text]
Preferred: [preferred skills section text]
[responsibilities section excerpt]
```

**Cosine similarity:** Since embeddings are L2-normalized, similarity = dot product. Results clipped to [0, 1] (negative similarity is meaningless here).

**Offline operation:** Run `python semantic_scorer.py` once with internet. The model is cached at `~/.cache/huggingface`. Ranking runs with no network calls at all.

---

### `reasoning_generator.py` — Reasoning String Generation

**What it does:** Generates a 1–2 sentence reasoning string per candidate that:
- References **actual scored facts** (never hallucinated skills or experience)
- Connects to JD requirements
- **Varies phrasing** across 100 rows (avoids robotic repetition that gets penalized at Stage 4)
- Acknowledges concerns where they exist (high notice period, inactive account, IT-services background)

**Approach:** Pure template-based string construction using the scored attributes. No LLM API calls (spec prohibits network access during ranking).

**Template pools used:**
- 5 opener variants: `"{title} with {years} years..."`, `"{years}-year {title}"`, `"Strong {title} ({years}yrs)"`, etc.
- 5 skill phrase variants: `"matched on {skills}"`, `"strong in {skills}"`, `"brings {skills} expertise"`, etc.
- 5 career-positive phrases, 3 career-generic phrases
- 5 behavioral-positive phrases, 3 behavioral-neutral phrases
- Concern phrases for: long notice period, platform inactivity, IT-services background
- GitHub activity phrases, assessment confirmation phrases, education tier phrases

**Seed for reproducibility:** Each candidate's numeric ID is used as the random seed, so the same candidate always gets the same reasoning variant. Output is fully deterministic.

**Hallucination prevention:** Every fact referenced in the reasoning is pulled directly from:
- `structured.top_matched_skills` → actual skills from the candidate's profile
- `profile.years_of_experience`, `profile.current_title` → direct profile fields
- `behavioral.notice_days`, `behavioral.days_since_active` → from `redrob_signals`
- `gate.it_fraction` → computed from `career_history.company`

---

### `final_ranker.py` — Pipeline Orchestration

**What it does:** Orchestrates the complete two-stage ranking funnel and writes the output CSV.

**Function `run_ranking_pipeline(candidates, jd_data, semantic_model)`:**

Steps in order:
1. `filter_honeypots()` — removes honeypots from full pool
2. `score_structured_batch()` — structured scores for all clean candidates
3. `score_behavioral_batch()` + `compute_assessment_boost()` — behavioral scores for all
4. `score_gates_batch()` — gate multipliers for all
5. Compute `pre_screen_score` = `gate × (0.40×struct + 0.15×beh + 0.10×assess)` for all; select top 3,000
6. `score_semantic_batch()` — embed top 3,000 only
7. Compute `final_score = gate × (0.40×struct + 0.35×sem + 0.15×beh + 0.10×assess)` for top 3,000
8. Honeypot rate safety check (warn at 5%, error at 10%)
9. Select clean top-150 for reasoning generation
10. `generate_reasoning_batch()` — template reasoning for top 150

**Function `write_submission_csv(top_records, reasoning_map, output_path)`:**
- Normalizes final scores to [0.20, 0.99] range while preserving rank order
- Enforces non-increasing score constraint (per spec)
- Writes UTF-8 CSV with columns: `candidate_id, rank, score, reasoning`

---

### `main.py` — CLI Entry Point

**What it does:** Full pipeline end-to-end with timing instrumentation per stage, summary stats, and a first-10-rows preview.

**Printed summary includes:**
- Total candidates processed, honeypots found (count + % + rule breakdown)
- Pre-screen cutoff score and top score (tells you if PRESCREEN_CUTOFF needs adjusting)
- Honeypot rate in top-100 pre-exclusion (must stay under 10%)
- Final #1 and #100 scores (score spread health check)
- Per-stage timing (honeypot, structured, behavioral, gate, prescreen, semantic, final, reasoning)
- Total wall time vs 5-minute budget

**CLI options:**
```
--candidates <path>       # override input file (auto-detects .jsonl / .jsonl.gz)
--output <path>           # override output CSV path
--no-semantic             # skip embedding (faster, lower quality, useful for debugging)
--prescreen-cutoff <N>    # override PRESCREEN_CUTOFF from config.py
```

---

### `test_on_sample.py` — Development Test Runner

**What it does:** Runs the full pipeline on `sample_candidates.json` (50 candidates) in ~9 seconds. Use this after every code change before committing.

**Output:**
- Full ranked table with all component scores (Final, Struct, Sem, Beh, Gate, HP flag)
- Honeypot details for any flagged candidates
- Validation result (row-count errors expected in sample mode — noted)
- Total wall time

---

### `validate_submission.py` — Official Format Validator (provided by hackathon)

**What it does:** Validates the submission CSV against all spec rules. Run this before uploading.

**Checks:**
- Exactly 100 data rows (plus header)
- All 4 required columns in correct order: `candidate_id, rank, score, reasoning`
- Every `candidate_id` matches `CAND_XXXXXXX` format
- Every `candidate_id` is unique
- Ranks 1–100 each appear exactly once
- Scores are non-increasing (rank 1 ≥ rank 2 ≥ ... ≥ rank 100)
- Score ties broken by `candidate_id` ascending
- UTF-8 encoding

---

## 7. Scoring Methodology

### Final Score Formula

```
final_score = gate_score × (
    0.40 × structured_score      ← deep profile match: skills + career + edu
  + 0.35 × semantic_score        ← JD–profile semantic similarity
  + 0.15 × behavioral_score      ← is this person reachable and available?
  + 0.10 × assessment_boost      ← verified platform skill tests (sparse but trusted)
)
```

`gate_score` is applied **multiplicatively**, not additively. It compresses the entire score for candidates who fail hard requirements, without zeroing them completely.

### Weight Rationale

| Component | Weight | Why |
|-----------|--------|-----|
| Structured | 40% | Career evidence is the most reliable signal. Skills × proficiency × duration is richer than keyword presence. |
| Semantic | 35% | Captures what the JD *means* (not keywords). But not too high — pure embedding rewards keyword-stuffers. |
| Behavioral | 15% | Critical for *reachability*, but a perfect candidate who's inactive isn't hired. Secondary signal. |
| Assessment | 10% | Objective platform-verified scores. Sparse (24% have any), but highly trusted when present. |

---

## 8. Honeypot Detection Rules

The spec documents ~80 "honeypot" candidates with subtly impossible profiles. Ranking more than 10% of them in the top-100 = **disqualification**. Our system excludes all honeypots before the final selection.

| Rule | What it catches | Why |
|------|-----------------|-----|
| H1: Expert + zero duration | `proficiency=expert` with `duration_months=0` | "Expert" at something you've never used is impossible |
| H2: Experience math mismatch | Claimed years ≫ sum of career history months | "13.7yr claimed but 11 months of career history total" |
| H3: Expert inflation | ≥8 skills rated "expert" | Expert = 0.1% of all skills in dataset; 8+ is statistically impossible |
| H4: Skill duration > career | Skill used longer than entire career (+ 36mo buffer) | Can't have 10yr of Kubernetes experience in a 2yr career |
| H5: Full-time role overlap | Two non-current jobs overlap > 3 months | Impossible to work two full-time jobs for 8 months |
| H6: Future dates | End-date in future on past job; graduated in the future | "Graduated 2028, claims 10yr experience as of 2026" |

---

## 9. Design Decisions (Interview Q&A)

**Q: Why a two-stage funnel instead of embedding all 100k?**

MiniLM on CPU processes ~35 candidates/second for 300-token texts. 100k / 35 = ~2,857 seconds = 47 minutes. That's 9× over the 5-minute budget. Structured pre-screening in NumPy takes 15 seconds for 100k candidates. We lose nothing meaningful: a candidate with 1yr experience in manufacturing and no Python is never in the top 100 regardless of semantic score.

**Q: Why is semantic weight only 0.35, not higher?**

The JD explicitly warns this is a trap. All 133 skills appear uniformly across the 100k pool — skill presence alone is meaningless. Pure embedding similarity rewards candidates who've stuffed "RAG" and "LLM" into their summary without any real evidence of production ML work. We want career evidence (structured score) to dominate, with semantic as a precision layer for distinguishing between similarly-structured candidates.

**Q: Why not hard-drop all IT-services candidates?**

The JD says candidates who worked at IT-services firms but also have product-company experience are fine. Hard drops create false positives. A 0.25× gate multiplier demotes them to the bottom of rankings without eliminating genuine candidates who may have done real ML work at a product company before joining TCS.

**Q: How do you handle -1 sentinel values without silently scoring them as zero?**

- `github_activity_score = -1` → score 0.30 (slightly below neutral 0.50; no GitHub trail is mildly concerning for an AI Engineer role)
- `offer_acceptance_rate = -1` → 0.50 neutral (no history = no information)
- Any missing field → 0.50 neutral (unknown ≠ bad)

The behavioral scorer never maps any absent signal to 0. This was a deliberate policy to prevent punishing candidates who simply haven't filled in optional platform fields.

**Q: How does the reasoning avoid hallucination?**

Every sentence is built from scored attributes that are themselves derived from the candidate's actual data:
- Skills mentioned = `structured.top_matched_skills` ← from actual `candidate.skills[]`
- Experience years = `profile.years_of_experience` ← direct field
- Notice period = `behavioral.notice_days` ← from `redrob_signals.notice_period_days`
- GitHub claim = `behavioral.has_github` ← `github_activity_score != -1`

No free text generation, no LLM, no inference beyond the data. Stage 4 reviewers can cross-check every claim against the raw candidate record.

**Q: How do you know the honeypot rate will stay under 10%?**

Honeypots are excluded **before** the pre-screen selection. The scoring pipeline never ranks them — they're zeroed out first. We additionally compute the rate in the "pre-exclusion" top-100 (i.e., if we had not excluded them) as a diagnostic. If that rate exceeds 5%, we print a warning. If it exceeds 10%, the pipeline raises a hard error before writing any output.

---

## 10. Compute Constraints Compliance

| Constraint | Limit | This Pipeline |
|-----------|-------|---------------|
| Total runtime | ≤ 5 minutes | ~75 seconds |
| RAM | ≤ 16 GB | ~2–3 GB peak |
| Compute | CPU only, no GPU | ✓ `device="cpu"` enforced |
| Network | Off during ranking | ✓ model cached offline at download step |
| Disk intermediate state | ≤ 5 GB | < 1 GB (MiniLM cache ~80 MB) |

### Timing Breakdown (100k candidates)

| Stage | Time |
|-------|------|
| Data loading (JSONL parse + `_meta` precompute) | ~8s |
| Honeypot filter (6 rules, 100k candidates) | ~15s |
| Structured scoring (100k) | ~20s |
| Behavioral scoring (100k) | ~5s |
| Gate scoring (100k) | ~10s |
| Pre-screen selection (top 3,000) | ~1s |
| Semantic embedding (3,000 candidates) | ~10–15s |
| Final scoring + reasoning generation | ~2s |
| **Total** | **~75s** |

---

## 11. Output Format

The output `submission.csv` must match this exact spec:

```csv
candidate_id,rank,score,reasoning
CAND_0042871,1,0.9900,"ML Engineer with 7 years; strong in Python, NLP, Elasticsearch; career shows production retrieval work at product companies. Open to work, 15-day notice period, GitHub score 72/100."
CAND_0019884,2,0.9823,"Applied Scientist (6 yrs); brings PyTorch, NLP, AWS expertise; track record of applied ML in production environments. High recruiter response rate."
...
CAND_0007729,100,0.2000,"Adjacent technical skills only; career history shows technical engineering work. Moderate engagement signals."
```

**Rules (enforced by `validate_submission.py`):**
- Exactly 100 data rows + 1 header row
- `rank` integers 1–100, each appearing exactly once
- `score` floats, non-increasing with rank
- Score ties broken by `candidate_id` ascending
- All `candidate_id` values must exist in `candidates.jsonl`
- UTF-8 encoding, `.csv` extension

**Evaluation scoring formula:**
```
Final = 0.50 × NDCG@10 + 0.30 × NDCG@50 + 0.15 × MAP + 0.05 × P@10
```

NDCG@10 has the highest weight (50%) — precision in the top 10 matters most.
