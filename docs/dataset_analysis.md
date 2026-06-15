# Dataset Analysis Report
## Redrob — Intelligent Candidate Discovery & Ranking Challenge
**Generated:** 2026-06-14 | **Analyst:** AI-assisted read-only exploration

---

## 1. File Inventory

| File | Format | Size | Purpose |
|------|--------|------|---------|
| `candidates.jsonl` | JSONL (newline-delimited JSON) | 464.7 MB | **Main dataset** — 100,000 candidate profiles |
| `sample_candidates.json` | JSON (array) | 293 KB | 50-candidate preview subset |
| `candidate_schema.json` | JSON Schema (Draft-07) | 8.6 KB | Schema definition for a single candidate record |
| `job_description.docx` | DOCX | 39.3 KB | The target JD: Senior AI Engineer — Founding Team |
| `sample_submission.csv` | CSV | 9.0 KB | Format reference — 100 ranked candidates |
| `submission_metadata_template.yaml` | YAML | 5.1 KB | Team metadata template for portal submission |
| `submission_spec.docx` | DOCX | 41.7 KB | Full rules, scoring, evaluation pipeline |
| `redrob_signals_doc.docx` | DOCX | 36.3 KB | Explanation of the 23 behavioral signal fields |
| `README.docx` | DOCX | 9.9 KB | Quick-start guide for participants |
| `validate_submission.py` | Python | 4.9 KB | Local validator script before submission |

---

## 2. File-by-File Breakdown

### 2.1 `candidates.jsonl` — Main Candidate Pool

**Format:** One JSON object per line | **Records:** 100,000 | **No header row**

#### Top-Level Schema

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `candidate_id` | string | Unique ID, format `CAND_XXXXXXX` (7 digits) | Yes |
| `profile` | object | Core professional profile | Yes |
| `career_history` | array (1–10 items) | Past & current roles | Yes |
| `education` | array (0–5 items) | Degrees and institutions | Yes |
| `skills` | array | Skills with proficiency + endorsements | Yes |
| `certifications` | array | Professional certifications | No |
| `languages` | array | Language proficiencies | No |
| `redrob_signals` | object | 23 behavioral/platform signals | Yes |

#### `profile` Sub-Fields

| Field | Type | Notes |
|-------|------|-------|
| `anonymized_name` | string | Pseudonymized name |
| `headline` | string | One-line professional headline (free text) |
| `summary` | string | Multi-sentence bio (free text, longest field) |
| `location` | string | City / Region |
| `country` | string | Country name |
| `years_of_experience` | float | Range: 1.0 – 16.9, mean 7.17 |
| `current_title` | string | Current job title |
| `current_company` | string | Current employer |
| `current_company_size` | enum | 8 buckets: "1-10" to "10001+" |
| `current_industry` | string | Industry category |

#### `career_history` Item Fields

| Field | Type | Notes |
|-------|------|-------|
| `company` | string | Employer name |
| `title` | string | Role title |
| `start_date` | date string | ISO 8601 (`YYYY-MM-DD`) |
| `end_date` | date string or null | null if current role |
| `duration_months` | integer | Pre-computed months in role |
| `is_current` | boolean | True for current role |
| `industry` | string | Industry for this role |
| `company_size` | enum | Same 8 buckets as profile |
| `description` | string | Role responsibilities (free text, richest signal) |

#### `education` Item Fields

| Field | Type | Notes |
|-------|------|-------|
| `institution` | string | University/college name |
| `degree` | string | e.g. B.Tech, M.S., Ph.D |
| `field_of_study` | string | e.g. Computer Science |
| `start_year` | integer | 1970–2030 |
| `end_year` | integer | 1970–2035 |
| `grade` | string or null | GPA/percentage/class — optional |
| `tier` | enum | `tier_1` to `tier_4` or `unknown` — institution prestige |

#### `skills` Item Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Skill name (133 unique values in dataset) |
| `proficiency` | enum | `beginner`, `intermediate`, `advanced`, `expert` |
| `endorsements` | integer | Peer endorsement count |
| `duration_months` | integer | Months of use |

#### `redrob_signals` Fields (All 23)

