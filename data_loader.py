"""
data_loader.py — Load and preprocess candidate data and the job description.

Responsibilities:
  - Stream candidates.jsonl (or .jsonl.gz) into memory as a list of dicts.
  - Precompute per-candidate aggregates that are reused across multiple modules:
      total_career_months, career_texts, skill_name_set, etc.
  - Parse job_description.docx into a structured dict of JD requirements.
  - Load candidate_schema.json for reference.

Design note: We load all 100k candidates into memory as plain dicts.
At ~4KB per record average, 100k records ≈ 400MB — well within the 16GB budget.
Streaming is used only during the initial parse to avoid duplicate allocation.
"""

from __future__ import annotations

import gzip
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from docx import Document


# ─────────────────────────────────────────────────────────────
# Candidate loading
# ─────────────────────────────────────────────────────────────

def load_candidates(path: str | Path) -> list[dict]:
    """
    Load candidates from a .jsonl or .jsonl.gz file.
    Returns a list of candidate dicts with precomputed aggregates injected
    under the key '_meta' (so original data is never mutated).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Candidates file not found: {path}")

    candidates: list[dict] = []
    opener = gzip.open if path.suffix == ".gz" else open

    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            candidate = json.loads(line)
            candidate["_meta"] = _precompute_meta(candidate)
            candidates.append(candidate)

    return candidates


def load_candidates_from_json(path: str | Path) -> list[dict]:
    """
    Load the sample_candidates.json file (a JSON array, not JSONL).
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}, got {type(data)}")
    for candidate in data:
        candidate["_meta"] = _precompute_meta(candidate)
    return data


def _precompute_meta(c: dict) -> dict:
    """
    Precompute derived aggregates once per candidate and store in _meta.
    These are accessed repeatedly by honeypot_filter, hard_gate, and scorers.
    """
    career_history: list[dict] = c.get("career_history", [])
    skills: list[dict] = c.get("skills", [])

    # Total career duration in months (sum of all roles)
    total_career_months: int = sum(
        int(job.get("duration_months") or 0) for job in career_history
    )

    # Skill lookup structures
    skill_names: set[str] = {s["name"] for s in skills if "name" in s}
    skill_map: dict[str, dict] = {
        s["name"]: s for s in skills if "name" in s
    }

    # Expert-level skills count (used by H3)
    expert_skill_count: int = sum(
        1 for s in skills if s.get("proficiency") == "expert"
    )

    # Concatenated career description text (lowercased for keyword matching)
    career_desc_texts: list[str] = [
        (job.get("description") or "").lower() for job in career_history
    ]
    all_career_text: str = " ".join(career_desc_texts)

    # Career history companies (lowercased for IT-services matching)
    career_companies: list[str] = [
        (job.get("company") or "").lower() for job in career_history
    ]

    # Current/most-recent role description (for G4 coding-recency gate)
    # career_history is ordered newest-first by convention in this dataset
    current_role_desc: str = ""
    current_role_title: str = ""
    for job in career_history:
        if job.get("is_current") or job.get("end_date") is None:
            current_role_desc = (job.get("description") or "").lower()
            current_role_title = (job.get("title") or "").lower()
            break
    if not current_role_desc and career_history:
        current_role_desc = (career_history[0].get("description") or "").lower()
        current_role_title = (career_history[0].get("title") or "").lower()

    # Parse career start/end dates for overlap detection (H5)
    career_date_ranges: list[tuple[date | None, date | None]] = []
    today = date.today()
    for job in career_history:
        start = _parse_date(job.get("start_date"))
        end_raw = job.get("end_date")
        end = None if (end_raw is None or job.get("is_current")) else _parse_date(end_raw)
        # Clamp future end dates to today for sane calculations
        if end and end > today:
            end = today
        career_date_ranges.append((start, end))

    # Education end years (for H6 future-date check)
    education_end_years: list[int] = [
        int(e.get("end_year", 0)) for e in c.get("education", []) if e.get("end_year")
    ]

    # Highest education tier across all degrees
    from config import EDU_TIER_SCORE
    edu_entries = c.get("education", [])
    best_edu_score: float = max(
        (EDU_TIER_SCORE.get(e.get("tier", "unknown"), 0.40) for e in edu_entries),
        default=0.40,
    )

    # Degree level bonus (take the best degree)
    from config import DEGREE_LEVEL_BONUS
    best_degree_bonus: float = 1.00
    for e in edu_entries:
        degree_key = (e.get("degree") or "").lower().strip(".")
        for key, bonus in DEGREE_LEVEL_BONUS.items():
            if key.replace(".", "") in degree_key.replace(".", ""):
                best_degree_bonus = max(best_degree_bonus, bonus)
                break

    # Skill assessment scores for JD-relevant skills
    from config import JD_ASSESSMENT_TOPICS
    rs = c.get("redrob_signals", {})
    raw_assessments: dict[str, float] = rs.get("skill_assessment_scores") or {}
    relevant_assessments: dict[str, float] = {
        k: float(v) for k, v in raw_assessments.items()
        if k in JD_ASSESSMENT_TOPICS and v is not None
    }

    return {
        "total_career_months": total_career_months,
        "skill_names": skill_names,
        "skill_map": skill_map,
        "expert_skill_count": expert_skill_count,
        "all_career_text": all_career_text,
        "career_desc_texts": career_desc_texts,
        "career_companies": career_companies,
        "current_role_desc": current_role_desc,
        "current_role_title": current_role_title,
        "career_date_ranges": career_date_ranges,
        "education_end_years": education_end_years,
        "best_edu_score": best_edu_score,
        "best_degree_bonus": best_degree_bonus,
        "relevant_assessments": relevant_assessments,
    }


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# Job description parsing
# ─────────────────────────────────────────────────────────────

