"""
behavioral_scorer.py — Behavioral / platform signal scoring.

Produces behavioral_score ∈ [0, 1] representing candidate availability and
engagement quality on the Redrob platform.

SENTINEL VALUE POLICY (critical):
  github_activity_score = -1  → candidate has no GitHub linked → score 0.30 (slightly
                                 below neutral 0.50, because absence of any code trail
                                 is mildly negative for an AI Engineer role)
  offer_acceptance_rate = -1  → no offer history → neutral 0.50 (not penalized)
  Missing / None fields      → neutral 0.50 (unknown, not penalized)

Rationale: a candidate without platform data is not a bad candidate.
Behavioral signals reduce/boost an already-structured score, they don't drive it.

Signal weights (from config.py):
  open_to_work_flag         0.20
  last_active_date (recency) 0.20
  recruiter_response_rate   0.20
  notice_period_days        0.15
  interview_completion_rate 0.10
  github_activity_score     0.10
  verified contact          0.05
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import NamedTuple

from config import (
    BEH_WEIGHT_GITHUB,
    BEH_WEIGHT_INTERVIEW_COMPLETION,
    BEH_WEIGHT_NOTICE_PERIOD,
    BEH_WEIGHT_OPEN_TO_WORK,
    BEH_WEIGHT_RECENCY,
    BEH_WEIGHT_RESPONSE_RATE,
    BEH_WEIGHT_VERIFIED,
    NOTICE_PERIOD_SCORES,
    RECENCY_DECAY,
)


class BehavioralResult(NamedTuple):
    behavioral_score: float
    open_to_work: bool
    days_since_active: int
    response_rate: float
    notice_days: int
    interview_completion: float
    github_score_raw: float   # -1 or 0–100
    has_github: bool


def score_behavioral(candidate: dict) -> BehavioralResult:
    rs = candidate.get("redrob_signals", {})
    today = date.today()

    # ── Open to work ──────────────────────────────────────────────────────
    # True → full score; False → not penalized (many good candidates are passive)
    open_to_work: bool = bool(rs.get("open_to_work_flag", False))
    open_score = 1.00 if open_to_work else 0.40

    # ── Last active date (recency decay) ──────────────────────────────────
    last_active_str = rs.get("last_active_date")
    days_since_active = 999
    if last_active_str:
        try:
            last_active = datetime.strptime(last_active_str[:10], "%Y-%m-%d").date()
            days_since_active = (today - last_active).days
        except ValueError:
            pass
    recency_score = _interpolate(days_since_active, RECENCY_DECAY, higher_is_worse=True)

    # ── Recruiter response rate ───────────────────────────────────────────
    raw_response = rs.get("recruiter_response_rate")
    response_rate: float = float(raw_response) if raw_response is not None else 0.50  # neutral
    response_score = response_rate  # already in [0, 1]

    # ── Notice period ─────────────────────────────────────────────────────
    notice_raw = rs.get("notice_period_days")
    notice_days: int = int(notice_raw) if notice_raw is not None else 90  # default neutral
    notice_score = _interpolate(notice_days, NOTICE_PERIOD_SCORES, higher_is_worse=True)

    # ── Interview completion rate ─────────────────────────────────────────
    raw_interview = rs.get("interview_completion_rate")
    interview_completion: float = float(raw_interview) if raw_interview is not None else 0.50
    interview_score = interview_completion

    # ── GitHub activity score ──────────────────────────────────────────────
    # -1 = no GitHub linked → 0.30 (slight discount vs neutral 0.50 for an AI Engineer role)
    #  0-100 → normalized to [0, 1]
    github_raw: float = float(rs.get("github_activity_score", -1))
    has_github = github_raw >= 0
    if github_raw < 0:
        github_score = 0.30   # no GitHub — small penalty (not zero)
    else:
        github_score = github_raw / 100.0

    # ── Verified contact ──────────────────────────────────────────────────
    verified_email = bool(rs.get("verified_email", False))
    verified_phone = bool(rs.get("verified_phone", False))
    if verified_email and verified_phone:
        verified_score = 1.00
    elif verified_email or verified_phone:
        verified_score = 0.70
    else:
        verified_score = 0.40  # not penalized heavily, but unverified contact is a mild risk

    # ── Combine ───────────────────────────────────────────────────────────
    behavioral_score = (
        BEH_WEIGHT_OPEN_TO_WORK         * open_score
        + BEH_WEIGHT_RECENCY            * recency_score
        + BEH_WEIGHT_RESPONSE_RATE      * response_score
        + BEH_WEIGHT_NOTICE_PERIOD      * notice_score
        + BEH_WEIGHT_INTERVIEW_COMPLETION * interview_score
        + BEH_WEIGHT_GITHUB             * github_score
        + BEH_WEIGHT_VERIFIED           * verified_score
    )

    return BehavioralResult(
        behavioral_score=min(1.0, max(0.0, behavioral_score)),
        open_to_work=open_to_work,
        days_since_active=days_since_active,
        response_rate=response_rate,
        notice_days=notice_days,
        interview_completion=interview_completion,
        github_score_raw=github_raw,
        has_github=has_github,
    )


def _interpolate(
    value: float,
    breakpoints: list[tuple[int, float]],
    higher_is_worse: bool = False,
) -> float:
    """
    Linear interpolation between breakpoint tuples (x, y) where x is the input
    domain value and y is the output score. If higher_is_worse, higher input → lower score.
    """
    if not breakpoints:
        return 0.50

    xs = [b[0] for b in breakpoints]
    ys = [b[1] for b in breakpoints]

    if value <= xs[0]:
        return ys[0]
    if value >= xs[-1]:
        return ys[-1]

    for i in range(len(xs) - 1):
        if xs[i] <= value <= xs[i + 1]:
            t = (value - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])

    return ys[-1]


def compute_assessment_boost(candidate: dict) -> float:
    """
    Compute the skill_assessment_boost component (weight 0.10 in final score).

    Uses only assessments for JD-relevant skills (precomputed in _meta).
    When assessments are absent, returns 0.50 (neutral — not punished).
    When present, returns mean(scores) / 100 normalized to [0, 1].
    """
    meta = candidate["_meta"]
    relevant = meta.get("relevant_assessments", {})
    if not relevant:
        return 0.50  # unknown — neutral

    mean_score = sum(relevant.values()) / len(relevant)
    return mean_score / 100.0  # scores are 0–100 in schema


def score_behavioral_batch(candidates: list[dict]) -> list[BehavioralResult]:
    """Score behavioral signals for all candidates."""
    return [score_behavioral(c) for c in candidates]