| Field | Type | Range / Values | What it signals |
|-------|------|----------------|-----------------|
| `profile_completeness_score` | float | 25–99.9 (mean 56.8) | Profile fill quality |
| `signup_date` | date | — | Platform tenure |
| `last_active_date` | date | — | Recency of engagement |
| `open_to_work_flag` | boolean | 35.3% true | Actively job-seeking |
| `profile_views_received_30d` | integer | — | Recruiter interest |
| `applications_submitted_30d` | integer | — | Job-seeking intensity |
| `recruiter_response_rate` | float | 0–1 | Responsiveness |
| `avg_response_time_hours` | float | — | Speed of response |
| `skill_assessment_scores` | dict | skill → 0–100 | Verified skill scores |
| `connection_count` | integer | — | Network size |
| `endorsements_received` | integer | — | Social proof |
| `notice_period_days` | integer | 0–150 (mean 87) | Time-to-start |
| `expected_salary_range_inr_lpa` | object {min, max} | 3–74.5 LPA | Salary expectations |
| `preferred_work_mode` | enum | remote/hybrid/onsite/flexible (~25% each) | Location flexibility |
| `willing_to_relocate` | boolean | 28.8% true | Mobility |
| `github_activity_score` | float | -1 (no GitHub) or 0–96.9 | Coding activity |
| `search_appearance_30d` | integer | — | Recruiter discovery rate |
| `saved_by_recruiters_30d` | integer | — | Shortlisting frequency |
| `interview_completion_rate` | float | 0–1 | Reliability in process |
| `offer_acceptance_rate` | float | -1 (no history) or 0–1 | Historical intent |
| `verified_email` | boolean | 72.0% true | Contact reliability |
| `verified_phone` | boolean | 61.8% true | Contact reliability |
| `linkedin_connected` | boolean | 36.0% true | External profile link |

#### Sample Record (First Candidate — CAND_0000001)

```json
{
  "candidate_id": "CAND_0000001",
  "profile": {
    "anonymized_name": "Ira Vora",
    "headline": "Backend Engineer | SQL, Spark, Cloud",
    "summary": "Software / data professional with 6.9 years ... Interested in transitioning toward more AI/ML-focused work...",
    "location": "Toronto", "country": "Canada",
    "years_of_experience": 6.9,
    "current_title": "Backend Engineer",
    "current_company": "Mindtree",
    "current_company_size": "10001+",
    "current_industry": "IT Services"
  },
  "career_history": [{"company": "Mindtree", "title": "Backend Engineer", "start_date": "2024-03-08", "end_date": null, "duration_months": 27, "is_current": true, ...}],
  "education": [{"institution": "Lovely Professional University", "degree": "B.E.", "field_of_study": "Computer Science", "tier": "tier_3", "grade": "8.24 CGPA"}],
  "skills": [{"name": "Tailwind", "proficiency": "intermediate", "endorsements": 3, "duration_months": 13}, ...17 total],
  "redrob_signals": {
    "profile_completeness_score": 86.9,
    "open_to_work_flag": true,
    "recruiter_response_rate": 0.34,
    "github_activity_score": 9.2,
    "skill_assessment_scores": {"NLP": 38.8, "Image Classification": 64.8, "Fine-tuning LLMs": 41.6, ...},
    ...
  }
}
```

#### Missing Value Summary

No structural missing values were found — all `required` schema fields are present. Optional fields have expected absences:

| Field / Condition | Count | % of 100,000 |
|-------------------|-------|--------------|
| `certifications` (empty array) | ~75,019 | ~75.0% |
| `skill_assessment_scores` (empty dict) | ~75,756 | ~75.8% |
| `github_activity_score == -1` (no GitHub linked) | 64,637 | 64.6% |
| `offer_acceptance_rate == -1` (no offer history) | 59,554 | 59.6% |
| `education.grade` (nullable per schema) | partial | — |

> **Note:** `-1` sentinel values for `github_activity_score` and `offer_acceptance_rate` are intentional design choices documented in the schema, not true missing values. Handle them as a separate category during feature engineering.

#### Unique Value Counts for Key Categorical Fields

