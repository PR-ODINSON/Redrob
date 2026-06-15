"""
structured_scorer.py — Rule-based structured scoring of candidate profiles.

Produces structured_score ∈ [0, 1] per candidate, as a weighted combination of:
  - skills_score (0.40): weighted skill match against JD, using proficiency + duration
  - career_score (0.30): career trajectory — ML/AI titles, product-company work
  - exp_score   (0.20): experience-curve Gaussian (same formula as G1 gate)
  - edu_score   (0.06): education tier × degree level
  - cert_score  (0.04): relevant certification bonus

The structured_score feeds the fast pre-screen (Stage 1 of the two-stage funnel).
All 100k candidates are scored here; only PRESCREEN_CUTOFF are passed to semantic.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from config import (
    CAREER_ML_KEYWORDS,
    CAREER_TITLE_TIERS,
    CERT_RELEVANCE,
    GATE_EXP_CENTER,
    GATE_EXP_FLOOR,
    GATE_EXP_SIGMA,
    PREFERRED_SKILLS,
    PROFICIENCY_WEIGHT,
    REQUIRED_SKILLS,
    STRUCT_WEIGHT_CAREER,
    STRUCT_WEIGHT_CERTS,
    STRUCT_WEIGHT_EDU,
    STRUCT_WEIGHT_EXP,
    STRUCT_WEIGHT_SKILLS,
)


class StructuredResult(NamedTuple):
    structured_score: float   # final combined [0, 1]
    skills_score: float
    career_score: float
    exp_score: float
    edu_score: float
    cert_score: float
    top_matched_skills: list[str]  # for reasoning_generator
    python_present: bool           # for reasoning + gate
    has_ml_career_evidence: bool   # for reasoning


def score_structured(candidate: dict) -> StructuredResult:
    """Compute structured score for a single candidate."""
    meta = candidate["_meta"]
    profile = candidate.get("profile", {})

    skills_score, top_skills, python_present = _score_skills(
        candidate.get("skills", []),
        meta["skill_names"],
        meta["skill_map"],
    )

    career_score, has_ml = _score_career(
        candidate.get("career_history", []),
        meta["all_career_text"],
        meta["career_desc_texts"],
    )

    exp_score = _score_experience(float(profile.get("years_of_experience") or 0))

    edu_score = _score_education(
        meta["best_edu_score"],
        meta["best_degree_bonus"],
    )

    cert_score = _score_certifications(candidate.get("certifications", []))

    structured_score = (
        STRUCT_WEIGHT_SKILLS  * skills_score
        + STRUCT_WEIGHT_CAREER  * career_score
        + STRUCT_WEIGHT_EXP   * exp_score
        + STRUCT_WEIGHT_EDU   * edu_score
        + STRUCT_WEIGHT_CERTS * cert_score
    )

    return StructuredResult(
        structured_score=min(1.0, structured_score),
        skills_score=skills_score,
        career_score=career_score,
        exp_score=exp_score,
        edu_score=edu_score,
        cert_score=cert_score,
        top_matched_skills=top_skills,
        python_present=python_present,
        has_ml_career_evidence=has_ml,
    )


# ─────────────────────────────────────────────────────────────
# Sub-scorers
# ─────────────────────────────────────────────────────────────

def _score_skills(
    skills: list[dict],
    skill_names: set[str],
    skill_map: dict[str, dict],
) -> tuple[float, list[str], bool]:
    """
    Compute the skills match score against the JD.

    Scoring per skill:
      contribution = proficiency_weight × duration_weight × jd_relevance

    Duration weight: capped at 48 months (4 years) to avoid over-rewarding stale skills.
    This prevents a candidate with 10-year-old Python from dominating over a 3-year expert.
    """
    DURATION_CAP = 48.0  # months

    # Python absence cap: if Python is not present, cap skills_score at 0.40
    # (the JD says "Strong Python. Yes really." — it's a hard requirement)
    python_present = "Python" in skill_names

    contributions: list[tuple[float, str]] = []

    # Score required skills
    for skill_name, jd_relevance in REQUIRED_SKILLS.items():
        if skill_name in skill_map:
            s = skill_map[skill_name]
            prof_w = PROFICIENCY_WEIGHT.get(s.get("proficiency", "beginner"), 0.25)
            dur_w = min(float(s.get("duration_months") or 1) / DURATION_CAP, 1.0)
            # Endorsements give a small trust boost (capped at +10%)
            endorse_boost = min(float(s.get("endorsements") or 0) / 50.0, 0.10)
            contrib = jd_relevance * prof_w * dur_w * (1.0 + endorse_boost)
            contributions.append((contrib, skill_name))

    # Score preferred skills (with lower base relevance)
    for skill_name, jd_relevance in PREFERRED_SKILLS.items():
        if skill_name in skill_map:
            s = skill_map[skill_name]
            prof_w = PROFICIENCY_WEIGHT.get(s.get("proficiency", "beginner"), 0.25)
            dur_w = min(float(s.get("duration_months") or 1) / DURATION_CAP, 1.0)
            contrib = jd_relevance * prof_w * dur_w
            contributions.append((contrib, skill_name))

    if not contributions:
        return (0.0, [], python_present)

    # Normalize: divide by theoretical maximum (all required skills at expert/48mo/0 endorse)
    max_possible = sum(REQUIRED_SKILLS.values()) + sum(PREFERRED_SKILLS.values())
    # Expert + 48mo = proficiency_weight(1.0) * dur_w(1.0) * relevance
    # So max_possible with endorsements included:
    theoretical_max = (
        sum(v * 1.0 * 1.0 * 1.10 for v in REQUIRED_SKILLS.values())
        + sum(v * 1.0 * 1.0 for v in PREFERRED_SKILLS.values())
    )

    raw_score = sum(c for c, _ in contributions)
    skills_score = min(raw_score / theoretical_max, 1.0)

    # Apply Python cap if needed
    if not python_present:
        skills_score = min(skills_score, 0.40)

    # Top matched skills for reasoning (sorted by contribution)
    contributions.sort(reverse=True)
    top_skills = [name for _, name in contributions[:5]]

    return skills_score, top_skills, python_present


def _score_career(
    career_history: list[dict],
    all_career_text: str,
    career_desc_texts: list[str],
) -> tuple[float, bool]:
    """
    Score career trajectory for ML/AI relevance at product companies.

    Two components:
    1. Title relevance: best-matching title tier across all roles
    2. ML evidence: fraction of career descriptions containing ML/AI keywords
    """
    if not career_history:
        return 0.0, False

    # 1. Title relevance score (best title across all roles, weighted by recency)
    title_scores: list[float] = []
    for i, job in enumerate(career_history):
        title_lower = (job.get("title") or "").lower()
        recency_weight = 1.0 / (1.0 + i * 0.15)  # more recent = higher weight

        best_title_score = 0.0
        for title_key, score in CAREER_TITLE_TIERS.items():
            if title_key in title_lower:
                best_title_score = max(best_title_score, score)

        # Fallback: generic "engineer" or "developer" gets a baseline
        if best_title_score == 0.0 and any(
            kw in title_lower for kw in ["engineer", "developer", "scientist", "analyst"]
        ):
            best_title_score = 0.30

        title_scores.append(best_title_score * recency_weight)

    title_score = min(sum(title_scores) / len(title_scores), 1.0) if title_scores else 0.0

    # 2. ML evidence density: how much of career text mentions ML/AI work
    # Count keyword hits across all descriptions, normalized by description count
    ml_hit_count = sum(
        1 for kw in CAREER_ML_KEYWORDS if kw in all_career_text
    )
    ml_evidence_score = min(ml_hit_count / 15.0, 1.0)  # 15+ distinct keywords = max score
    has_ml_evidence = ml_hit_count >= 3

    # Recency bonus: does the MOST RECENT role show ML evidence?
    most_recent_ml = sum(
        1 for kw in CAREER_ML_KEYWORDS if kw in (career_desc_texts[0] if career_desc_texts else "")
    )
    recency_bonus = 0.10 if most_recent_ml >= 3 else 0.0

    career_score = 0.50 * title_score + 0.45 * ml_evidence_score + 0.05 * recency_bonus
    career_score = min(career_score + recency_bonus, 1.0)

    return career_score, has_ml_evidence


def _score_experience(years_exp: float) -> float:
    """
    Smooth Gaussian experience curve, same formula as gate G1 but used
    here as a positive-signal component (not a penalty).
    """
    score = math.exp(-0.5 * ((years_exp - GATE_EXP_CENTER) / GATE_EXP_SIGMA) ** 2)
    return max(GATE_EXP_FLOOR, score)


def _score_education(best_edu_score: float, best_degree_bonus: float) -> float:
    """
    Education tier × degree-level bonus, capped at 1.0.
    Precomputed in data_loader._precompute_meta.
    """
    return min(best_edu_score * best_degree_bonus, 1.0)


def _score_certifications(certifications: list[dict]) -> float:
    """
    Certification relevance bonus.
    Only positive (no penalty for absence — 75% of candidates have none).
    Relevant certs: DeepLearning.AI, Google Cloud, AWS > Scrum, ASQ.
    """
    if not certifications:
        return 0.0

    best_score = 0.0
    for cert in certifications:
        issuer_lower = (cert.get("issuer") or "").lower().strip()
        name_lower = (cert.get("name") or "").lower()

        for issuer_key, relevance in CERT_RELEVANCE.items():
            if issuer_key in issuer_lower:
                # Extra bump if cert name also contains ML-relevant terms
                ml_bump = 0.10 if any(
                    kw in name_lower
                    for kw in ["machine learning", "deep learning", "ai", "ml", "data"]
                ) else 0.0
                best_score = max(best_score, min(relevance + ml_bump, 1.0))
                break

    return best_score


def score_structured_batch(candidates: list[dict]) -> list[StructuredResult]:
    """Score all candidates. Returns results in same order."""
    return [score_structured(c) for c in candidates]
