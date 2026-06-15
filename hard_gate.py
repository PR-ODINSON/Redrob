"""
hard_gate.py — Hard-requirement gate scoring.

Produces gate_score ∈ [0, 1] per candidate:
    gate_score = gate_exp × gate_career × gate_recency

The gate_score is applied MULTIPLICATIVELY to the base score, not additively.
This means a candidate who fails all gates still gets a non-zero score (floor 0.20³ ≈ 0.01),
allowing edge-case genuine candidates to survive — but they will rank very low.

Gates:
  G1 — experience_range fit (Gaussian curve)
  G3 — IT-services career penalty
  G4 — recency-of-hands-on-coding evidence

Gate G2 (tech skill proxy detection) is folded into structured_scorer as a skills match
bonus rather than a gate multiplier, per the approved design — this avoids double-penalizing
candidates who describe AI work in free text but don't have it in the skills list.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from config import (
    CODING_KEYWORDS,
    GATE_EXP_CENTER,
    GATE_EXP_FLOOR,
    GATE_EXP_SIGMA,
    GATE_RECENCY_AMBIGUOUS,
    GATE_RECENCY_HAS_CODE,
    GATE_RECENCY_MANAGERIAL,
    IT_SERVICES_FIRMS,
    IT_SERVICES_FULL_PENALTY,
    IT_SERVICES_HIGH_PENALTY,
    IT_SERVICES_MED_PENALTY,
    MANAGERIAL_KEYWORDS,
)


class GateResult(NamedTuple):
    gate_score: float       # combined multiplier ∈ [0, 1]
    gate_exp: float         # G1 component
    gate_career: float      # G3 component
    gate_recency: float     # G4 component
    it_fraction: float      # fraction of career at IT services firms
    it_months: int          # months at IT services firms
    total_months: int       # total career months


def score_gate(candidate: dict) -> GateResult:
    """Compute all gate components for a single candidate."""
    meta = candidate["_meta"]
    profile = candidate.get("profile", {})

    # ── G1: Experience Gaussian ───────────────────────────────────────────
    years_exp = float(profile.get("years_of_experience") or 0)
    gate_exp = math.exp(-0.5 * ((years_exp - GATE_EXP_CENTER) / GATE_EXP_SIGMA) ** 2)
    gate_exp = max(GATE_EXP_FLOOR, gate_exp)

    # ── G3: IT services career penalty ───────────────────────────────────
    gate_career, it_fraction, it_months = _score_it_services(
        meta["career_companies"],
        candidate.get("career_history", []),
        meta["total_career_months"],
    )

    # ── G4: Recent coding evidence ───────────────────────────────────────
    gate_recency = _score_coding_recency(
        meta["current_role_desc"],
        meta["current_role_title"],
    )

    gate_score = gate_exp * gate_career * gate_recency

    return GateResult(
        gate_score=gate_score,
        gate_exp=gate_exp,
        gate_career=gate_career,
        gate_recency=gate_recency,
        it_fraction=it_fraction,
        it_months=it_months,
        total_months=meta["total_career_months"],
    )


def _is_it_services_company(company_lower: str) -> bool:
    """Return True if the company name matches any known IT services firm."""
    for firm in IT_SERVICES_FIRMS:
        if firm in company_lower:
            return True
    return False


def _score_it_services(
    career_companies: list[str],
    career_history: list[dict],
    total_career_months: int,
) -> tuple[float, float, int]:
    """
    Compute the IT-services gate multiplier based on the fraction of career
    months spent at known IT services firms.

    Returns (gate_career, it_fraction, it_months).
    """
    if total_career_months == 0:
        return 1.0, 0.0, 0

    it_months = 0
    for company_lower, job in zip(career_companies, career_history):
        if _is_it_services_company(company_lower):
            it_months += int(job.get("duration_months") or 0)

    it_fraction = it_months / total_career_months

    if it_fraction >= 1.0:
        gate_career = IT_SERVICES_FULL_PENALTY      # 0.25 — entire career IT services
    elif it_fraction >= 0.75:
        gate_career = IT_SERVICES_HIGH_PENALTY      # 0.50
    elif it_fraction >= 0.50:
        gate_career = IT_SERVICES_MED_PENALTY       # 0.75
    else:
        gate_career = 1.00                          # mostly product companies — no penalty

    return gate_career, it_fraction, it_months


def _score_coding_recency(current_role_desc: str, current_role_title: str) -> float:
    """
    G4: Assess whether the candidate's current/most-recent role shows evidence
    of hands-on coding. JD says "hasn't written production code in 18 months → not a fit."

    Returns one of: GATE_RECENCY_HAS_CODE | GATE_RECENCY_AMBIGUOUS | GATE_RECENCY_MANAGERIAL
    """
    # Check for coding evidence in role description
    desc_lower = current_role_desc.lower()
    title_lower = current_role_title.lower()

    coding_hits = sum(1 for kw in CODING_KEYWORDS if kw in desc_lower)
    managerial_hits = sum(1 for kw in MANAGERIAL_KEYWORDS if kw in desc_lower)

    # Also check title for pure management indicators
    title_is_managerial = any(
        kw in title_lower
        for kw in ["vp ", "vice president", "director", "cto", "coo", "ceo", "head of"]
    )

    if title_is_managerial and coding_hits < 2:
        # Pure executive title with almost no coding evidence in description
        return GATE_RECENCY_MANAGERIAL

    if coding_hits >= 2:
        return GATE_RECENCY_HAS_CODE

    if managerial_hits >= 2 and coding_hits == 0:
        return GATE_RECENCY_MANAGERIAL

    # Ambiguous: some description present but not clearly technical
    return GATE_RECENCY_AMBIGUOUS


def score_gates_batch(candidates: list[dict]) -> list[GateResult]:
    """Score gates for all candidates. Returns results in same order."""
    return [score_gate(c) for c in candidates]