| Field | Unique Values |
|-------|---------------|
| Skills (`name`) | **133** |
| `current_industry` | ~20+ categories |
| `preferred_work_mode` | 4 (remote, hybrid, onsite, flexible) |
| `education.tier` | 5 (tier_1 – tier_4, unknown) |
| `skills.proficiency` | 4 (beginner, intermediate, advanced, expert) |
| `career_history.company_size` | 8 buckets |
| Certification issuers | 6 (AWS, ASQ, Scrum Alliance, Coursera/DeepLearning.AI, Google Cloud, DeepLearning.AI) |
| Countries | 8 (India 75.1%, USA 10.0%, Australia 2.6%, Canada 2.5%, UK 2.5%, Germany 2.5%, Singapore 2.5%, UAE 2.4%) |

#### Distribution Summaries

| Metric | Min | Max | Mean | Median |
|--------|-----|-----|------|--------|
| Years of experience | 1.0 | 16.9 | 7.17 | 6.80 |
| Profile completeness score | 25.0 | 99.9 | 56.8 | 56.8 |
| GitHub activity score (excluding -1) | 0.0 | 96.9 | 9.6 | — |
| Notice period (days) | 0 | 150 | 87.4 | 90 |
| Salary min (LPA) | 3.0 | 49.7 | 12.2 | 11.9 |
| Salary max (LPA) | 6.0 | 74.5 | 19.8 | 19.4 |
| Skills per candidate | 5 | 23 | 9.6 | 9 |
| Career history entries | 1 | 9 | 3.0 | 3 |
| Education entries | 1 | 2 | 1.4 | 1 |
| Certs per candidate | 0 | 3 | 0.37 | 0 |
| Skill assessment scores count | 0 | 5 | 0.36 | 0 |

#### Skill Proficiency Distribution (across all skill records)

| Proficiency | Count | % |
|-------------|-------|---|
| intermediate | 470,309 | 49.2% |
| beginner | 379,097 | 39.7% |
| advanced | 109,585 | 11.5% |
| expert | 1,311 | 0.1% |

#### Education Tier Distribution

| Tier | Count |
|------|-------|
| tier_3 | 53,220 |
| tier_4 | 51,885 |
| tier_2 | 27,821 |
| tier_1 | 6,852 |

#### Top 30 Most Common Skills

HTML, Databricks, Redux, Terraform, Angular, Figma, Salesforce CRM, Vue.js, Sales, Accounting, Agile, Kafka, Excel, BigQuery, CI/CD, Project Management, Airflow, AWS, Flask, Scrum, Illustrator, Kubernetes, ETL, CSS, Docker, Next.js, Apache Beam, Java, Go, TypeScript

> **Key observation:** Skills appear very uniformly distributed (~12,000 candidates each for the top skills). This likely reflects synthetic data generation, and means simple skill-keyword counting will not differentiate candidates well. You must use depth/proficiency/duration signals alongside mere presence.

---

### 2.2 `sample_candidates.json`

- **Format:** JSON array of 50 candidate objects
- **Schema:** Identical to `candidates.jsonl` records
- **Primary Key:** `candidate_id`
- **Purpose:** Human-readable preview; safe for development/testing without loading 464 MB

---

### 2.3 `candidate_schema.json`

- **Format:** JSON Schema Draft-07
- **Purpose:** Validation and documentation of the candidate object structure
- **Contains:** All field names, types, enums, min/max constraints, and descriptions
- **Key enums defined:** `current_company_size`, `education.tier`, `skills.proficiency`, `languages.proficiency`, `redrob_signals.preferred_work_mode`

---

### 2.4 `job_description.docx`

**Role:** Senior AI Engineer — Founding Team at Redrob AI (Series A)

#### Structured Fields Extracted

| JD Attribute | Value |
|--------------|-------|
| Title | Senior AI Engineer |
| Company | Redrob AI |
| Location | Pune / Noida, India (Hybrid) |
| Experience | 5–9 years (preferred 6–8, applied ML at product companies) |
| Employment type | Full-time |

#### Hard-Required Skills (Must-Haves)
1. Production embeddings-based retrieval (sentence-transformers, BGE, E5, OpenAI embeddings)
2. Vector databases / hybrid search (Pinecone, Weaviate, Qdrant, Milvus, FAISS, Elasticsearch, OpenSearch)
3. Strong Python
4. Evaluation frameworks for ranking (NDCG, MRR, MAP, A/B testing)