def load_job_description(path: str | Path) -> dict[str, Any]:
    """
    Parse the job description DOCX and return a structured dict with:
      - full_text: entire JD as a single string (for embedding)
      - title, company, location, experience_range, employment_type
      - required_skills_text: the "things you absolutely need" section
      - preferred_skills_text: the "things we'd like you to have" section
      - disqualifiers_text: the "things we explicitly do NOT want" section
    """
    path = Path(path)
    doc = Document(str(path))

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)

    # Extract structured fields via simple heuristics
    title = _extract_field(paragraphs, "Job Description:", default="Senior AI Engineer")
    company = _extract_field(paragraphs, "Company:", default="Redrob AI")
    location = _extract_field(paragraphs, "Location:", default="Pune/Noida, India")
    employment_type = _extract_field(paragraphs, "Employment Type:", default="Full-time")
    experience_raw = _extract_field(paragraphs, "Experience Required:", default="5-9 years")
    experience_range = _parse_experience_range(experience_raw)

    # Find section blocks
    required_skills_text = _extract_section(
        full_text,
        start_markers=["Things you absolutely need", "you absolutely need"],
        end_markers=["Things we'd like", "Things we explicitly", "On location"],
    )
    preferred_skills_text = _extract_section(
        full_text,
        start_markers=["Things we'd like you to have"],
        end_markers=["Things we explicitly", "On location"],
    )
    disqualifiers_text = _extract_section(
        full_text,
        start_markers=["Things we explicitly do NOT want", "we explicitly do NOT"],
        end_markers=["On location", "The vibe check", "How to read"],
    )

    # Build the embedding text: concatenate JD sections that best describe the role
    # We exclude boilerplate (location, process sections) to keep signal dense
    embedding_text = "\n".join([
        f"Role: {title} at {company}",
        f"Experience: {experience_raw}",
        "Required: " + required_skills_text,
        "Preferred: " + preferred_skills_text,
        # Include a paragraph of context from the responsibilities section
        _extract_section(
            full_text,
            start_markers=["What you'd actually be doing", "high-level mandate"],
            end_markers=["What we mean by"],
        ),
    ])

    return {
        "full_text": full_text,
        "embedding_text": embedding_text,
        "title": title,
        "company": company,
        "location": location,
        "employment_type": employment_type,
        "experience_raw": experience_raw,
        "experience_range": experience_range,  # (min_years, max_years)
        "required_skills_text": required_skills_text,
        "preferred_skills_text": preferred_skills_text,
        "disqualifiers_text": disqualifiers_text,
    }


def _extract_field(paragraphs: list[str], prefix: str, default: str = "") -> str:
    for p in paragraphs:
        if p.startswith(prefix):
            return p[len(prefix):].strip()
    return default


def _extract_section(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    """Extract a text block between start and end marker strings."""
    start_idx = -1
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            start_idx = idx
            break
    if start_idx == -1:
        return ""

    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker, start_idx + 1)
        if idx != -1:
            end_idx = min(end_idx, idx)

    return text[start_idx:end_idx].strip()


def _parse_experience_range(experience_str: str) -> tuple[float, float]:
    """Parse '5–9 years' or '5-9 years' into (5.0, 9.0)."""
    numbers = re.findall(r"(\d+(?:\.\d+)?)", experience_str)
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    elif len(numbers) == 1:
        n = float(numbers[0])
        return (n, n)
    return (5.0, 9.0)  # JD default


# ─────────────────────────────────────────────────────────────
# Schema loading (reference only)
# ─────────────────────────────────────────────────────────────

def load_schema(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────
# Candidate text builder (for semantic embedding)
# ─────────────────────────────────────────────────────────────

def build_candidate_text(candidate: dict) -> str:
    """
    Build the text representation of a candidate for semantic embedding.
    Combines headline + summary + career history descriptions.
    Titles are prefixed to give them slight extra weight.
    """
    p = candidate.get("profile", {})
    parts: list[str] = []

    headline = (p.get("headline") or "").strip()
    if headline:
        parts.append(headline)

    summary = (p.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    for job in candidate.get("career_history", []):
        title = (job.get("title") or "").strip()
        desc = (job.get("description") or "").strip()
        if title:
            parts.append(f"Role: {title}.")
        if desc:
            parts.append(desc)

    # Include skill names as a comma-separated list for keyword anchoring
    skills = candidate.get("skills", [])
    if skills:
        skill_list = ", ".join(s["name"] for s in skills if "name" in s)
        parts.append(f"Skills: {skill_list}.")

    return " ".join(parts)
