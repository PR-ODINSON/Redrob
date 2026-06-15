"""
final_ranker.py — Orchestrates the two-stage ranking funnel.

Stage 1 (fast pre-screen, all 100k candidates):
  pre_screen_score = gate_score × (structured_score + behavioral_score)
  → Take top PRESCREEN_CUTOFF candidates

Stage 2 (semantic re-rank, top PRESCREEN_CUTOFF only):
  final_score = gate_score × (
      WEIGHT_STRUCTURED × structured_score
    + WEIGHT_SEMANTIC   × semantic_score
    + WEIGHT_BEHAVIORAL × behavioral_score
    + WEIGHT_ASSESSMENT × assessment_boost
  )
  → Select top REASONING_POOL, generate reasoning, output top TOP_N

Honeypots are excluded before final selection.
A warning is raised if the honeypot rate in the top-100 (pre-exclusion) exceeds
HONEYPOT_WARN_THRESHOLD, and an assertion enforces the 10% hard limit.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from behavioral_scorer import BehavioralResult, compute_assessment_boost, score_behavioral_batch
from config import (
    HONEYPOT_DISQUALIFY_THRESHOLD,
    HONEYPOT_WARN_THRESHOLD,
    OUTPUT_CSV,
    PRESCREEN_CUTOFF,
    REASONING_POOL,
    TOP_N,
    WEIGHT_ASSESSMENT,
    WEIGHT_BEHAVIORAL,
    WEIGHT_SEMANTIC,
    WEIGHT_STRUCTURED,
)
from hard_gate import GateResult, score_gates_batch
from honeypot_filter import HoneypotResult, filter_honeypots, honeypot_summary
from reasoning_generator import generate_reasoning_batch
from structured_scorer import StructuredResult, score_structured_batch


@dataclass
class CandidateRecord:
    """Holds all scoring artifacts for a single candidate."""
    candidate: dict
    honeypot: HoneypotResult
    gate: GateResult
    structured: StructuredResult
    behavioral: BehavioralResult
    assessment_boost: float
    semantic_score: float      # 0.0 until Stage 2 fills it in
    pre_screen_score: float    # Stage 1 ordering score
    final_score: float         # Stage 2 final score


def run_ranking_pipeline(
    candidates: list[dict],
    jd_data: dict,
    semantic_model=None,
    verbose: bool = True,
) -> tuple[list[CandidateRecord], dict]:
    """
    Full ranking pipeline.

    Args:
        candidates:      Full candidate pool (already loaded + _meta precomputed)
        jd_data:         Parsed JD dict from data_loader.load_job_description()
        semantic_model:  Pre-loaded SentenceTransformer (pass None to skip semantic)
        verbose:         Print timing info

    Returns:
        top_records:  Top TOP_N CandidateRecords (non-honeypot), ranked best→worst
        stats:        Summary statistics dict
    """
    timings: dict[str, float] = {}
    stats: dict = {}

    def _tick(label: str, t0: float) -> float:
        elapsed = time.time() - t0
        timings[label] = elapsed
        if verbose:
            print(f"  [{label}] {elapsed:.2f}s")
        return time.time()

    total_input = len(candidates)
    t0 = time.time()

    # ── Step 1: Honeypot detection (full pool) ────────────────────────────
    if verbose:
        print(f"\nStep 1: Honeypot detection ({total_input:,} candidates)...")
    clean_candidates, honeypot_results = filter_honeypots(candidates)
    hp_stats = honeypot_summary(honeypot_results)
    t0 = _tick("honeypot_filter", t0)

    if verbose:
        print(f"  Honeypots flagged: {hp_stats['flagged']} ({hp_stats['flagged_pct']:.2f}%)")
        print(f"  Rule breakdown: {hp_stats['rule_counts']}")

    # ── Step 2: Structured scoring (full pool, clean only) ────────────────
    if verbose:
        print(f"\nStep 2: Structured scoring ({len(clean_candidates):,} clean candidates)...")
    structured_results = score_structured_batch(clean_candidates)
    t0 = _tick("structured_scorer", t0)

    # ── Step 3: Behavioral scoring (full pool, clean only) ────────────────
    if verbose:
        print(f"\nStep 3: Behavioral scoring ({len(clean_candidates):,} candidates)...")
    behavioral_results = score_behavioral_batch(clean_candidates)
    assessment_boosts = [compute_assessment_boost(c) for c in clean_candidates]
    t0 = _tick("behavioral_scorer", t0)

    # ── Step 4: Gate scoring (full pool, clean only) ──────────────────────
    if verbose:
        print(f"\nStep 4: Gate scoring ({len(clean_candidates):,} candidates)...")
    gate_results = score_gates_batch(clean_candidates)
    t0 = _tick("gate_scorer", t0)

    # ── Step 5: Pre-screen score (Stage 1) ───────────────────────────────
    # Simple sum: gate × (structured + behavioral) — semantic not yet computed
    if verbose:
        print(f"\nStep 5: Pre-screen scoring & top-{PRESCREEN_CUTOFF} selection...")

    pre_screen_scores = np.array([
        gate.gate_score * (
            WEIGHT_STRUCTURED * sr.structured_score
            + WEIGHT_BEHAVIORAL * br.behavioral_score
            + WEIGHT_ASSESSMENT * ab
        )
        for sr, br, gate, ab in zip(structured_results, behavioral_results, gate_results, assessment_boosts)
    ])

    # Get indices of top PRESCREEN_CUTOFF by pre-screen score
    if len(pre_screen_scores) <= PRESCREEN_CUTOFF:
        top_prescreen_indices = np.argsort(-pre_screen_scores)
    else:
        # Use argpartition for efficiency, then sort just the top chunk
        partition_idx = np.argpartition(-pre_screen_scores, PRESCREEN_CUTOFF)[:PRESCREEN_CUTOFF]
        top_prescreen_indices = partition_idx[np.argsort(-pre_screen_scores[partition_idx])]

    cutoff_score = float(pre_screen_scores[top_prescreen_indices[-1]])
    t0 = _tick("prescreen", t0)

    if verbose:
        print(f"  Pre-screen cutoff score: {cutoff_score:.4f}")
        print(f"  Pre-screen top score:    {float(pre_screen_scores[top_prescreen_indices[0]]):.4f}")

    # ── Step 6: Semantic scoring (top PRESCREEN_CUTOFF only) ─────────────
    prescreen_candidates = [clean_candidates[i] for i in top_prescreen_indices]

    if semantic_model is not None:
        if verbose:
            print(f"\nStep 6: Semantic scoring ({len(prescreen_candidates)} candidates)...")
        from semantic_scorer import embed_jd, score_semantic_batch
        jd_embedding = embed_jd(semantic_model, jd_data)
        semantic_scores_arr = score_semantic_batch(
            semantic_model, jd_embedding, prescreen_candidates, show_progress=verbose
        )
        t0 = _tick("semantic_scorer", t0)
    else:
        # Fallback if no model provided (e.g., offline test without model downloaded)
        if verbose:
            print("\nStep 6: Semantic scoring SKIPPED (no model provided)")
        semantic_scores_arr = np.full(len(prescreen_candidates), 0.50)
        timings["semantic_scorer"] = 0.0

    # ── Step 7: Final score computation (top PRESCREEN_CUTOFF) ────────────
    if verbose:
        print(f"\nStep 7: Computing final scores...")

    records: list[CandidateRecord] = []
    for j, orig_idx in enumerate(top_prescreen_indices):
        c = clean_candidates[orig_idx]
        sr = structured_results[orig_idx]
        br = behavioral_results[orig_idx]
        gr = gate_results[orig_idx]
        ab = assessment_boosts[orig_idx]
        sem = float(semantic_scores_arr[j])
        pre = float(pre_screen_scores[orig_idx])

        final = gr.gate_score * (
            WEIGHT_STRUCTURED * sr.structured_score
            + WEIGHT_SEMANTIC   * sem
            + WEIGHT_BEHAVIORAL * br.behavioral_score
            + WEIGHT_ASSESSMENT * ab
        )

        hp_result = honeypot_results[c.get("candidate_id", "")]

        records.append(CandidateRecord(
            candidate=c,
            honeypot=hp_result,
            gate=gr,
            structured=sr,
            behavioral=br,
            assessment_boost=ab,
            semantic_score=sem,
            pre_screen_score=pre,
            final_score=final,
        ))

    # Sort by final score descending
    records.sort(key=lambda r: (-r.final_score, r.candidate.get("candidate_id", "")))

    t0 = _tick("final_scoring", t0)

    # ── Step 8: Honeypot rate check in pre-exclusion top-100 ──────────────
    pre_exclusion_top100 = records[:TOP_N]
    hp_in_top100 = sum(1 for r in pre_exclusion_top100 if r.honeypot.is_honeypot)
    hp_rate_top100 = hp_in_top100 / TOP_N

    if hp_rate_top100 > HONEYPOT_WARN_THRESHOLD:
        print(f"\n⚠  WARNING: Honeypot rate in top-100 (pre-exclusion) = "
              f"{hp_rate_top100:.1%} > {HONEYPOT_WARN_THRESHOLD:.0%} threshold")

    if hp_rate_top100 > HONEYPOT_DISQUALIFY_THRESHOLD:
        raise RuntimeError(
            f"CRITICAL: Honeypot rate {hp_rate_top100:.1%} exceeds "
            f"disqualification threshold {HONEYPOT_DISQUALIFY_THRESHOLD:.0%}. "
            f"Investigate scoring pipeline before submitting."
        )

    # ── Step 9: Exclude honeypots, select final top-100 ───────────────────
    # All honeypots should already be excluded since we ran filter_honeypots first,
    # but include a safety check in case some slipped through the prescreen
    clean_records = [r for r in records if not r.honeypot.is_honeypot]
    final_top = clean_records[:TOP_N]

    if len(final_top) < TOP_N:
        if len(clean_records) < 10:
            raise RuntimeError(
                f"Only {len(clean_records)} non-honeypot candidates available. "
                f"Something is wrong with honeypot rules or data loading."
            )
        # In sample/test runs the pool may be smaller than TOP_N — just use what we have
        print(f"  ⚠  Only {len(final_top)} clean candidates available (TOP_N={TOP_N}). "
              f"Using all available for sample/small-pool run.")

    # ── Step 10: Generate reasoning for top REASONING_POOL ───────────────
    if verbose:
        print(f"\nStep 8: Generating reasoning strings (top {REASONING_POOL})...")

    reasoning_pool = clean_records[:REASONING_POOL]
    pool_scores = [r.final_score for r in reasoning_pool]
    pool_ranks = list(range(1, len(reasoning_pool) + 1))

    reasonings = generate_reasoning_batch(
        [r.candidate for r in reasoning_pool],
        [r.structured for r in reasoning_pool],
        [r.behavioral for r in reasoning_pool],
        [r.gate for r in reasoning_pool],
        pool_scores,
        pool_ranks,
    )

    # Attach reasoning to records
    reasoning_map = {
        reasoning_pool[i].candidate.get("candidate_id"): reasonings[i]
        for i in range(len(reasoning_pool))
    }
    t0 = _tick("reasoning", t0)

    # ── Compile stats ─────────────────────────────────────────────────────
    stats = {
        "total_input": total_input,
        "honeypots_found": hp_stats["flagged"],
        "honeypot_pct": hp_stats["flagged_pct"],
        "honeypot_rules": hp_stats["rule_counts"],
        "clean_candidates": len(clean_candidates),
        "prescreen_cutoff": PRESCREEN_CUTOFF,
        "prescreen_cutoff_score": cutoff_score,
        "prescreen_top_score": float(pre_screen_scores[top_prescreen_indices[0]]),
        "honeypot_in_top100_preexclusion": hp_in_top100,
        "honeypot_rate_top100": hp_rate_top100,
        "final_top_score": records[0].final_score if records else 0,
        "final_100th_score": final_top[-1].final_score if final_top else 0,
        "timings": timings,
        "total_time": sum(timings.values()),
    }

    return final_top, reasoning_map, stats


def write_submission_csv(
    top_records: list[CandidateRecord],
    reasoning_map: dict[str, str],
    output_path: str = OUTPUT_CSV,
) -> Path:
    """
    Write the final ranked submission CSV matching the exact spec:
      candidate_id, rank, score, reasoning
      100 rows, ranks 1–100, scores non-increasing.
    """
    path = Path(output_path)

    # Normalise scores to [0, 1] range while preserving rank order
    # The spec says score should be in [0,1] and non-increasing; we round to 4 decimals
    scores = [r.final_score for r in top_records]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0

    # Min-max normalise to [0.20, 0.99] to avoid zero scores
    def normalise(s: float) -> float:
        if max_score == min_score:
            return 0.99
        return 0.20 + 0.79 * (s - min_score) / (max_score - min_score)

    normalised = [normalise(s) for s in scores]

    # Re-sort: within groups of equal normalised score, order by candidate_id ascending
    # (spec tie-break rule). The sort must be stable to preserve score ordering.
    paired = sorted(
        zip(top_records, normalised),
        key=lambda x: (round(-x[1], 4), x[0].candidate.get("candidate_id", "")),
    )
    top_records = [p[0] for p in paired]
    normalised  = [p[1] for p in paired]

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        prev_score = None
        for rank, (record, norm_score) in enumerate(zip(top_records, normalised), start=1):
            cid = record.candidate.get("candidate_id", f"UNKNOWN_{rank}")

            # Enforce non-increasing constraint (handle float rounding edge cases)
            if prev_score is not None and norm_score > prev_score:
                norm_score = prev_score
            prev_score = norm_score

            score_str = f"{norm_score:.4f}"
            reasoning = reasoning_map.get(cid, f"Rank {rank} candidate per scoring model.")

            # Sanitise reasoning for CSV (remove newlines, truncate if too long)
            reasoning = reasoning.replace("\n", " ").replace("\r", " ").strip()
            if len(reasoning) > 400:
                reasoning = reasoning[:397] + "..."

            writer.writerow([cid, rank, score_str, reasoning])

    return path