#### Nice-to-Have Skills
- LLM fine-tuning (LoRA, QLoRA, PEFT)
- Learning-to-rank models (XGBoost-based or neural)
- HR-tech / recruiting tech exposure
- Distributed systems / large-scale inference
- Open-source contributions in AI/ML

#### Explicit Disqualifiers (Important for Ranking)
- Pure research background with no production deployment
- "AI experience" only from recent LangChain-calling-OpenAI projects
- Senior engineer who hasn't written code in 18+ months
- Career entirely at IT services / consulting firms (TCS, Infosys, Wipro, Accenture, etc.)
- CV/Speech/Robotics background without NLP/IR exposure
- 5+ years on closed-source proprietary systems only

#### Behavioral Signals Explicitly Mentioned
- Active on Redrob platform / "in the job market" signals
- Notice period: prefer <30 days (buy-out up to 30 days)
- Candidates inactive for 6+ months with low response rates should be downweighted

#### JD Insight for Ranking
> The JD explicitly warns: *"The right answer involves reasoning about the gap between what the JD says and what the JD means."* A candidate who says "RAG" and "Pinecone" in skills but whose title is "Marketing Manager" is NOT a fit. A candidate without AI keywords but with a career history of building recommendation systems at product companies IS a fit.

---

### 2.5 `sample_submission.csv`

**Format:** CSV with header | **Rows:** 100 (plus 1 header) | **Encoding:** UTF-8

#### Exact Required Schema

| Column | Type | Constraint |
|--------|------|-----------|
| `candidate_id` | string | Must exist in `candidates.jsonl`; format `CAND_XXXXXXX` |
| `rank` | integer | 1–100, sequential, unique, 1 = best |
| `score` | float | 4 decimal places (e.g. `0.9920`); non-increasing with rank |
| `reasoning` | string | 1–2 sentence human-readable justification |

#### Sample Rows

```
candidate_id,rank,score,reasoning
CAND_0004989,1,0.9920,"HR Manager with 6.1 yrs; 9 AI core skills; response rate 0.76."
CAND_0001195,2,0.9840,"HR Manager with 8.7 yrs; 9 AI core skills; response rate 0.20."
CAND_0003114,3,0.9760,"ML Engineer with 6.4 yrs; 4 AI core skills; response rate 0.88."
```

> Note: The sample submission is explicitly labeled as a **format reference only**, not a quality ranking. The ranking above is not a target.

#### Score Range in Sample
- Min: 0.20, Max: 0.992
- The score should reflect actual fit probability; all scores identical = auto-rejection

---

### 2.6 `submission_metadata_template.yaml`

Not a data file — metadata form for portal submission. Required fields:
- `team_name`, `primary_contact`, `team_members`
- `github_repo`, `sandbox_link`, `reproduce_command`
- Compute environment specs (CPU only, ≤16 GB RAM, ≤5 min runtime)
- `ai_tools_used`, `ai_usage_summary`
- `methodology_summary` (≤200 words, strongly recommended)

---

### 2.7 `submission_spec.docx` — Evaluation Rules Summary

#### Scoring Metric (Final Composite)
```
Final Score = 0.50 × NDCG@10 + 0.30 × NDCG@50 + 0.15 × MAP + 0.05 × P@10
```

#### Hard Rules
- Exactly 100 rows (no more, no less)
- Each rank 1–100 appears exactly once
- Each `candidate_id` appears exactly once and must exist in `candidates.jsonl`
- Scores must be non-increasing with rank
- File must be UTF-8 CSV (not .xlsx or .json)

#### Evaluation Pipeline (Stages)
1. **Stage 1:** Automated format validation
2. **Stage 2:** NDCG/MAP scoring against hidden ground truth
3. **Stage 3:** Code reproduction in sandboxed Docker (CPU, 16 GB, 5 min)
4. **Stage 4:** Manual review of reasoning quality (10 sampled rows)
5. **Stage 5:** Technical interview for top candidates

#### Honeypot Warning
~80 candidates have subtly impossible profiles. Submissions with honeypot rate > 10% in top 100 are **disqualified**.

