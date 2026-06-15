"""
honeypot_filter.py — Rule-based honeypot / impossible-profile detection.

Six independent rules (H1–H6), each producing a boolean flag and a reason string.
A candidate is marked is_honeypot = True if ANY rule fires.

Rules are derived from:
  - submission_spec.docx Section 7: explicit examples of honeypot patterns
  - candidate_schema.json: field types and value ranges
  - Empirical analysis of the 100k pool (see dataset_analysis.md)

All rules operate ONLY on precomputed _meta values (computed once in data_loader.py)
and the raw candidate dict. No re-parsing occurs here.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

from config import (
    HONEYPOT_EXP_BUFFER,
    HONEYPOT_EXP_LOWER_BUFFER,
    HONEYPOT_EXP_RATIO_LOWER,
    HONEYPOT_EXP_RATIO_UPPER,
    HONEYPOT_EXPERT_COUNT_THRESHOLD,
    HONEYPOT_OVERLAP_MONTHS,
    HONEYPOT_SKILL_DURATION_BUFFER_MONTHS,
)


class HoneypotResult(NamedTuple):
    is_honeypot: bool
    flags: list[str]   # list of rule IDs that fired, e.g. ["H1", "H3"]
    reasons: list[str] # human-readable explanations for debugging


def check_honeypot(candidate: dict) -> HoneypotResult:
    """
    Run all honeypot rules against a single candidate.
    Returns a HoneypotResult with combined flag and per-rule reasons.
    """
    meta = candidate["_meta"]
    flags: list[str] = []
    reasons: list[str] = []

    # ── H1: Expert proficiency with zero duration ────────────────────────
    # Spec: "expert proficiency in skills with 0 years used"
    for skill in candidate.get("skills", []):
        if skill.get("proficiency") == "expert" and skill.get("duration_months", 1) == 0:
            flags.append("H1")
            reasons.append(
                f"H1: skill '{skill.get('name')}' claimed as expert with 0 months duration"
            )
            break  # one instance is enough; avoid duplicate H1 entries

    # ── H2: Claimed experience vs career history math ────────────────────
    # years_of_experience >> or << sum of career_history durations
    claimed_years: float = float(candidate.get("profile", {}).get("years_of_experience") or 0)
    total_career_months: int = meta["total_career_months"]
    total_career_years: float = total_career_months / 12.0

    if total_career_years > 0:
        upper_limit = total_career_years * HONEYPOT_EXP_RATIO_UPPER + HONEYPOT_EXP_BUFFER
        lower_limit = total_career_years * HONEYPOT_EXP_RATIO_LOWER - HONEYPOT_EXP_LOWER_BUFFER

        if claimed_years > upper_limit:
            flags.append("H2")
            reasons.append(
                f"H2: claimed {claimed_years:.1f}yr experience but career history "
                f"totals only {total_career_years:.1f}yr (upper limit {upper_limit:.1f}yr)"
            )
        elif total_career_years > 1.0 and claimed_years < lower_limit:
            # Only flag the lower bound if career is substantial (avoid flagging new grads)
            flags.append("H2")
            reasons.append(
                f"H2: claimed only {claimed_years:.1f}yr but career history "
                f"totals {total_career_years:.1f}yr (lower limit {lower_limit:.1f}yr)"
            )

    # ── H3: Expert skill inflation ───────────────────────────────────────
    # Spec: "expert proficiency in 10 skills". We use 8 as conservative threshold.
    # Only 0.1% of all skills in the 100k pool are rated "expert".
    expert_count: int = meta["expert_skill_count"]
    if expert_count >= HONEYPOT_EXPERT_COUNT_THRESHOLD:
        flags.append("H3")
        reasons.append(
            f"H3: {expert_count} skills rated 'expert' "
            f"(threshold {HONEYPOT_EXPERT_COUNT_THRESHOLD}; global rate is 0.1%)"
        )

    # ── H4: Skill duration far exceeds total career span ─────────────────
    # A candidate cannot have used a skill for 120 months if their experience is 12 months.
    # We use max(career_months, claimed_experience_months) as the baseline so pre-career
    # learning (college, side projects) is fairly accounted for. Buffer = 36 months
    # (3 years) allows students who learned skills before their first formal role.
    buffer = HONEYPOT_SKILL_DURATION_BUFFER_MONTHS
    claimed_experience_months = claimed_years * 12.0
    # Use the more generous of career history total or claimed years
    effective_experience_months = max(total_career_months, claimed_experience_months)
    for skill in candidate.get("skills", []):
        skill_duration = skill.get("duration_months") or 0
        if effective_experience_months > 0 and skill_duration > (effective_experience_months + buffer):
            flags.append("H4")
            reasons.append(
                f"H4: skill '{skill.get('name')}' has {skill_duration}mo duration "
                f"but effective experience is only {effective_experience_months:.0f}mo "
                f"(+{buffer}mo buffer = {effective_experience_months+buffer:.0f}mo max)"
            )
            break

    # ── H5: Overlapping full-time roles ──────────────────────────────────
    # Two non-current roles with overlapping date ranges (> threshold months)
    date_ranges = meta["career_date_ranges"]
    career_history = candidate.get("career_history", [])
    past_roles = [
        (i, dr) for i, (dr, job) in enumerate(zip(date_ranges, career_history))
        if not job.get("is_current") and dr[0] is not None and dr[1] is not None
    ]
    overlap_found = False
    for i in range(len(past_roles)):
        if overlap_found:
            break
        for j in range(i + 1, len(past_roles)):
            idx_i, (start_i, end_i) = past_roles[i]
            idx_j, (start_j, end_j) = past_roles[j]
            # Check if these two roles overlap
            overlap_start = max(start_i, start_j)
            overlap_end = min(end_i, end_j)
            if overlap_start < overlap_end:
                overlap_months = (overlap_end - overlap_start).days // 30
                if overlap_months > HONEYPOT_OVERLAP_MONTHS:
                    flags.append("H5")
                    reasons.append(
                        f"H5: career roles {idx_i+1} and {idx_j+1} overlap by "
                        f"~{overlap_months} months "
                        f"({start_i} to {end_i} vs {start_j} to {end_j})"
                    )
                    overlap_found = True
                    break

    # ── H6: Future dates in past history ─────────────────────────────────
    today = date.today()
    for i, (job, (start, end)) in enumerate(zip(career_history, date_ranges)):
        if not job.get("is_current") and end is not None and end > today:
            flags.append("H6")
            reasons.append(
                f"H6: role {i+1} is marked not-current but end_date {end} is in the future"
            )
            break

    # Cross-check: graduated in future but has substantial experience
    for end_year in meta["education_end_years"]:
        if end_year > today.year and claimed_years > 3.0:
            flags.append("H6")
            reasons.append(
                f"H6: education ends in {end_year} (future) "
                f"but candidate claims {claimed_years:.1f}yr experience"
            )
            break

    return HoneypotResult(
        is_honeypot=len(flags) > 0,
        flags=sorted(set(flags)),
        reasons=reasons,
    )


def filter_honeypots(candidates: list[dict]) -> tuple[list[dict], dict[str, HoneypotResult]]:
    """
    Run honeypot detection on the full candidate pool.
    Returns:
      - clean_candidates: candidates where is_honeypot == False
      - honeypot_results: dict of candidate_id → HoneypotResult for all candidates
    """
    honeypot_results: dict[str, HoneypotResult] = {}
    clean_candidates: list[dict] = []

    for candidate in candidates:
        cid = candidate.get("candidate_id", "UNKNOWN")
        result = check_honeypot(candidate)
        honeypot_results[cid] = result
        # Inject the honeypot result into _meta for downstream access
        candidate["_meta"]["honeypot"] = result
        if not result.is_honeypot:
            clean_candidates.append(candidate)

    return clean_candidates, honeypot_results


def honeypot_summary(honeypot_results: dict[str, HoneypotResult]) -> dict:
    """Return summary statistics for reporting in main.py."""
    total = len(honeypot_results)
    flagged = sum(1 for r in honeypot_results.values() if r.is_honeypot)
    rule_counts: dict[str, int] = {}
    for r in honeypot_results.values():
        for flag in r.flags:
            rule_counts[flag] = rule_counts.get(flag, 0) + 1
    return {
        "total": total,
        "flagged": flagged,
        "flagged_pct": 100 * flagged / total if total else 0,
        "rule_counts": rule_counts,
    }
