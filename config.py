"""
config.py — Central configuration for the Redrob candidate ranking pipeline.

All tuneable constants live here. After the first full run, adjust PRESCREEN_CUTOFF
and weights based on the score-distribution printout from main.py before resubmitting.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# Pipeline topology
# ─────────────────────────────────────────────────────────────

# Candidates passed from structured pre-screen → semantic re-rank.
# Raising this improves recall at the cost of embedding time.
PRESCREEN_CUTOFF: int = 3000

# How many candidates to generate reasoning for (≥ 100).
REASONING_POOL: int = 150

# Final output size (must be 100 per spec).
TOP_N: int = 100

# ─────────────────────────────────────────────────────────────
# Honeypot detection thresholds
# ─────────────────────────────────────────────────────────────

# H1: Any skill with proficiency=="expert" AND duration_months==0 → honeypot
# (No threshold needed — one instance is enough.)

# H2: Experience claimed vs career history math
# years_of_experience > sum_career_years * HONEYPOT_EXP_RATIO_UPPER + HONEYPOT_EXP_BUFFER
HONEYPOT_EXP_RATIO_UPPER: float = 1.6   # upper multiplier on career years
HONEYPOT_EXP_BUFFER: float = 2.0        # additive buffer (pre-career / internship gap)
HONEYPOT_EXP_RATIO_LOWER: float = 0.4   # lower multiplier — can't claim far less than career
HONEYPOT_EXP_LOWER_BUFFER: float = 1.0  # additive lower buffer

# H3: Too many "expert"-level skills
HONEYPOT_EXPERT_COUNT_THRESHOLD: int = 8  # 8+ expert skills → honeypot

# H4: Skill duration far exceeds total career span.
# Buffer = 36 months (3yr) to allow pre-career learning (college, side projects).
# Baseline = max(career_history_months, years_of_experience × 12) — generous.
HONEYPOT_SKILL_DURATION_BUFFER_MONTHS: int = 36  # allow 12 months side-project slack

# H5: Career overlap threshold (months of overlap before flagging)
HONEYPOT_OVERLAP_MONTHS: int = 3

# Honeypot rate warnings / disqualification (per spec)
HONEYPOT_WARN_THRESHOLD: float = 0.05    # warn if honeypot rate in top-100 exceeds 5%
HONEYPOT_DISQUALIFY_THRESHOLD: float = 0.10  # spec hard disqualification at 10%

# ─────────────────────────────────────────────────────────────
# Hard gate multipliers (gate_score = gate_exp * gate_career * gate_recency)
# ─────────────────────────────────────────────────────────────

# G1 — Experience Gaussian: center and spread
GATE_EXP_CENTER: float = 7.0   # ideal years of experience
GATE_EXP_SIGMA: float = 2.5    # standard deviation (Gaussian width)
GATE_EXP_FLOOR: float = 0.20   # minimum so no candidate is zeroed on experience alone

# G3 — IT services career penalty multipliers (applied to gate_career)
IT_SERVICES_FULL_PENALTY: float = 0.25   # entire career at IT services
IT_SERVICES_HIGH_PENALTY: float = 0.50   # ≥ 75% of career at IT services
IT_SERVICES_MED_PENALTY: float = 0.75    # ≥ 50% of career at IT services

# G4 — Coding-recency gate values
GATE_RECENCY_HAS_CODE: float = 1.00    # current/recent role shows coding evidence
GATE_RECENCY_AMBIGUOUS: float = 0.85   # ambiguous role description
GATE_RECENCY_MANAGERIAL: float = 0.60  # current role appears managerial / strategy-only

# ─────────────────────────────────────────────────────────────
# Final score combination weights (must sum to 1.0)
# ─────────────────────────────────────────────────────────────
# gate_score is applied multiplicatively, not additively.
# final_score = gate_score × (WEIGHT_STRUCTURED × structured_score
#                            + WEIGHT_SEMANTIC   × semantic_score
#                            + WEIGHT_BEHAVIORAL × behavioral_score
#                            + WEIGHT_ASSESSMENT × assessment_boost)

WEIGHT_STRUCTURED:  float = 0.40   # career evidence, skills, edu, certs
WEIGHT_SEMANTIC:    float = 0.35   # JD–profile cosine similarity (top 3k only)
WEIGHT_BEHAVIORAL:  float = 0.15   # availability / engagement signals
WEIGHT_ASSESSMENT:  float = 0.10   # platform-verified skill assessment scores

assert abs(WEIGHT_STRUCTURED + WEIGHT_SEMANTIC + WEIGHT_BEHAVIORAL + WEIGHT_ASSESSMENT - 1.0) < 1e-9

# ─────────────────────────────────────────────────────────────
# Structured scorer sub-weights (must sum to 1.0)
# ─────────────────────────────────────────────────────────────
STRUCT_WEIGHT_SKILLS:   float = 0.40  # weighted skill match against JD
STRUCT_WEIGHT_CAREER:   float = 0.30  # career trajectory / product-company ML titles
STRUCT_WEIGHT_EXP:      float = 0.20  # experience-curve score (Gaussian, same as G1)
STRUCT_WEIGHT_EDU:      float = 0.06  # education tier bonus
STRUCT_WEIGHT_CERTS:    float = 0.04  # relevant certification bonus

assert abs(STRUCT_WEIGHT_SKILLS + STRUCT_WEIGHT_CAREER + STRUCT_WEIGHT_EXP
           + STRUCT_WEIGHT_EDU + STRUCT_WEIGHT_CERTS - 1.0) < 1e-9

# ─────────────────────────────────────────────────────────────
# Behavioral scorer sub-weights (must sum to 1.0)
# ─────────────────────────────────────────────────────────────
BEH_WEIGHT_OPEN_TO_WORK:         float = 0.20
BEH_WEIGHT_RECENCY:              float = 0.20
BEH_WEIGHT_RESPONSE_RATE:        float = 0.20
BEH_WEIGHT_NOTICE_PERIOD:        float = 0.15
BEH_WEIGHT_INTERVIEW_COMPLETION: float = 0.10
BEH_WEIGHT_GITHUB:               float = 0.10
BEH_WEIGHT_VERIFIED:             float = 0.05

assert abs(BEH_WEIGHT_OPEN_TO_WORK + BEH_WEIGHT_RECENCY + BEH_WEIGHT_RESPONSE_RATE
           + BEH_WEIGHT_NOTICE_PERIOD + BEH_WEIGHT_INTERVIEW_COMPLETION
           + BEH_WEIGHT_GITHUB + BEH_WEIGHT_VERIFIED - 1.0) < 1e-9

# ─────────────────────────────────────────────────────────────
# Skill proficiency → weight mapping
# ─────────────────────────────────────────────────────────────
PROFICIENCY_WEIGHT: dict[str, float] = {
    "beginner":     0.25,
    "intermediate": 0.50,
    "advanced":     0.85,
    "expert":       1.00,
}

# ─────────────────────────────────────────────────────────────
# JD skill relevance tiers
# Required skills (hard needs per JD) — score 1.0 or close
# Preferred skills (nice-to-haves) — score 0.5-0.7
# Adjacent skills (background signal) — score 0.2-0.4
# ─────────────────────────────────────────────────────────────

# Skills the JD explicitly requires or strongly implies
REQUIRED_SKILLS: dict[str, float] = {
    # Core ML / AI
    "Python":               1.00,   # "Strong Python. Yes really."
    "NLP":                  0.95,   # embeddings, retrieval = NLP
    "MLOps":                0.85,   # production deployment
    "TensorFlow":           0.70,
    "PyTorch":              0.70,
    "Scikit-learn":         0.65,
    # Search / retrieval / vector infra
    "Elasticsearch":        0.80,
    "Kafka":                0.50,   # data infra adjacent
    # Cloud / infra (production indicator)
    "AWS":                  0.55,
    "Docker":               0.55,
    "Kubernetes":           0.50,
    # Data engineering (upstream of ML)
    "Spark":                0.45,
    "Airflow":              0.45,
    "BigQuery":             0.40,
}

# Nice-to-have skills per JD
PREFERRED_SKILLS: dict[str, float] = {
    "SQL":                  0.40,
    "ETL":                  0.35,
    "CI/CD":                0.35,
    "Git":                  0.30,
    "Databricks":           0.45,
    "Java":                 0.25,
    "Go":                   0.25,
    "TypeScript":           0.20,
    "Agile":                0.20,
    "Scrum":                0.15,
    "Project Management":   0.10,
}

# All JD-relevant skills in one dict (used for skill_assessment_scores lookup)
JD_RELEVANT_SKILLS: set[str] = set(REQUIRED_SKILLS) | set(PREFERRED_SKILLS)

# Skill assessment score topics that map to the JD
JD_ASSESSMENT_TOPICS: set[str] = {
    "NLP", "Python", "Machine Learning", "Deep Learning",
    "Fine-tuning LLMs", "Image Classification", "Speech Recognition",
    "Data Engineering", "MLOps", "SQL",
}

# ─────────────────────────────────────────────────────────────
# Career trajectory signals
# ─────────────────────────────────────────────────────────────

# Job title keywords that indicate relevant ML/AI/Data seniority
# Tiered by relevance — tier 1 = strongest signal
CAREER_TITLE_TIERS: dict[str, float] = {
    # Tier 1 — clearly on-target
    "machine learning engineer":    1.00,
    "ml engineer":                  1.00,
    "ai engineer":                  1.00,
    "research engineer":            0.90,
    "nlp engineer":                 0.95,
    "data scientist":               0.85,
    "applied scientist":            0.85,
    "senior engineer":              0.70,
    "software engineer":            0.65,
    # Tier 2 — adjacent but relevant
    "data engineer":                0.60,
    "backend engineer":             0.55,
    "platform engineer":            0.50,
    "devops engineer":              0.40,
    "full stack engineer":          0.45,
    # Tier 3 — weak signal
    "analyst":                      0.30,
    "consultant":                   0.25,
    "manager":                      0.20,
    "lead":                         0.35,
    "architect":                    0.40,
}

# Career description keywords indicating production ML/AI work
CAREER_ML_KEYWORDS: list[str] = [
    "embedding", "embeddings", "retrieval", "rag", "vector", "recommendation",
    "ranking", "search", "inference", "model", "training", "fine-tun",
    "transformer", "bert", "llm", "nlp", "neural", "classification",
    "pipeline", "feature", "mlops", "serving", "deploy", "productio",
    "faiss", "pinecone", "weaviate", "elasticsearch", "opensearch",
    "sentence-transformer", "huggingface", "pytorch", "tensorflow", "sklearn",
    "ndcg", "mrr", "evaluation", "benchmark", "a/b test",
]

# Description keywords signaling hands-on coding
CODING_KEYWORDS: list[str] = [
    "implemented", "built", "developed", "shipped", "wrote", "engineered",
    "designed and built", "refactored", "optimised", "optimized", "coded",
    "integrated", "migrated", "automated", "deployed", "authored",
]

# Description keywords signaling purely managerial / non-coding role
MANAGERIAL_KEYWORDS: list[str] = [
    "managed team", "managed a team", "led team", "led a team",
    "stakeholder", "roadmap", "okr", "strategy", "executive", "board",
    "p&l", "budget", "headcount", "hiring manager",
]

# ─────────────────────────────────────────────────────────────
# Education tier → score
# ─────────────────────────────────────────────────────────────
EDU_TIER_SCORE: dict[str, float] = {
    "tier_1":   1.00,
    "tier_2":   0.75,
    "tier_3":   0.50,
    "tier_4":   0.30,
    "unknown":  0.40,   # benefit of the doubt
}

# Degree level → bonus multiplier on top of institution tier
DEGREE_LEVEL_BONUS: dict[str, float] = {
    "ph.d":   1.20,
    "phd":    1.20,
    "m.tech": 1.10,
    "m.e.":   1.10,
    "m.s.":   1.10,
    "m.sc":   1.05,
    "mba":    0.90,  # slight discount for non-technical MBA for this JD
    "b.tech": 1.00,
    "b.e.":   1.00,
    "b.sc":   0.95,
    "b.s.":   0.95,
}

# ─────────────────────────────────────────────────────────────
# Certification relevance
# ─────────────────────────────────────────────────────────────
CERT_RELEVANCE: dict[str, float] = {
    # High relevance for this AI Engineer JD
    "coursera/deeplearning.ai": 0.90,
    "deeplearning.ai":          0.90,
    "google cloud":             0.75,
    "aws":                      0.70,
    # Lower relevance
    "scrum alliance":           0.25,
    "asq":                      0.15,
}

# ─────────────────────────────────────────────────────────────
# IT services firms (the JD explicitly disqualifies entire-career-IT-services candidates)
# Match against career_history.company (case-insensitive substring)
# ─────────────────────────────────────────────────────────────
IT_SERVICES_FIRMS: list[str] = [
    "tcs", "tata consultancy",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "hcl technologies", "hcl tech",
    "tech mahindra",
    "mphasis",
    "hexaware",
    "l&t infotech", "ltimindtree",
    "patni",
    "igate",
    "niit technologies",
    "mastech",
    "syntel",
    "mindtree",   # current company of sample CAND_0000001 — correctly penalized per JD
    "persistent systems",
    "zensar",
    "cyient",
    "mphasize",
    "birlasoft",
    "kpit",
]

# ─────────────────────────────────────────────────────────────
# Sentence transformer model (must be cached offline before ranking)
# ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_BATCH_SIZE: int = 256   # tune down if OOM on low-RAM machines
EMBEDDING_MAX_SEQ_LEN: int = 384  # MiniLM default; texts are truncated to this

# ─────────────────────────────────────────────────────────────
# Behavioral scorer — notice period score breakpoints (days → score)
# ─────────────────────────────────────────────────────────────
NOTICE_PERIOD_SCORES: list[tuple[int, float]] = [
    (0,   1.00),   # immediate joiner
    (30,  1.00),   # JD says "can buy out up to 30 days"
    (60,  0.80),   # still viable
    (90,  0.60),   # 3-month notice — common in India, but a concern
    (120, 0.40),
    (150, 0.25),
    (180, 0.15),   # maximum schema value
]

# Behavioural scorer — last-active recency decay (days → score)
RECENCY_DECAY: list[tuple[int, float]] = [
    (7,   1.00),
    (30,  0.90),
    (60,  0.75),
    (90,  0.60),
    (120, 0.45),
    (180, 0.30),
    (270, 0.20),
    (365, 0.10),
]

# ─────────────────────────────────────────────────────────────
# File paths (relative to the project root)
# ─────────────────────────────────────────────────────────────
CANDIDATES_JSONL:        str = "data/candidates.jsonl"
CANDIDATES_JSONL_GZ:     str = "data/candidates.jsonl.gz"
SAMPLE_CANDIDATES_JSON:  str = "data/sample_candidates.json"
JD_DOCX:                 str = "docs/job_description.docx"
SIGNALS_DOCX:            str = "docs/redrob_signals_doc.docx"
SCHEMA_JSON:             str = "data/candidate_schema.json"
OUTPUT_CSV:              str = "output/submission.csv"