---

### 2.8 `validate_submission.py`

Python script to locally validate submission before uploading. Run:
```bash
python validate_submission.py --submission your_team.csv --candidates candidates.jsonl
```

---

## 3. Data Relationship Map

```
candidates.jsonl (100,000 records)
    └── Primary key: candidate_id (format: CAND_XXXXXXX)

sample_candidates.json (50 records)
    └── Identical schema — subset for development

sample_submission.csv (100 records)
    └── candidate_id → references candidates.jsonl
    └── Defines exact output schema required

candidate_schema.json
    └── Validates candidates.jsonl structure

job_description.docx
    └── Defines the target role (matching target)
    └── Skills in JD should map to candidates.skills[].name

redrob_signals_doc.docx
    └── Explains candidates.redrob_signals fields
```

All `candidate_id` values in `sample_submission.csv` are verified present in `candidates.jsonl`. No cross-file foreign key violations found.

---

## 4. Data Quality Issues

### 4.1 Duplicate Records
**None found.** All 100,000 `candidate_id` values are unique. All ID formats match `^CAND_[0-9]{7}$`.

### 4.2 Honeypot / Impossible Profiles
~122 candidates detected with suspicious flag combinations. Examples:
- **Experience mismatch:** `years_of_experience` >> or << sum of career history months (e.g., 13.7 claimed years but only 0.9 career-history years)
- **Expert skills with zero months used:** `proficiency = "expert"` but `duration_months = 0`
- **Expert skill inflation:** 8–11 skills claimed as "expert" (expert-level is only 0.1% of all skill records globally)

> These are the ~80 documented honeypots. Rank any of them highly and risk disqualification. Your system should detect impossible profile consistencies.

### 4.3 Sentinel Values (Design, Not Bug)
- `github_activity_score = -1` → No GitHub linked (64.6% of candidates)
- `offer_acceptance_rate = -1` → No offer history (59.6% of candidates)
- These must be handled as categorical "not available" states, not as negative scores.

### 4.4 Skill Naming Consistency
The 133 unique skill names are consistent and pre-normalized (no "Python" vs "python" vs "Python3" variations). No free-form skill entry — all skills come from a fixed vocabulary. This is a synthetic dataset design choice.

### 4.5 Date Format Consistency
All dates (`start_date`, `end_date`, `signup_date`, `last_active_date`) use ISO 8601 `YYYY-MM-DD` format uniformly. No inconsistencies found.

### 4.6 Uniform Skill Distribution (Synthetic Artifact)
Top-30 skills each appear in ~12,000 candidates (12% of the pool). This is a synthetic data artifact — in real data, skill frequency would follow a power law. This means naive TF-IDF or keyword counting will produce very flat scores. You need depth signals (proficiency, duration, endorsements) to differentiate.

### 4.7 Profile Completeness Score Distribution
Mean completeness is only 56.8%. Many candidates have substantially incomplete profiles. The `profile_completeness_score` field itself is a useful signal.

### 4.8 Certifications Sparsity
75% of candidates have zero certifications. Only 6 issuers exist (AWS, ASQ, Scrum Alliance, Coursera/DeepLearning.AI, Google Cloud, DeepLearning.AI). For this JD (AI Engineer), AWS and Coursera/DeepLearning.AI certs are the most relevant.

### 4.9 Skill Assessment Score Sparsity
75.8% of candidates have zero completed skill assessments. Only 24.2% have any verified scores. When available, these are the highest-quality skill signals (objective, platform-verified). Don't ignore them.

### 4.10 No Encoding Issues
The JSONL file uses UTF-8 throughout. Unicode characters (e.g., arrows, dashes) in DOCX files are properly represented in JSON candidates.

---

## 5. Field Classification

### 5.1 Free-Text Fields (Best for Semantic / Embedding Matching)

| Field | Location | Content Type |
|-------|----------|-------------|
| `profile.summary` | Top-level | Multi-sentence professional bio — richest semantic signal |
| `profile.headline` | Top-level | One-line career summary |
| `career_history[].description` | Per role | Role responsibilities & achievements — **most JD-relevant text** |
| `career_history[].title` | Per role | Job title (semi-structured) |
| `profile.current_title` | Top-level | Current job title |
| `education[].field_of_study` | Per degree | Study field |
| `certifications[].name` | Per cert | Certification name |

**Recommendation:** Concatenate `profile.summary + profile.headline + career_history[].description` and embed with a sentence transformer for semantic JD-candidate similarity.

### 5.2 Structured / Rule-Based Fields

| Field | Type | Scoring Use |
|-------|------|------------|
| `profile.years_of_experience` | float | Range check: 5–9 years preferred, hard lower bound ~4 |
| `skills[].name` | enum (133 values) | Set intersection with JD required/preferred skills |
| `skills[].proficiency` | ordinal enum | Weight: beginner=1, intermediate=2, advanced=3, expert=4 |
| `skills[].duration_months` | integer | Months of use — depth proxy |
| `skills[].endorsements` | integer | Social proof weight |
| `education[].tier` | ordinal enum | Prestige bonus: tier_1 >> tier_4 |
| `education[].degree` | string | Degree level (B.Tech/B.E. vs M.Tech/M.S. vs Ph.D) |
| `career_history[].industry` | string | Product company vs services company (key disqualifier) |
| `career_history[].company_size` | enum | Startup vs enterprise experience |
| `career_history[].duration_months` | integer | Tenure — longevity signal |
| `certifications[].name` | string | Exact match to relevant certs |
| `redrob_signals.notice_period_days` | integer | JD prefers <30 days |
| `redrob_signals.expected_salary_range_inr_lpa` | object | Salary alignment |

### 5.3 Behavioral / Platform Signal Fields

#### High-Value Behavioral Signals for This JD

| Signal | Meaning | Suggested Use |
|--------|---------|--------------|
| `open_to_work_flag` | Actively looking | Binary multiplier |
| `last_active_date` | Recency of platform engagement | Days-since-active penalty |
| `recruiter_response_rate` | Will they reply? | Availability multiplier |
| `avg_response_time_hours` | How fast they reply | Inverse weight |
| `interview_completion_rate` | Follow-through | Reliability score |
| `offer_acceptance_rate` | Historical intent (when ≠ -1) | Interest signal |
| `github_activity_score` | Active coder (when ≠ -1) | Strong positive for AI Engineer |
| `skill_assessment_scores` | Verified platform scores | Highest-trust skill signal |
| `profile_completeness_score` | Profile quality | Data quality filter |
| `profile_views_received_30d` | Recruiter interest | Passive demand signal |
| `saved_by_recruiters_30d` | Active shortlisting | Market validation |
| `verified_email` + `verified_phone` | Contactable | Reachability gate |
| `notice_period_days` | Time-to-start | JD constraint filter |
| `willing_to_relocate` | Location flexibility | Geography filter |

#### Lower-Value Signals (for this JD)
- `connection_count` — network size, weak proxy for seniority
- `applications_submitted_30d` — job-seeking intensity (high = eager, but could mean desperate)
- `search_appearance_30d` — platform discoverability

---

## 6. Suggested Feature Engineering Strategy

### Tier 1: Semantic Match (Embedding-Based)
Concatenate the following and embed using a lightweight sentence transformer (e.g., `all-MiniLM-L6-v2`):
```
[profile.summary] + [profile.headline] + [career_history[].description joined] 
+ [skills[].name joined] + [certifications[].name joined]
```
Compare against embedded JD text (responsibilities, required skills sections).

**Why:** The JD explicitly warns against keyword-stuffing. Semantic embeddings capture "built a recommendation system at a product company" even without the words "RAG" or "Pinecone."

### Tier 2: Structured Rule-Based Scoring
Build a composite score from explicit match criteria:
1. **Skills overlap score:** JD required skills ∩ candidate skills, weighted by proficiency level and duration_months
2. **Experience window score:** Soft Gaussian penalty for deviation from 5–9 years (center at 7)
3. **Title/career relevance:** Does career history contain AI/ML/Data roles at product companies?
4. **Industry fit:** Penalize candidates whose entire career is at IT services (TCS, Infosys, Wipro, etc.)
5. **Education tier:** Bonus for tier_1/tier_2 institutions
6. **Certification match:** Bonus for AI/ML-relevant certifications
7. **Skill assessment scores:** If available for relevant skills, use as strong override signal
8. **GitHub score:** Positive signal for AI Engineer role (when ≠ -1)

### Tier 3: Behavioral Availability Modifier
Apply as a multiplicative weight on top of Tiers 1+2:
```python
availability_score = (
    open_to_work_flag * 1.2 +
    (1 - days_since_last_active / 180) * 0.8 +
    recruiter_response_rate * 0.5 +
    interview_completion_rate * 0.4 +
    (1 if notice_period_days <= 30 else 0.7 if notice_period_days <= 60 else 0.5)
)
```

### Tier 4: Honeypot Penalization
Before ranking, flag and heavily penalize:
- `expert` proficiency with `duration_months == 0`
- `years_of_experience` > 2× total career_history months
- More than 7 skills at "expert" level

---

## 7. Summary Statistics Card

```
Dataset:          candidates.jsonl
Records:          100,000 candidates
File size:        464.7 MB (uncompressed JSONL)
Primary key:      candidate_id (CAND_XXXXXXX) — 0 duplicates
Schema:           7 top-level sections, 50+ total fields

Demographics:
  Countries:      8 (India 75%, USA 10%, rest 2-3% each)
  Industries:     20+ (IT Services 30%, Software 22%, Manufacturing 22%)
  Experience:     1–17 years, mean 7.2
  Work mode:      ~25% each (remote/hybrid/onsite/flexible)

Skills:
  Unique skills:  133 (synthetic fixed vocabulary)
  Avg per person: 9.6 skills
  Distribution:   Intermediate 49%, Beginner 40%, Advanced 12%, Expert 0.1%

Availability signals:
  Open to work:   35.3%
  Verified email: 72.0%
  Has GitHub:     35.4% (github_activity_score ≠ -1)
  Has skill tests: 24.2%
  Has certs:      25.0%

Submission format:
  File:           team_xxx.csv (UTF-8)
  Columns:        candidate_id, rank, score, reasoning
  Rows:           Exactly 100
  Score formula:  0.50×NDCG@10 + 0.30×NDCG@50 + 0.15×MAP + 0.05×P@10
  Honeypot limit: ≤10% of top 100 (else disqualified)
  Max submissions: 3
```

---

## 8. Key Actionable Observations

1. **The JD title is "Senior AI Engineer" but the dataset has diverse titles** — simple title-matching will miss good candidates. Career history description is far more predictive.

2. **75.6% of candidates have no skill assessment scores** — when available, treat these as gold-standard signals. Missing assessments ≠ low skill; just handle separately.

3. **64.6% have no GitHub linked** (`github_activity_score = -1`) — normalize this properly; don't penalize candidates for not linking GitHub, but reward those who do.

4. **IT services filter is critical** — the JD explicitly disqualifies candidates who have spent their entire career at TCS/Infosys/Wipro/Accenture. Check `career_history[].industry` and `company` for this.

5. **Skill distribution is flat (synthetic artifact)** — do not rely on skill presence alone. Use `proficiency`, `duration_months`, `endorsements`, and cross-reference with `skill_assessment_scores`.

6. **~80 honeypots exist** — build a profile consistency checker as a pre-filter. Look for `expert` + `0 months`, experience math mismatches, implausible certification timelines.

7. **Behavioral signals gate availability** — a perfect-on-paper candidate who is inactive for months with 5% response rate is effectively not hirable. The behavioral multiplier should be real, not cosmetic.

8. **Notice period matters** — JD says "prefer sub-30 days, can buy out up to 30." 30–60 day candidates are still viable. 60–150 day candidates need stronger profile signals to compensate.

9. **Location signals are mixed** — JD says Pune/Noida preferred but "open to relocation candidates from Tier-1 Indian cities." India dominates (75.1% of candidates). Use `willing_to_relocate` for non-Pune/Noida India candidates, and apply a soft penalty for overseas candidates.

10. **NDCG@10 has 50% weight** — precision in your top 10 matters more than anything else. Invest most effort in getting the top 10 right.

---

*End of report. No original data files were modified during this analysis.*
